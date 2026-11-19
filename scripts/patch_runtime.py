"""Explicit optional version/source-guarded vLLM fix; run only with GPU environment Python."""
import os
import subprocess
import sys
import _bootstrap
from project_runtime import REPO, ROOT
from fetch_solo import verify

if __name__ == '__main__':
    verify()
    env = os.environ.copy()
    env['JEV_RUNTIME_DIR'] = str(ROOT/'runtime/service')
    subprocess.run([sys.executable, '-B', str(REPO/'deploy/fix_vllm_warmup.py')], env=env, check=True)
