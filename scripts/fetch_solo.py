"""Explicitly fetch optional pinned author generator/service sources, never models."""
import subprocess
import _bootstrap
from project_runtime import REPO, SHA

def verify():
    head = subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'], text=True).strip()
    if head != SHA: raise RuntimeError('SOLO source checkout is not the fixed commit')
    if subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'], text=True).strip():
        raise RuntimeError('SOLO checkout has changes; refusing to use modified third-party sources')

def main():
    if REPO.exists():
        verify(); print('Pinned SOLO source verified'); return
    REPO.mkdir(parents=True)
    env = __import__('os').environ.copy()
    env['GIT_LFS_SKIP_SMUDGE'] = '1'
    for argv in [['git','init',str(REPO)], ['git','-C',str(REPO),'remote','add','origin','https://github.com/0814wdwd/solo_jev.git'],
                 ['git','-C',str(REPO),'fetch','--depth=1','origin',SHA], ['git','-C',str(REPO),'checkout','--detach','FETCH_HEAD']]:
        subprocess.run(argv, check=True, env=env, timeout=120)
    verify(); print('Pinned SOLO author source fetched; no model downloaded')

if __name__ == '__main__': main()
