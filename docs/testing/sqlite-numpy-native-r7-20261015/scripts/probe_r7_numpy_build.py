import hashlib,importlib.metadata,json,platform,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent.parent
out=root/'.tmp/sqlite-numpy-native-audit-20261015';out.mkdir(exist_ok=True)
site=Path(np.__file__).resolve().parent.parent
dist=importlib.metadata.distribution('numpy')
native=list((site/'numpy.libs').glob('*.dll'))
receipt={'python':platform.python_version(),'executable':sys.executable,'numpy':np.__version__,'numpy_path':np.__file__,'build_config':np.show_config(mode='dicts'),'dlls':{str(p.relative_to(site)):hashlib.sha256(p.read_bytes()).hexdigest() for p in native},'dist_metadata':{n:hashlib.sha256((Path(dist._path)/n).read_bytes()).hexdigest() for n in ['METADATA','WHEEL','RECORD','DELVEWHEEL'] if (Path(dist._path)/n).exists()},'sbom_files':[str(p) for p in Path(dist._path).rglob('*') if p.is_file() and ('sbom' in p.name.lower() or 'cyclonedx' in p.name.lower())],'scope':'Existing isolated NumPy wheel build identity; new R7 environment must match or be audited separately, not a zero-vulnerability proof'}
(out/'existing-numpy-build.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({'numpy':receipt['numpy'],'dll_count':len(native),'sbom_files':receipt['sbom_files'],'blas':receipt['build_config'].get('Build Dependencies',{}).get('blas')}))
