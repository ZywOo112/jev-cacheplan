"""Single/batch Noul, Choice or Score through the real JEV Backend; IDs restored."""
import argparse
import json
import uuid
from pathlib import Path
import _bootstrap
from project_runtime import ROOT, read, save, load_service_config
from solo_layout import LayoutOptimizer, read_json
from adapters.jev_adapter import LoggedBackend
from layout.execution import execute_plan

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT/'examples/sample_data.json')
    p.add_argument('--question', default='Does the customer_request ask for a monetary refund?')
    p.add_argument('--kind', choices=['noul','choice','score'], default='noul')
    p.add_argument('--options', help='JSON array required for choice; e.g. ["refund","replacement"]')
    p.add_argument('--method', choices=['original','solo'], default='solo')
    p.add_argument('--limit', type=int)
    p.add_argument('--plan-only', action='store_true')
    p.add_argument('--compare', action='store_true')
    args = p.parse_args()
    rows = read(args.input)
    if args.limit is not None:
        if args.limit < 1: p.error('--limit must be positive')
        rows = rows[:args.limit]
    methods = ['original','solo'] if args.compare else [args.method]
    data = read_json(rows)
    if args.plan_only:
        for method in methods:
            plan = LayoutOptimizer(method, seed=42).plan(data)
            print(json.dumps({'method': method, 'row_order': plan.row_order.tolist(), 'column_order': plan.column_order.tolist(), 'columns': list(plan.ordered_columns)}))
        return
    config = load_service_config()
    run = ROOT / 'runs' / ('example_' + uuid.uuid4().hex)
    run.mkdir(parents=True)
    options = json.loads(args.options) if args.options else None
    for method in methods:
        plan = LayoutOptimizer(method, seed=42).plan(data)
        backend = LoggedBackend(f"http://{config['host']}:{config['port']}", model_dir=Path(config['model_dir']),
                                log_path=run/(method+'_http.jsonl'), timeout=600, max_retries=0, request_seed=0)
        try:
            output = execute_plan(data, args.question, plan, backend, kind=args.kind, options=options,
                                  concurrency=2, cache_salt='example-'+uuid.uuid4().hex)
        finally:
            backend.close()
        save(run/(method+'.json'), output)
        print(json.dumps({'method': method, 'result': output}, ensure_ascii=False))
    print('Results:', run)

if __name__ == '__main__': main()
