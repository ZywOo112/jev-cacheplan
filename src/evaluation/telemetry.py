"""Actual Prometheus snapshots and GPU resource sampling, extracted from the research runner."""
import json, os, re, subprocess, threading, time
from project_runtime import ROOT, read
import requests
class Meter:
    def __init__(self,base):
        self.base=base;self.session=requests.Session();self.session.trust_env=False;self.completed=0
    def snapshot(self,path=None):
        r=self.session.get(self.base+'/metrics',timeout=10);r.raise_for_status();text=r.text
        if path:path.write_text(text)
        values={}
        for line in text.splitlines():
            if not line or line[0]=='#':continue
            m=re.match(r'([^ {]+)(?:\{[^}]*\})?\s+([-+0-9.eE]+)(?:\s|$)',line)
            if m:
                try:values[m[1]]=values.get(m[1],0)+float(m[2])
                except ValueError:pass
        return values
    def barrier(self):
        started=time.monotonic()
        while True:
            values=self.snapshot();count=values.get('vllm:request_success_total')
            if count is None:return {'available':False,'reason':'No request_success counter'}
            if count>=self.completed:return {'available':True,'flushed':True,'expected':self.completed,'actual':count}
            if time.monotonic()-started>20:return {'available':True,'flushed':False,'expected':self.completed,'actual':count}
            time.sleep(.25)

class ResourceSampler:
    def __init__(self,run,config):self.run=run;self.config=config;self.stop=threading.Event()
    def start(self):
        self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start();return self
    def worker(self):
        tick=time.monotonic()
        while not self.stop.is_set():
            try:
                p=subprocess.run(['nvidia-smi','--id='+self.config['gpu_uuid'],'--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
                apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
                entries=[];own_group=None
                pid_record=ROOT/'runtime/service/server.json'
                if pid_record.exists():own_group=read(pid_record)['pgid']
                for line in apps.stdout.splitlines():
                    a=[v.strip() for v in line.split(',')]
                    if len(a)!=3 or a[1]!=self.config['gpu_uuid']:continue
                    try:owned=os.getpgid(int(a[0]))==own_group;memory=int(a[2])
                    except (OSError,ValueError):continue
                    entries.append({'pid':int(a[0]),'used_mib':memory,'owned_project_process':owned})
                a=[v.strip() for v in p.stdout.strip().split(',')]
                result={'utc':utc(),'elapsed_seconds':time.monotonic()-tick,'raw_gpu':p.stdout.strip(),'processes':entries}
                if len(a)==6:result.update(index=int(a[0]),name=a[1],total_mib=int(a[2]),used_mib=int(a[3]),free_mib=int(a[4]),utilization_pct=int(a[5]),
                                            other_process_mib=sum(v['used_mib'] for v in entries if not v['owned_project_process']))
                with (self.run/'resources.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
            except Exception as exc:
                with (self.run/'resources.jsonl').open('a') as f:f.write(json.dumps({'utc':utc(),'sampling_error':type(exc).__name__})+'\n')
            self.stop.wait(2)
    def close(self):self.stop.set();self.thread.join(timeout=12)
