import pathlib,struct,json
p=pathlib.Path('.tmp/vector-errors-testenv-20261014/.venv/Lib/site-packages/lancedb/_lancedb.pyd');raw=p.read_bytes();assert raw[:2]==b'MZ';o=struct.unpack_from('<I',raw,0x3c)[0];assert raw[o:o+4]==b'PE\0\0';n=struct.unpack_from('<H',raw,o+6)[0];opt=struct.unpack_from('<H',raw,o+20)[0];sections=[]
for i in range(n):
 q=o+24+opt+i*40;sections.append({'name':raw[q:q+8].rstrip(b'\0').decode('ascii',errors='replace'),'raw_size':struct.unpack_from('<I',raw,q+16)[0]})
r={'file':str(p),'sections':sections,'cargo_auditable_dep_v0_section_present':any(x['name']=='.dep-v0' for x in sections),'limitation':'No cargo-auditable metadata section is evidence for panic-string recovery fallback; dependency inventory not complete or feature reachability.'}
pathlib.Path('.tmp/vector-native-audit-20261014/tooling/pe-sections.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(r)
