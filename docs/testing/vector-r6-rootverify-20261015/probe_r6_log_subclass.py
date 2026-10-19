import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'.tmp/vector-r6-20261014'))
from vector_errors import VectorStorageError
from safe_vector_logging import processor
class SubStorage(VectorStorageError):pass
marker='R6_ROOT_SYNTHETIC_SUBCLASS_MARKER'
e=SubStorage('storage_unavailable','search')
e.__cause__=RuntimeError(marker)
event={'event':marker,'error':marker,'exc_info':(type(e),e,None)}
out=processor(None,'error',event)
safe='exc_info' not in out and marker not in json.dumps(out,default=lambda _: 'NON_JSON_OBJECT')
receipt={'typed_subclass_sanitized':safe,'candidate_event_passthrough':out is event,'scope':'pure processor probe, not console/file test'}
dest=root/'.tmp/vector-r6-rootverify-20261015';dest.mkdir(exist_ok=True)
(dest/'subclass-precheck.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
raise SystemExit(0 if safe else 1)
