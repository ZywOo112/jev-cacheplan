"""Official ContractNLI records and the locked, ID-free decision input schema."""
import json
from pathlib import Path

OPTIONS=('Entailment','Contradiction','NotMentioned')
FIELDS=('contract_text','hypothesis')
PROMPTS={
 'concise': 'Given the complete NDA contract and the hypothesis, classify their relationship. Choose Entailment if the contract supports the hypothesis, Contradiction if the contract states the opposite, or NotMentioned if neither is established. Use only the contract; do not infer missing terms from general knowledge.',
 'explicit': 'You are assessing a hypothesis about the supplied complete non-disclosure agreement (NDA). Choose exactly one relationship: Entailment means the NDA explicitly or necessarily supports the hypothesis; Contradiction means it supports an incompatible statement or the negation of the hypothesis; NotMentioned means the NDA establishes neither the hypothesis nor its negation. Read relevant exceptions and conditions. Absence of a clause is NotMentioned, not Contradiction. Base the decision only on this NDA, not customary practices or outside knowledge.'}

def load_records(path):
    with Path(path).open() as stream:return [json.loads(line) for line in stream if line.strip()]

def state(record):
    result={field:record[field] for field in FIELDS}
    if any(not isinstance(v,str) or not v.strip() for v in result.values()):raise ValueError('Empty model text')
    return result

def serialize(record,order=FIELDS):
    values=state(record)
    if sorted(order)!=sorted(FIELDS):raise ValueError('Invalid model feature schema')
    return json.dumps({k:values[k] for k in order},ensure_ascii=False,separators=(',',':'),allow_nan=False)

def prompt(text,question):
    # Verified against the fixed upstream DecisionSpec.prompt in preparation/tests.
    return f'[kind] choice\n[state] {text}\n[question] {question}\n[options]\nA) Entailment\nB) Contradiction\nC) NotMentioned\n[decision]:'
