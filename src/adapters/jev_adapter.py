"""Existing audited JEV backend; compatibility exports preserve its public API."""
from dataclasses import asdict
import hashlib, json, threading, time
import numpy as np
import requests
from solo_layout import JevBackend
from layout.validation import validate_distribution, validate_plan
from layout.execution import execute_plan

class LoggedBackend(JevBackend):
    def __init__(self,*args,log_path,max_retries=1,request_seed=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.log_path=log_path
        self.max_retries=max_retries
        self.request_seed=request_seed
        self._audit_lock=threading.Lock()
        self._audit_context=threading.local()

    def emit(self,entry):
        with self._audit_lock:
            with self.log_path.open("a") as f:
                f.write(json.dumps(entry,ensure_ascii=False,allow_nan=False)+"\n")

    def _session(self):
        underlying=super()._session()
        parent=self
        class AuditedSession:
            def post(self,url,*,json,timeout):
                if parent.request_seed is not None:json={**json,"seed":parent.request_seed}
                for attempt in range(parent.max_retries+1):
                    started=time.perf_counter()
                    entry={"event":"http","record_id":getattr(parent._audit_context,"record_id",None),
                           "state":getattr(parent._audit_context,"state",None),
                           "attempt":attempt+1,"url":url,"payload":json}
                    try:
                        response=underlying.post(url,json=json,timeout=timeout)
                        entry.update(http_status=response.status_code,seconds=time.perf_counter()-started)
                        try: entry["raw_response"]=response.json()
                        except ValueError: entry["raw_response_text"]=response.text[:20000]
                        parent.emit(entry)
                        if response.status_code not in {429,502,503,504} or attempt==parent.max_retries:
                            return response
                    except (requests.ConnectionError,requests.Timeout) as exc:
                        entry.update(exception_type=type(exc).__name__,seconds=time.perf_counter()-started)
                        parent.emit(entry)
                        if attempt==parent.max_retries: raise
                    time.sleep(0.2*(2**attempt))
        return AuditedSession()

    def decide(self,state,spec,*,cache_salt=None,audit_id=None):
        values=json.loads(state)
        record_id=audit_id if audit_id is not None else values.get("record_id")
        self._audit_context.record_id=record_id
        self._audit_context.state=state
        try:
            response=super().decide(state,spec,cache_salt=cache_salt)
            validate_distribution(response.probabilities,spec.options)
            self.emit({"event":"parsed","record_id":record_id,
                       "kind":spec.kind,"options":list(spec.options),
                       "response":asdict(response),"cache_salt":cache_salt,
                       "state_sha256":hashlib.sha256(state.encode()).hexdigest()})
            return response
        except Exception as exc:
            self.emit({"event":"parse_or_request_error","record_id":record_id,
                       "exception_type":type(exc).__name__,"message":str(exc)[:500]})
            raise
