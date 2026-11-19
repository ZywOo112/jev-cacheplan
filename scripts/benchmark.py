"""Regenerate pinned author data, measure real JEV scans, or summarize saved results."""
import argparse
import csv
import importlib.util
import json
import statistics
import subprocess
import sys
import uuid
from pathlib import Path
import _bootstrap
from project_runtime import ROOT, REPO, SHA, REVISION, read, save, digest, utc, load_service_config
from fetch_solo import verify

DATA = ROOT / 'data/generated'

def prepare():
    from tokenizers import Tokenizer
    from solo_layout import DecisionSpec, LayoutOptimizer
    from solo_layout._table import as_table, Serializer
    verify()
    config = load_service_config()
    tokenizer_file = Path(config['model_dir'])/'tokenizer.json'
    tokenizer = Tokenizer.from_file(str(tokenizer_file))
    count = lambda value: len(tokenizer.encode(value, add_special_tokens=False).ids)
    source = importlib.util.spec_from_file_location('pinned_author_demo', REPO/'demo.py')
    demo = importlib.util.module_from_spec(source)
    source.loader.exec_module(demo)
    settings = read(ROOT/'configs/benchmark.json')
    reference = {c['case']: c for c in read(ROOT/'benchmarks/dataset_manifests.json')}
    for name in settings['case_order']:
        target = DATA/name
        if target.exists():
            meta = read(target/'manifest.json')
            for f, expected in meta['files'].items():
                if digest(target/f) != expected: raise RuntimeError('Existing generated file changed: '+f)
            print('Verified existing', name); continue
        frame, truth, details = demo.shared(settings['rows'], settings['cases'][name]['ratio'], settings['seed'], count)
        info = demo.describe(frame, count, details)
        if info['dataset_sha256'] != reference[name]['workload']['dataset_sha256']:
            raise RuntimeError('Generated data differs from the fixed author workload')
        if digest(tokenizer_file) != reference[name]['tokenizer_sha256']:
            raise RuntimeError('Unexpected tokenizer; fixed revision required')
        records = frame.to_dict(orient='records')
        table = as_table(frame)
        spec = DecisionSpec.create(settings['question'])
        lengths = {}
        for method in ['original','solo']:
            plan = LayoutOptimizer(method, seed=42).plan(table)
            renderer = Serializer(table, plan.column_order)
            lengths[method] = [{'record_id': r['record_id'], 'tokens': count(spec.prompt(renderer(i))),
                                'prompt_sha256': __import__('hashlib').sha256(spec.prompt(renderer(i)).encode()).hexdigest()}
                               for i,r in enumerate(records)]
        maximum = max(r['tokens'] for vals in lengths.values() for r in vals)
        if maximum + 1 > config['max_model_len']:
            raise RuntimeError('Full prompt exceeds max_model_len; do not truncate')
        target.mkdir(parents=True)
        (target/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
        save(target/'truth.json', [bool(x) for x in truth])
        save(target/'prompt_lengths.json', lengths)
        save(target/'manifest.json', {'case': name, 'seed': settings['seed'], 'workload': info,
             'max_prompt_tokens': maximum, 'tokenizer_sha256': digest(tokenizer_file),
             'model_revision': REVISION, 'upstream_commit': SHA,
             'files': {p.name: digest(p) for p in target.iterdir() if p.is_file()}})
        print('Generated and author-SHA verified', name, maximum, 'maximum prompt tokens')

def analyze(session=None):
    if session:
        rows = []
        for d in read(session/'completed_runs.json'):
            q = d['quality']; p = d['performance']
            rows.append({'case': d['case'], 'method': d['method'], 'repeat': d['repeat'], 'run_id': d['run_id'],
                         **{k:v for k,v in p.items() if isinstance(v,(float,int))},
                         'accuracy': q['accuracy'], 'macro_f1':q['macro_f1']})
        output = session/'analysis_summary.json'
    else:
        with (ROOT/'benchmarks/results/run_metrics.csv').open() as f: rows = list(csv.DictReader(f))
        output = None
    result = {}
    for case in sorted({r['case'] for r in rows}):
        groups = {method: [r for r in rows if r['case']==case and r['method']==method] for method in ['original','solo']}
        info = {}
        for method, data in groups.items():
            if not data: raise ValueError('A complete Original/SOLO pair is required')
            seconds = [float(x['end_to_end_seconds']) for x in data]
            info[method] = {'n':len(data), 'seconds_values':seconds, 'median_seconds':statistics.median(seconds),
                 'mean_seconds': statistics.mean(seconds), 'sample_sd_seconds': statistics.stdev(seconds) if len(seconds)>1 else None}
        info['median_time_speedup'] = info['original']['median_seconds']/info['solo']['median_seconds']
        result[case] = info
    if output: save(output,result)
    print(json.dumps(result,indent=2))
    return result

def run(stop_service=False):
    from evaluation.solo_reproduction import measure, cache_probe
    from evaluation.telemetry import Meter
    verify()
    config = load_service_config()
    # Freeze actual selected device UUID, rather than treating example index 0 as universal.
    config['gpu_uuid'] = subprocess.check_output(['nvidia-smi','--id='+config['gpu_uuid'],
                 '--query-gpu=uuid','--format=csv,noheader'],text=True,timeout=10).strip()
    settings = read(ROOT/'configs/benchmark.json')
    session = ROOT/'runs'/('shared_'+uuid.uuid4().hex)
    session.mkdir(parents=True)
    save(session/'configuration.json', {'service':config,'benchmark':settings,'created_utc':utc()})
    meter = Meter(f"http://{config['host']}:{config['port']}")
    completed = []
    try:
        meter.completed = int(meter.snapshot().get('vllm:request_success_total',0))
        core = [json.loads(x) for x in (DATA/'shared_970/records.jsonl').read_text().splitlines()]
        proof = session/'cache_probe'; proof.mkdir()
        cache_probe(core, settings['question'], config, meter, proof)
        for name in settings['case_order']:
            d = DATA/name
            meta = read(d/'manifest.json')
            for file, expected in meta['files'].items():
                if digest(d/file) != expected: raise RuntimeError('Generated input integrity check failed')
            if meta['max_prompt_tokens']+1>config['max_model_len']: raise RuntimeError('Full prompt cannot fit, no truncation allowed')
            records = [json.loads(x) for x in (d/'records.jsonl').read_text().splitlines()]
            truth, lengths = read(d/'truth.json'), read(d/'prompt_lengths.json')
            for repeat in range(1,settings['cases'][name]['repeats']+1):
                for method in settings['orders'][repeat-1]:
                    dest = session/(name+'_r'+str(repeat)+'_'+method)
                    dest.mkdir()
                    summary = measure(records, truth, method, name, repeat, settings['question'], lengths, dest, config, meter)
                    completed.append({'run_id':dest.name, **summary})
                    save(session/'completed_runs.json', completed)
        analyze(session)
    finally:
        meter.session.close()
        if stop_service:
            subprocess.run([sys.executable,'-B',str(ROOT/'scripts/service.py'),'stop'],check=True)
    print('Saved unique session:', session)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    runner = sub.add_parser('run'); runner.add_argument('--stop-service',action='store_true')
    analysis = sub.add_parser('analyze'); analysis.add_argument('--session',type=Path)
    args = parser.parse_args(argv)
    if args.action == 'prepare': prepare()
    elif args.action == 'run': run(args.stop_service)
    else: analyze(args.session)

if __name__ == '__main__': main()
