"""Existing layout and probability guards, relocated without algorithm changes."""
import numpy as np

def validate_distribution(p, options):
    p=np.asarray(p,dtype=float)
    if p.shape!=(len(options),) or not np.isfinite(p).all() or (p<0).any() or not np.isclose(p.sum(),1,atol=1e-6,rtol=0):
        raise ValueError("Invalid decision probability distribution")
    return p

def validate_plan(plan,n,columns):
    if tuple(plan.columns)!=tuple(columns):
        raise ValueError("Plan and input schema differ")
    for values,size in [(plan.row_order,n),(plan.column_order,len(columns))]:
        a=np.asarray(values)
        if a.ndim!=1 or a.dtype.kind not in "iu" or len(a)!=size or sorted(a.tolist())!=list(range(size)):
            raise ValueError("Plan must contain canonical row/column permutations")
