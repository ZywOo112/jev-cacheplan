"""Existing external-plan execution and positional restoration."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import numpy as np
from solo_layout import DecisionSpec
from solo_layout._table import as_table, Serializer
from .validation import validate_plan, validate_distribution

def execute_plan(data,question,plan,backend,*,kind="noul",options=None,concurrency=2,cache_salt=None):
    if concurrency<1 or concurrency>2:
        raise ValueError("Functional adapter limits concurrency to 1 or 2")
    table=as_table(data)
    n=len(table)
    validate_plan(plan,n,table.columns)
    spec=DecisionSpec.create(question,kind,options)
    serializer=Serializer(table,plan.column_order)
    states=[serializer(int(i)) for i in plan.row_order]
    ids=[json.loads(state)["record_id"] for state in states]
    if len(set(ids))!=n or any(not isinstance(i,str) or not i for i in ids):
        raise ValueError("Every record must have one unique nonempty ID")
    planned=np.empty((n,len(spec.options)),dtype=float)
    completed=np.zeros(n,dtype=bool)
    backend.prepare(spec)
    with ThreadPoolExecutor(max_workers=concurrency,thread_name_prefix="layout-plan") as pool:
        jobs={pool.submit(backend.decide,state,spec,cache_salt=cache_salt):pos
              for pos,state in enumerate(states)}
        for future in as_completed(jobs):
            pos=jobs[future]
            response=future.result()
            planned[pos]=validate_distribution(response.probabilities,spec.options)
            completed[pos]=True
    if not completed.all():
        raise RuntimeError("Incomplete batch; never fabricate failed decisions")
    restored=plan.restore(planned)
    restored_ids=plan.restore(np.asarray(ids,dtype=object)).tolist()
    source_ids=[json.loads(Serializer(table,range(len(table.columns)))(i))["record_id"] for i in range(n)]
    if restored_ids!=source_ids:
        raise RuntimeError("Input/output ID alignment failed")
    return {"planned_ids":ids,"restored_ids":restored_ids,
            "row_order":plan.row_order.tolist(),"column_order":plan.column_order.tolist(),
            "planned_probabilities":planned.tolist(),"probabilities":restored.tolist(),
            "decisions":np.asarray(spec.options)[restored.argmax(axis=1)].tolist()}
