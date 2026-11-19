"""Offline layout/content/positional restoration checks. No model, HTTP, or download."""
import json
import numpy as np
import _bootstrap
from project_runtime import ROOT, read
from evaluation.solo_reproduction import build_inputs

def main():
    rows = read(ROOT / 'examples/sample_data.json')
    output = {}
    for method in ['original', 'solo']:
        _, plan, states = build_inputs(rows, method)
        original = np.arange(len(rows))
        assert np.array_equal(plan.restore(original[plan.row_order]), original)
        assert all(json.loads(s) == rows[int(i)] for s, i in zip(states, plan.row_order))
        output[method] = {'row_order': plan.row_order.tolist(), 'columns': list(plan.ordered_columns)}
    print(json.dumps({'offline_checks': 'passed', 'inference_executed': False, 'layouts': output}, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
