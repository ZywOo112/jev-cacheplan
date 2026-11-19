"""Portable wrapper over the fixed SOLO PID/start-tick ownership controller."""
import argparse
import os
import socket
import subprocess
import sys
import _bootstrap
from project_runtime import ROOT, REPO, GPU_PYTHON, load_service_config
from fetch_solo import verify

def memory_gate(config):
    row = subprocess.check_output(['nvidia-smi', '--id='+config['gpu_uuid'],
          '--query-gpu=memory.total,memory.free', '--format=csv,noheader,nounits'], text=True, timeout=10)
    total, free = [int(x.strip()) for x in row.strip().split(',')]
    needed = max(config['selected_budget_mib'], int(total*config['gpu_memory_utilization']))
    if free < needed + config['extra_free_headroom_mib']:
        raise RuntimeError('Insufficient free GPU memory for budget plus headroom; do not stop other jobs')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start','stop','status'])
    args = parser.parse_args()
    verify()
    config = load_service_config()
    if args.action == 'start':
        memory_gate(config)
        # Refuse even a non-JEV process on this port before launching any child.
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', config['port'])) == 0:
                raise RuntimeError('Port is already occupied; inspect ownership/status or choose JEV_PORT')
    env = os.environ.copy()
    env.update({'JEV_VENV':str(GPU_PYTHON.parent.parent), 'JEV_MODEL_DIR':config['model_dir'],
        'JEV_RUNTIME_DIR':str(ROOT/'runtime/service'), 'JEV_HOST':config['host'], 'JEV_PORT':str(config['port']),
        'JEV_MAX_MODEL_LEN':str(config['max_model_len']), 'JEV_MAX_NUM_SEQS':str(config['max_num_seqs']),
        'JEV_BATCH_TOKENS':str(config['max_num_batched_tokens']), 'JEV_GPU_MEMORY_UTILIZATION':str(config['gpu_memory_utilization']),
        'JEV_PREFIX_CACHING':'1' if config['enable_prefix_caching'] else '0',
        'JEV_PER_REQUEST_METRICS':'1' if config['per_request_metrics'] else '0', 'JEV_EAGER':'1',
        'JEV_START_TIMEOUT':'900', 'CUDA_VISIBLE_DEVICES':config['gpu_uuid'], 'CUDA_DEVICE_ORDER':'PCI_BUS_ID',
        'HF_HUB_OFFLINE':'1', 'TRANSFORMERS_OFFLINE':'1', 'PYTHONDONTWRITEBYTECODE':'1',
        'HF_HOME':str(ROOT/'.cache/huggingface'), 'VLLM_CACHE_ROOT':str(ROOT/'.cache/vllm')})
    result = subprocess.run([sys.executable,'-B',str(REPO/'deploy/control.py'),args.action], env=env)
    raise SystemExit(result.returncode)

if __name__ == '__main__': main()
