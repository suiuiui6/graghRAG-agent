"""SQLite supplementary guard: fresh child, real tiny SQLite files only."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).parents[1] / 'research' / 'isolated_guard.py'


@pytest.mark.parametrize('database', ['outside', 'escape', 'uri', 'empty', 'fd', 'inside', 'memory'])
def test_sqlite_connect_boundary(tmp_path, database):
    assert MODULE.is_file(), 'SQLite guard v2 must exist'
    run = tmp_path / 'run'
    run.mkdir()
    outside = tmp_path / 'outside.db'
    manifest = {'status': 'verified', 'run_root': str(run),
                'python_executable': str(run / 'python' / 'python.exe')}
    script = '''import importlib.util,sys,json,sqlite3,os
spec=importlib.util.spec_from_file_location('guard',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
run,outside,kind=sys.argv[2:5]
database={'outside':outside, 'escape':os.path.join(run,'..','outside.db'),
          'uri':'file:'+outside+'?mode=rwc', 'empty':'', 'fd':1,
          'inside':os.path.join(run,'inside.db'), 'memory':':memory:'}[kind]
m.install_guard(run,json.loads(sys.argv[5]))
try:
 connection=sqlite3.connect(database,uri=kind=='uri')
 connection.execute('create table evidence (value integer)')
 connection.execute('insert into evidence values (42)')
 connection.commit()
 assert connection.execute('select value from evidence').fetchone()==(42,)
 connection.close()
except (PermissionError, ValueError, TypeError):
 assert kind not in ('inside','memory')
 print('BLOCKED')
else:
 assert kind in ('inside','memory'), 'outside SQLite connection was allowed'
 print('ALLOWED')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(MODULE),
                             str(run), str(outside), database, json.dumps(manifest)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ('ALLOWED' if database in ('inside', 'memory') else 'BLOCKED')
    assert not outside.exists()
    assert (run / 'inside.db').exists() == (database == 'inside')
