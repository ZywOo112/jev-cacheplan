"""CPU suite: forbid real HTTP and put every cache/temp under the release checkout."""
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    def denied(*args, **kwargs):
        raise AssertionError('CPU tests must use explicit fake backends, never real HTTP')
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)
    (ROOT/'runtime/tmp').mkdir(parents=True, exist_ok=True)
