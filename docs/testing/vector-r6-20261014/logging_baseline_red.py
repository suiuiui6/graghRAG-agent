"""Baseline R5/production processor chain, before adding candidate processor."""
import contextlib,io,json,pathlib,tempfile
import structlog
from vector_errors import VectorStorageError
r=pathlib.Path(__file__).resolve().parent
ns={'__name__':'baseline_logging'};p=r/'current-consumer/logging_config.py';exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),ns)
directory=pathlib.Path(tempfile.mkdtemp(dir=r));output=io.StringIO()
with contextlib.redirect_stderr(output):ns['setup_logging'](str(directory))
mark='R6_BARE_PRIVATE_BASELINE_19452'
try:
 try:raise ValueError(mark)
 except ValueError as exc:raise VectorStorageError('storage_unavailable','search') from exc
except VectorStorageError:ns['get_logger']('baseline').error('storage_failed',exc_info=True)
text=(directory/'app.log').read_text(encoding='utf-8')
(r/'baseline-red-output.log').write_text(text,encoding='utf-8')
assert mark not in text, 'baseline leaks bare synthetic marker'
