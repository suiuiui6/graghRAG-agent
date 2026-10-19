"""Verify installation against lock/RECORD and freeze bounded authored evidence."""
import base64
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import tomllib

root = Path(__file__).resolve().parent
evidence = root.parents[1]/"docs/testing/sqlite-numpy-r7-20261015"
lock = tomllib.loads((root/"uv.lock").read_text(encoding="utf-8"))
dependencies = {p["name"]:p["version"] for p in lock["package"] if "registry" in p["source"]}
installed = {d.metadata["Name"].lower():d.version for d in importlib.metadata.distributions()}
assert dependencies == installed == {"numpy":"2.5.4"}, (dependencies, installed)
wheel = next(w for p in lock["package"] if p["name"]=="numpy" for w in p["wheels"] if w["url"].endswith("cp312-cp312-win_amd64.whl"))
dist = importlib.metadata.distribution("numpy")
verified = 0
unhashed = []
for path, digest, size in csv.reader(dist.read_text("RECORD").splitlines()):
    file = Path(dist.locate_file(path)).resolve()
    assert file.is_relative_to(Path(sys.prefix).resolve()), path
    if not digest:
        unhashed.append(path)
        continue
    algorithm, expected = digest.split("=",1)
    assert algorithm=="sha256"
    content = file.read_bytes()
    assert str(len(content))==size, path
    assert base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")==expected,path
    verified+=1
identity = {"lock_registry_dependencies":dependencies,"actual_installed":installed,"selected_wheel":wheel,"record_sha256_verified_files":verified,"record_unhashed":unhashed,"wheel_bytes_retained":False,"wheel_hash_scope":"uv frozen sync validates official wheel against lock; this receipt also independently verifies installed hashed RECORD files, not an independently retained wheel ZIP hash"}
(evidence/"installation-binding.json").write_text(json.dumps(identity,indent=2),encoding="utf-8")
source = evidence/"source"
source.mkdir(exist_ok=True)
for p in root.iterdir():
    if p.is_file() and p.suffix in (".py",".toml",".lock"):
        shutil.copyfile(p, source/p.name)
manifest = {str(p.relative_to(evidence)).replace("\\","/"):{"size":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(evidence.rglob("*")) if p.is_file() and p.name not in ("manifest.json","freeze.json","freeze.stdout.log","freeze.stderr.log")}
(evidence/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps({"installed":installed,"record_verified":verified,"frozen_files":len(manifest),"selected_wheel_hash":wheel["hash"]}))
