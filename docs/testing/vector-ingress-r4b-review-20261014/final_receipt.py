import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
repo=root.parents[1]
source=repo/'docs/testing/vector-ingress-r4b-20261014'
frozen=json.loads((source/'freeze-manifest.json').read_text())
assert all(hashlib.sha256((source/p).read_bytes()).hexdigest()==h for p,h in frozen['files'].items())
for name in ('generic_filter.py','parser_port.py'):
    assert (root/name).read_bytes()==(source/name).read_bytes()
truth=json.loads((root/'fresh-chroma.json').read_text())
candidate=json.loads((root/'fresh-lance.json').read_text())
assert truth['fixture_sha256']==candidate['fixture_sha256']
assert len(candidate['cases'])==128 and not candidate['differences']
assert candidate['raw_payload_verified'] and candidate['compat_readback_verified']
prior=repo/'docs/testing/vector-ingress-r4b-rootverify-20261014'
pm=json.loads((prior/'manifest.json').read_text())
assert all(hashlib.sha256((prior/p).read_bytes()).hexdigest()==h for p,h in pm['files'].items())
receipt={'utc':datetime.now(timezone.utc).isoformat(),'source_freeze_sha256':hashlib.sha256((source/'freeze-manifest.json').read_bytes()).hexdigest(),'frozen_files_verified_after_review':len(frozen['files']),'root_rerun_files_verified':len(pm['files']),'fresh_seed':202610141731,'fresh_conditions':128,'fresh_differences':0,'raw_payload_type_bits_verified':True,'compat_readback_type_bits_verified':True,'executions':[{'command':'.tmp/backend-quality-venv-20261012/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/fresh_matrix.py chroma','exit_code':0,'permission':'require_escalated'},{'command':'.tmp/vector-replacement-mvp-20261013/.venv/Scripts/python.exe .tmp/vector-ingress-r4b-review-20261014/fresh_matrix.py lance','exit_code':0,'permission':'require_escalated'}],'environment':{'PYTHON_DOTENV_DISABLED':'1','HF_HUB_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file() and p.name!='final-receipt.json'}}
(root/'final-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
