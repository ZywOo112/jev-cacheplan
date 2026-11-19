"""Portable release contracts; no GPU or model weights are needed."""
import json
import os
import subprocess
import sys
from unittest.mock import patch
import numpy as np
import pytest
from project_runtime import ROOT, load_service_config
from evaluation.solo_reproduction import build_inputs, restore_outputs
from evaluation.telemetry import Meter
from benchmark import analyze
from service import memory_gate

def test_unicode_nested_duplicate_values_and_restore():
    rows = [{'record_id':'x','group':'共同','values':{'a':[1,'字']}},
            {'record_id':'y','group':'共同','values':{'a':[1,'字']}},
            {'record_id':'z','group':'另一','values':{'a':[3]}}]
    _, plan, states = build_inputs(rows,'solo')
    assert all(json.loads(s)==rows[int(i)] for i,s in zip(plan.row_order,states))
    matrix = np.array([[.1,.9],[.8,.2],[.3,.7]])
    result, responses, times = restore_outputs(plan,[r['record_id'] for r in rows],matrix[plan.row_order],
        [{'request_id':str(i)} for i in plan.row_order],np.array([1.,2.,3.])[plan.row_order])
    np.testing.assert_array_equal(result,matrix)
    assert [r['request_id'] for r in responses]==['0','1','2']
    np.testing.assert_array_equal(times,[1.,2.,3.])

def test_environment_model_port_gpu_overrides(monkeypatch,tmp_path):
    monkeypatch.setenv('JEV_MODEL_DIR',str(tmp_path/'model'))
    monkeypatch.setenv('JEV_PORT','18888')
    monkeypatch.setenv('JEV_GPU','1')
    config = load_service_config()
    assert config['model_dir']==str(tmp_path/'model') and config['port']==18888 and config['gpu_uuid']=='1'

def test_invalid_configuration_fails(monkeypatch):
    monkeypatch.setenv('JEV_PORT','0')
    with pytest.raises(ValueError): load_service_config()

def test_memory_gate_requires_safe_headroom():
    config={'gpu_uuid':'0','gpu_memory_utilization':.5,'selected_budget_mib':21000,'extra_free_headroom_mib':5120}
    with patch('service.subprocess.check_output',return_value='46000, 25000\n'):
        with pytest.raises(RuntimeError,match='headroom'): memory_gate(config)
    with patch('service.subprocess.check_output',return_value='46000, 30000\n'): memory_gate(config)

def test_metrics_sum_series_without_theoretical_cache_estimates():
    class Response:
        text = '# comment\nvllm:prefix_cache_hits_total{engine="0"} 5\nvllm:prefix_cache_hits_total{engine="1"} 7\nvllm:request_success_total 2\n'
        def raise_for_status(self): pass
    meter = Meter('http://127.0.0.1:1')
    try:
        with patch.object(meter.session,'get',return_value=Response()):
            result=meter.snapshot()
        assert result['vllm:prefix_cache_hits_total']==12 and result['vllm:request_success_total']==2
    finally: meter.session.close()

def test_published_metrics_recompute_both_reported_speedups():
    result=analyze()
    assert result['shared_970']['median_time_speedup']==pytest.approx(8.470945282176539)
    assert result['shared_983']['median_time_speedup']==pytest.approx(12.836734699125346)
    assert result['shared_800']['original']['n']==2 and result['shared_970']['original']['n']==3

@pytest.mark.parametrize('script,args',[
    ('cpu_example.py',[]), ('decide.py',['--compare','--plan-only']), ('benchmark.py',['analyze'])])
def test_cpu_readme_commands_from_unrelated_working_directory(script,args,tmp_path):
    result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),*args],cwd=tmp_path,
                          env=os.environ.copy(),capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()

def test_cacheplan_cli_alias_preserves_the_legacy_layout(tmp_path):
    def plan(*args):
        output = subprocess.check_output(
            [sys.executable, '-B', str(ROOT/'scripts/decide.py'), '--plan-only', *args],
            cwd=tmp_path, text=True, timeout=90)
        return [json.loads(line) for line in output.splitlines()]

    explicit = plan('--method', 'cacheplan')
    assert explicit == plan('--method', 'solo') == plan()
    assert explicit[0]['method'] == 'solo'
    assert explicit[0]['display_name'] == 'CachePlan'
    assert [item['display_name'] for item in plan('--compare')] == ['Original', 'CachePlan']

def test_cpu_example_has_public_names_and_no_inference(tmp_path):
    result=subprocess.check_output([sys.executable,'-B',str(ROOT/'scripts/cpu_example.py')],cwd=tmp_path,text=True,timeout=90)
    payload=json.loads(result)
    assert payload['offline_checks']=='passed' and payload['inference_executed'] is False
    assert list(payload['layouts'])==['Original','CachePlan']
    assert all(sorted(p['row_order'])==list(range(4)) for p in payload['layouts'].values())
