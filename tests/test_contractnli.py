"""Meaningful invariants for official-data features, sidecar IDs and metrics."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from data.contractnli import OPTIONS,state,serialize,prompt,PROMPTS
from evaluation.classification import classification
from adapters.jev_adapter import LoggedBackend
from solo_layout import DecisionSpec,read_json
from solo_layout._table import as_table,Serializer
from project_runtime import ROOT

class ContractNLITests(unittest.TestCase):
    def test_gold_and_identity_are_never_features(self):
        record={'record_id':'secret-identity','gold_label':'Entailment','evidence_span_indices':[1,4],
                'contract_text':'条款\nNo disclosure.','hypothesis':'Disclosure is permitted.'}
        text=serialize(record)
        self.assertEqual(set(json.loads(text)),{'contract_text','hypothesis'})
        self.assertNotIn('secret-identity',text)
        table=as_table(read_json([state(record)]))
        self.assertEqual(text,Serializer(table,[0,1])(0))
        for question in PROMPTS.values():self.assertEqual(prompt(text,question),DecisionSpec.create(question,'choice',OPTIONS).prompt(text))
    def test_three_class_metrics_include_absent_predictions(self):
        m=classification(['a','b','c'],['a','a','c'],['a','b','c'])
        self.assertAlmostEqual(m['accuracy'],2/3)
        self.assertEqual(m['per_class']['b']['recall'],0)
        self.assertEqual(m['confusion_matrix'],[[1,0,0],[1,0,0],[0,0,1]])
    def test_sidecar_audit_identity_and_seed_do_not_change_prompt(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runtime/tmp') as d:
            path=Path(d)/'labelled_fixture.jsonl'
            b=LoggedBackend('http://127.0.0.1:1',model_dir=ROOT/'tests/fixtures/model_metadata',log_path=path,request_seed=0)
            spec=DecisionSpec.create('test','choice',OPTIONS);b.prepare(spec)
            start=b._head['slots']['ranges']['choice'][0];ids=b._head['verbalizer_ids'][start:start+3]
            class Response:
                status_code=200
                def raise_for_status(self):pass
                def json(self):return {'id':'labelled-unit-fixture','choices':[{'logprobs':{'top_logprobs':[{f'token_id:{i}':-j-1 for j,i in enumerate(ids)}]}}]}
            class Session:
                headers={}
                def post(self,url,*,json,timeout):
                    self.payload=json;return Response()
                def close(self):pass
            fake=Session()
            with patch('solo_layout.backend.requests.Session',return_value=fake):
                b.decide('{"contract_text":"NDA","hypothesis":"test"}',spec,audit_id='outside-id',cache_salt='fixture-only')
            self.assertEqual(fake.payload['seed'],0)
            self.assertNotIn('outside-id',fake.payload['prompt'])
            entries=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertTrue(all(e['record_id']=='outside-id' for e in entries))
            b.close()
if __name__=='__main__':unittest.main(verbosity=2)
