from contextlib import contextmanager
from pathlib import Path
import uuid,shutil
@contextmanager
def temporary_directory(dir):
    p=Path(dir)/('private-'+uuid.uuid4().hex)
    p.mkdir()
    try:yield str(p)
    finally:shutil.rmtree(p)
