import hashlib,json,pathlib,shutil
repo=pathlib.Path(__file__).resolve().parents[2];out=pathlib.Path(__file__).resolve().parent
folder=repo/'docs/testing/vector-r6-20261014';mp=folder/'r6-freeze-manifest.json';m=json.loads(mp.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(mp)=='37a4ca29ce343e1621235b1bb8fdbee52beb120b67134fc3b32d1e6c1d1fbac5'
bad=[name for name,h in m['files'].items() if sha(folder/name)!=h]
inputs_bad=[name for name,h in m['validated_inputs'].items() if sha(repo/name)!=h]
assert not bad and not inputs_bad
dest=out/'frozen';dest.mkdir(exist_ok=True)
for name,h in m['files'].items():
 target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,target);assert sha(target)==h
receipt={'manifest_sha256':sha(mp),'files':len(m['files']),'validated_inputs':len(m['validated_inputs']),'drift':bad,'input_drift':inputs_bad,'private_copy':str(dest),'private_copy_drift':[]}
(out/'freeze-check.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
