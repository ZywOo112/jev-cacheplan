"""Project-adapter tests using explicit in-memory fixtures, never model results."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from solo_layout import DecisionResponse, DecisionSpec, LayoutPlan, read_json
from adapters.jev_adapter import LoggedBackend, execute_plan, validate_distribution
from project_runtime import ROOT

class FakeResponse:
    def __init__(self,status,body):
        self.status_code=status; self.body=body
    def json(self): return self.body
    def raise_for_status(self):
        if self.status_code>=400: raise RuntimeError("synthetic HTTP error")

class FakeSession:
    def __init__(self,responses):
        self.responses=iter(responses); self.calls=0; self.headers={}
    def post(self,*args,**kwargs):
        self.calls+=1; return next(self.responses)
    def close(self): pass

class AdapterTests(unittest.TestCase):
    def backend(self,path):
        return LoggedBackend("http://127.0.0.1:1",model_dir=ROOT/"tests/fixtures/model_metadata",
                             log_path=path,max_retries=1)
    def valid_body(self,b):
        spec=DecisionSpec.create("test")
        b.prepare(spec)
        ids=b._head["verbalizer_ids"][:2]
        return {"id":"cmpl-labelled-unit-fixture",
                "choices":[{"logprobs":{"top_logprobs":[{f"token_id:{i}":float(-j-1) for j,i in enumerate(ids)}]}}]}
    def test_bounded_503_retry_and_audit(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"runtime/tmp") as d:
            path=Path(d)/"labelled_synthetic.jsonl"; b=self.backend(path)
            fake=FakeSession([FakeResponse(503,{"error":"synthetic temporary error"}),
                              FakeResponse(200,self.valid_body(b))])
            with patch("solo_layout.backend.requests.Session",return_value=fake),patch("adapters.jev_adapter.time.sleep"):
                result=b.decide('{"record_id":"unit-retry"}',DecisionSpec.create("test"))
            self.assertEqual(fake.calls,2)
            self.assertAlmostEqual(sum(result.probabilities),1)
            events=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual([e["http_status"] for e in events if e["event"]=="http"],[503,200])
            b.close()
    def test_missing_logprobs_raises_without_false_decision(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"runtime/tmp") as d:
            path=Path(d)/"labelled_malformed.jsonl"; b=self.backend(path)
            fake=FakeSession([FakeResponse(200,{"choices":[{"logprobs":{"top_logprobs":[{}]}}]})])
            with patch("solo_layout.backend.requests.Session",return_value=fake):
                with self.assertRaisesRegex(RuntimeError,"required decision-token"):
                    b.decide('{"record_id":"unit-malformed"}',DecisionSpec.create("test"))
            self.assertEqual(fake.calls,1)
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["event"],"parse_or_request_error")
            b.close()
    def test_probability_guard_rejects_bad_responses(self):
        for values in [(-1,2),(.2,.2),(float("nan"),1),(1,)]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                validate_distribution(values,[False,True])
    def test_external_plan_restores_actual_backend_responses(self):
        source=read_json([{"record_id":"a","context":"shared","value":1},
                          {"record_id":"b","context":"shared","value":2},
                          {"record_id":"c","context":"shared","value":3}])
        plan=LayoutPlan("unit",np.array([2,0,1]),np.array([1,0,2]),
                        ("record_id","context","value"),0.0,3)
        class Backend:
            def prepare(self,spec): pass
            def decide(self,state,spec,**kwargs):
                row=json.loads(state)
                return DecisionResponse((.1,.9) if row["value"]>1 else (.9,.1))
        result=execute_plan(source,"value exceeds one?",plan,Backend())
        self.assertEqual(result["planned_ids"],["c","a","b"])
        self.assertEqual(result["restored_ids"],["a","b","c"])
        self.assertEqual(result["decisions"],[False,True,True])
    def test_invalid_plan_rejected_before_backend_access(self):
        source=read_json([{"record_id":"a"},{"record_id":"b"}])
        plan=LayoutPlan("unit",np.array([0,0]),np.array([0]),("record_id",),0.0,2)
        class NoRequests:
            def prepare(self,*args): raise AssertionError("Must not prepare invalid plan")
        with self.assertRaises(ValueError):
            execute_plan(source,"test",plan,NoRequests())

if __name__=="__main__":
    unittest.main(verbosity=2)
