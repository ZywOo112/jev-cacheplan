"""Read-only SHA256 checks of the fixed revision; never downloads weights."""
from pathlib import Path
import _bootstrap
from project_runtime import ROOT, REVISION, read, digest, load_service_config

def main():
    manifest=read(ROOT/'configs/model_files.json')
    if manifest['revision']!=REVISION: raise ValueError('Unexpected model revision')
    root=Path(load_service_config()['model_dir'])
    for entry in manifest['files']:
        file=root/entry['file']
        if file.stat().st_size!=entry['bytes'] or digest(file)!=entry['sha256']:
            raise RuntimeError('Model file differs from fixed revision: '+entry['file'])
    print('Fixed revision verified:', len(manifest['files']), 'files; no network used')

if __name__=='__main__':main()
