import hashlib,importlib.metadata as md,json,pathlib,sys
r=pathlib.Path(__file__).resolve().parent; repo=r.parents[1]
packages={d.metadata['Name']:d.version for d in md.distributions()}
paths={name:__import__(name).__file__ for name in ['lancedb','pyarrow','structlog']}
(r/'r5-environment.json').write_text(json.dumps({'python':sys.version,'executable':sys.executable,'packages':packages,'module_paths':paths,'locks':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [repo/'.tmp/vector-replacement-mvp-20261013/uv.lock',repo/'.tmp/vector-errors-testenv-20261014/uv.lock',repo/'backend/uv.lock']},'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in r.glob('*.py')}},indent=2))
