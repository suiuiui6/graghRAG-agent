import sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace as S
r=Path(__file__).parent;sys.path.insert(0,str(r/'candidate'))
from vector_store import VectorStore,_build_chroma_metadata,_parse_chroma_metadata
meta=S(source_file=None,source_format=None,page_idx=None,content_type=None,project_id=None,token_count=1,entity_types=['人物','a"b'],section_path=['章节',None],entity_ids=['id1','id2'],char_start=None,char_end=None)
chunks=[S(chunk_id='none',text='null metadata',content_type='text',metadata=None),S(chunk_id='lists',text='JSON metadata',content_type='text',metadata=meta)]
s=VectorStore('public-test',str(r/'public-db'));s.add_chunks(chunks,[[1.,0.]]*2)
actual={x['chunk_id']:x for x in s.get_by_ids(['none','lists'])}
expected={c.chunk_id:dict(chunk_id=c.chunk_id,text=c.text,metadata=_parse_chroma_metadata({k:'' if v is None else v for k,v in _build_chroma_metadata(c).items()})) for c in chunks}
assert actual==expected,(actual,expected)
(r/'public.json').write_text(json.dumps(dict(actual=actual,expected=expected),ensure_ascii=False,indent=2));print('2 public metadata roundtrips pass')
