"""Portable paths and configuration; imports never create files or start a service."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
SHA = 'c5bed0511f3c90a83774f1a01e37da6b0b60fa22'
REVISION = 'b63f651ce8ed64481d3f5e73ecdb05f740042f01'
MODEL = 'autotrust/JEV-9B'

def root_path(value):
    p = Path(value).expanduser()
    return p if p.is_absolute() else ROOT / p

REPO = root_path(os.environ.get('SOLO_SOURCE_DIR', '.cache/solo-source'))
GPU_PYTHON = root_path(os.environ.get('JEV_GPU_PYTHON', '.venv-gpu/bin/python'))
CPU_PYTHON = Path(sys.executable)

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def load_service_config():
    config = read(root_path(os.environ.get('JEV_CONFIG', 'configs/service.example.json')))
    for env, key, cast in [('JEV_MODEL_DIR','model_dir',str), ('JEV_PORT','port',int),
                           ('JEV_GPU','gpu_uuid',str), ('JEV_MAX_MODEL_LEN','max_model_len',int),
                           ('JEV_MEMORY_UTILIZATION','gpu_memory_utilization',float)]:
        if env in os.environ: config[key] = cast(os.environ[env])
    if config['model_revision'] != REVISION: raise ValueError('Expected fixed JEV model revision')
    if config['host'] not in ('127.0.0.1', 'localhost', '::1'): raise ValueError('Service must bind to loopback')
    if not 1 <= config['port'] <= 65535: raise ValueError('Invalid port')
    if not 0 < config['gpu_memory_utilization'] < 1: raise ValueError('Invalid GPU memory fraction')
    if config['max_model_len'] < 2: raise ValueError('Invalid context length')
    config['model_dir'] = str(root_path(config['model_dir']))
    return config
