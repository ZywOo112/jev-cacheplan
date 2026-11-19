"""Check public claims against preserved measurements, not rounded report numbers."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import pytest
from project_runtime import ROOT

def test_presentation_numbers_recompute_from_full_precision_measurements():
    with (ROOT/'benchmarks/results/run_metrics.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==14 and sum(int(r['n']) for r in rows)==1792
    for case,expected,n in [('shared_800',2.06,2),('shared_970',8.47,3),('shared_983',12.84,2)]:
        groups={m:[r for r in rows if r['case']==case and r['method']==m] for m in ['original','solo']}
        assert all(len(g)==n for g in groups.values())
        ratio=statistics.median(float(r['end_to_end_seconds']) for r in groups['original'])/statistics.median(float(r['end_to_end_seconds']) for r in groups['solo'])
        assert round(ratio,2)==expected
    core=[r for r in rows if r['case']=='shared_970' and r['method']=='solo']
    assert all(int(r['actual_cached_tokens'])==1016928 and int(r['total_prompt_tokens'])==1136750 for r in core)
    assert round(1016928/1136750*100,2)==89.46
    assert all(float(r['accuracy'])==1 and r['ids_restored_complete']=='True' for r in rows)

def test_dataset_shape_class_balance_and_prompt_lengths():
    with (ROOT/'benchmarks/dataset_statistics.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==3
    expected={'shared_800':1401,'shared_970':8881,'shared_983':15611}
    for row in rows:
        assert int(row['rows'])==128 and int(row['fields'])==10 and int(row['seed'])==42
        assert int(row['positive_labels'])==int(row['negative_labels'])==64
        assert int(row['original_max_prompt_tokens'])==int(row['solo_max_prompt_tokens'])==expected[row['case']]

def test_two_real_decisions_and_paired_restoration_evidence():
    evidence=json.loads((ROOT/'docs/presentation_evidence.json').read_text())
    examples=evidence['real_decision_examples']
    assert [[round(e['original_p_true'],6),round(e['cacheplan_p_true'],6)] for e in examples]==[[.998853,.999429],[.000852,.000281]]
    assert all(e['original_predicted']==e['cacheplan_predicted'] for e in examples)
    assert sum(p['records'] for p in evidence['paired_prediction_checks'])==896
    assert all(p['prediction_agreement']==1 for p in evidence['paired_prediction_checks'])

def test_published_visuals_match_recorded_sources_and_safe_svg():
    meta=json.loads((ROOT/'assets/figure_sources.json').read_text())
    for figure in meta['figures']:
        p=ROOT/figure['file']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==figure['sha256']
        if p.suffix=='.svg':
            root=ET.fromstring(p.read_text())
            assert root.tag.endswith('svg')
            assert not any(e.tag.split('}')[-1] in ['script','foreignObject'] for e in root.iter())
