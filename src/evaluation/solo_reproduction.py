"""Author-demo execution with real cache accounting and positional restoration."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from dataclasses import asdict
import hashlib,json,time,uuid
from pathlib import Path
import numpy as np
import pandas as pd
from solo_layout import LayoutOptimizer,DecisionSpec
from solo_layout._table import as_table,Serializer
from layout.validation import validate_plan,validate_distribution
from adapters.jev_adapter import LoggedBackend
from evaluation.telemetry import Meter,ResourceSampler
from evaluation.classification import classification
from project_runtime import ROOT,REPO,SHA,REVISION,save,read,digest,utc

def build_inputs(records,method):
    ids=[r['record_id'] for r in records]
    if not ids or len(set(ids))!=len(ids):raise ValueError('Nonempty unique author IDs are required')
    table=as_table(pd.DataFrame(records));plan=LayoutOptimizer(method,seed=42).plan(table)
    validate_plan(plan,len(records),table.columns)
    render=Serializer(table,plan.column_order);states=[render(int(i)) for i in plan.row_order]
    for index,text in zip(plan.row_order,states):
        assert json.loads(text)==records[int(index)] and tuple(json.loads(text))==plan.ordered_columns
    return table,plan,states

def restore_outputs(plan,ids,planned,responses,latencies):
    n=len(ids)
    if len(responses)!=n or any(x is None for x in responses):raise ValueError('Missing response')
    request_ids=[r['request_id'] for r in responses]
    if any(not x for x in request_ids) or len(set(request_ids))!=n:raise ValueError('Duplicate or missing server request ID')
    matrix=np.asarray(planned)
    if matrix.shape!=(n,2):raise ValueError('Noul probabilities must be N x 2')
    for row in matrix:validate_distribution(row,(False,True))
    restored=plan.restore(matrix)
    restored_ids=plan.restore(np.asarray([ids[int(i)] for i in plan.row_order],dtype=object)).tolist()
    assert restored_ids==ids
    assert np.array_equal(plan.restore(matrix.argmax(axis=1)),restored.argmax(axis=1))
    return restored,plan.restore(np.asarray(responses,dtype=object)).tolist(),plan.restore(np.asarray(latencies))

def backend(config,path):
    return LoggedBackend(f"http://127.0.0.1:{config['port']}",model_dir=Path(config['model_dir']),
        log_path=path,timeout=600,max_retries=0,request_seed=0)

def cache_probe(records,question,config,meter,run):
    _,_,states=build_inputs(records,'solo');spec=DecisionSpec.create(question)
    b=backend(config,run/'cache_probe_http.jsonl');salt='m3-probe-'+uuid.uuid4().hex;values=[]
    try:
        for i,s in enumerate([salt,salt,salt+'-fresh']):
            r=b.decide(states[0],spec,cache_salt=s,audit_id='probe-'+str(i));meter.completed+=1;values.append(asdict(r))
    finally:b.close()
    assert values[0]['cached_tokens']==0 and values[1]['cached_tokens']>0 and values[2]['cached_tokens']==0
    save(run/'cache_isolation.json',{'utc':utc(),'responses':values,'passed':True,'probe_not_formal':True})
    meter.barrier()

def measure(records,truth,method,case,repeat,question,expected,run,config,meter):
    n=len(records);ids=[r['record_id'] for r in records];spec=DecisionSpec.create(question)
    save(run/'input.json',{'records':records,'truth_sidecar':truth,'question':question,'author_ID_is_original_input_field':True})
    code_paths=[ROOT/'src/evaluation/solo_reproduction.py',ROOT/'src/adapters/jev_adapter.py',
       ROOT/'src/layout/validation.py',ROOT/'src/project_runtime.py',ROOT/'scripts/run_solo_reproduction.py',ROOT/'scripts/service.py']
    save(run/'code_versions.json',{str(p.relative_to(ROOT)):digest(p) for p in code_paths})
    save(run/'configuration.json',{'case':case,'repeat':repeat,'method':method,'service':config,'concurrency':4,
         'seed':42,'request_seed':0,'upstream_commit':SHA,'model_revision':REVISION,'question':question,
         'dataset_sha256':digest(ROOT/'data/generated'/case/'records.jsonl')})
    # Match the author's four-record warmup, but in a separate cache namespace.
    b=backend(config,run/'warmup_http.jsonl');table=as_table(pd.DataFrame(records[:4]));render=Serializer(table,range(len(table.columns)))
    try:
        for i in range(4):b.decide(render(i),spec,cache_salt='warm-'+run.name,audit_id='warm-'+str(i));meter.completed+=1
    finally:b.close()
    barrier_before=meter.barrier();before=meter.snapshot(run/'metrics_before.prom')
    sampler=ResourceSampler(run,config).start();salt='m3-'+uuid.uuid4().hex
    save(run/'namespace.json',{'cache_salt':salt,'warmup_salt':'warm-'+run.name})
    start=time.perf_counter();t=start
    table,plan,states=build_inputs(records,method);layout_seconds=time.perf_counter()-t
    lengths={item['record_id']:item for item in expected[method]}
    for i,text in zip(plan.row_order,states):
        assert hashlib.sha256(spec.prompt(text).encode()).hexdigest()==lengths[ids[int(i)]]['prompt_sha256']
    prepared_seconds=time.perf_counter()-start
    b=backend(config,run/'http.jsonl');planned=np.empty((n,2));responses=[None]*n;latencies=np.empty(n)
    def execute(position):
        index=int(plan.row_order[position]);tick=time.perf_counter()
        response=b.decide(states[position],spec,cache_salt=salt,audit_id=ids[index]);seconds=time.perf_counter()-tick
        assert response.prompt_tokens==lengths[ids[index]]['tokens']
        assert response.completion_tokens==1 and response.cached_tokens is not None
        return asdict(response),seconds
    request_start=time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=4,thread_name_prefix='m3') as pool:
            iterator=iter(range(n));jobs={}
            for _ in range(min(4,n)):
                position=next(iterator);jobs[pool.submit(execute,position)]=position
            completed=0
            while jobs:
                done,_=wait(jobs,return_when=FIRST_COMPLETED)
                for future in done:
                    position=jobs.pop(future);response,seconds=future.result()
                    planned[position]=response['probabilities'];responses[position]=response;latencies[position]=seconds
                    completed+=1;meter.completed+=1
                    if completed%16==0 or completed==n:
                        save(run/'progress.json',{'utc':utc(),'completed':completed,'total':n,'seconds':time.perf_counter()-request_start})
                        print('M3_PROGRESS',run.name,completed,n,round(time.perf_counter()-request_start,2),flush=True)
                    position=next(iterator,None)
                    if position is not None:jobs[pool.submit(execute,position)]=position
        request_seconds=time.perf_counter()-request_start;t=time.perf_counter()
        restored,returned,latencies=restore_outputs(plan,ids,planned,responses,latencies)
        restore_seconds=time.perf_counter()-t;e2e=time.perf_counter()-start
    except BaseException as exc:
        save(run/'failure.json',{'utc':utc(),'type':type(exc).__name__,'message':str(exc),'completed':sum(v is not None for v in responses)})
        raise
    finally:b.close();sampler.close()
    barrier_after=meter.barrier();after=meter.snapshot(run/'metrics_after.prom')
    assert barrier_before.get('flushed') and barrier_after.get('flushed')
    output=[]
    for i in range(n):output.append({'record_id':ids[i],'original_position':i,'truth':bool(truth[i]),
         'predicted':bool(restored[i].argmax()),'probabilities':restored[i].tolist(),'client_latency_seconds':float(latencies[i]),
         **{k:v for k,v in returned[i].items() if k!='probabilities'}})
    with (run/'predictions.jsonl').open('x') as f:
        for row in output:f.write(json.dumps(row)+'\n')
    quality=classification([str(bool(v)) for v in truth],[str(r['predicted']) for r in output],['False','True'])
    prompt_tokens=sum(r['prompt_tokens'] for r in output);cached=sum(r['cached_tokens'] for r in output)
    completion=sum(r['completion_tokens'] for r in output)
    deltas={k:after.get(k,0)-before.get(k,0) for k in set(before)|set(after) if k.startswith('vllm:') and k.endswith('_total')}
    queries=deltas.get('vllm:prefix_cache_queries_total');hits=deltas.get('vllm:prefix_cache_hits_total')
    assert queries==prompt_tokens and hits==cached and deltas['vllm:request_success_total']==n
    performance={'end_to_end_seconds':e2e,'layout_and_validation_seconds':layout_seconds,'prepare_seconds':prepared_seconds,
       'planning_seconds':plan.planning_seconds,'request_phase_seconds':request_seconds,'restore_seconds':restore_seconds,
       'mean_latency_seconds':float(np.mean(latencies)),'p50_latency_seconds':float(np.percentile(latencies,50)),
       'p95_latency_seconds':float(np.percentile(latencies,95)),'requests_per_second':n/e2e,
       'total_prompt_tokens':prompt_tokens,'actual_cached_tokens':cached,'cache_hit_fraction':cached/prompt_tokens,
       'total_completion_tokens':completion,'input_tokens_per_second':prompt_tokens/e2e,'output_tokens_per_second':completion/e2e,
       'uncached_prompt_tokens':prompt_tokens-cached,'metrics_cache_queries':queries,'metrics_cache_hits':hits,
       'metrics_counter_deltas':deltas,'barrier_before':barrier_before,'barrier_after':barrier_after,
       'e2e_definition':'DataFrame normalization, actual plan, serialization/content/hash checks, bounded HTTP, ID/label/probability restoration; excludes service/warmup/explain/metrics waiting/quality/output persistence',
       'latency_definition':'Worker start to parsed/audited response; 4 in flight maximum; no unbounded submission queue'}
    save(run/'layout_plan.json',{'method':method,'columns':list(plan.columns),'ordered_columns':list(plan.ordered_columns),
         'row_order':plan.row_order.tolist(),'column_order':plan.column_order.tolist(),'plan_rows':plan.plan_rows})
    save(run/'explain.json',LayoutOptimizer(method,seed=42).explain(table,methods=[method]).to_dict())
    save(run/'performance.json',performance);save(run/'quality.json',quality)
    summary={'utc':utc(),'status':'passed','case':case,'method':method,'repeat':repeat,'n':n,'cache_salt':salt,
         'ids_restored_complete':True,'quality':quality,'performance':performance}
    save(run/'summary.json',summary);return summary
