import sys, unittest, json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import vector_store as vs
import numpy as np
from contextlib import closing
from types import SimpleNamespace
from sqlite_vector_payload import temporary_directory

class Resources(unittest.TestCase):
    def test_all_201_chroma_rounding_boundaries(self):
        import math
        actual=json.loads((Path(__file__).parent/'chroma-135.json').read_text())['boundary']
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            for i in range(201):
                v=.1235+(i-100)*1e-10
                one=s.create_migration_collection(2,suffix=str(i))
                one._collection.add(ids=['x'],embeddings=[[v,math.sqrt(1-v*v)]])
                self.assertEqual(one.search([1.,0.])[0]['score'],actual[str(i)],i)
    def test_public_add_chunks_metadata_streams(self):
        values=['x'*20000]*100
        meta=SimpleNamespace(source_file='s',source_format='txt',page_idx=0,content_type='text',project_id='',token_count=1,entity_types=values,section_path=[],entity_ids=[],char_start=0,char_end=1)
        chunk=SimpleNamespace(chunk_id='x',text='body',content_type='text',metadata=meta)
        original=json.dumps
        def bounded(value,*a,**k):
            if type(value) is list:raise AssertionError('whole list encoding')
            if type(value) is str and len(value)>8192:raise AssertionError('whole string encoding')
            return original(value,*a,**k)
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            with patch.object(vs.json,'dumps',bounded):s.add_chunks([chunk],[[1.]])
            self.assertEqual(s.get_by_ids(['x'])[0]['metadata']['entity_types'],values)
    def test_invalid_outer_shape_before_hooks(self):
        class Hook:
            def __len__(self):raise AssertionError('unsafe length hook')
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            for kwargs in ({'embeddings':np.array(1.)}, {'embeddings':[[1.]],'documents':Hook()}, {'embeddings':[[1.]],'metadatas':Hook()}):
                with self.subTest(kwargs=tuple(kwargs)):
                    with self.assertRaises(vs.VectorInputError):s._collection.add(ids=['x'],**kwargs)
            self.assertEqual(s.count(),0)

    def test_string_encoder_bounded_and_roundtrip(self):
        text=('汉"\\\n'*100000)
        original=json.dumps;lengths=[]
        def observe(value,*a,**k):
            if isinstance(value,str):lengths.append(len(value))
            return original(value,*a,**k)
        with patch.object(vs.json,'dumps',observe):encoded=b''.join(vs.json_parts({'large':text,'n':3}))
        self.assertEqual(json.loads(encoded),{'large':text,'n':3})
        self.assertLessEqual(max(lengths),8192)

    def test_bytes_pages_and_oversize_single_row(self):
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            texts=['a'*(5*1024*1024),'b'*(5*1024*1024),'c'*(9*1024*1024),'tail']
            s._collection.add(ids=['a','b','c','d'],embeddings=[[1.]]*4,documents=texts)
            pages=list(s.iter_record_pages(page_size=256))
            self.assertEqual([p['ids'] for p in pages],[['a'],['b'],['c'],['d']])
            self.assertEqual([t for p in pages for t in p['documents']],texts)
            with closing(vs.connect(s.path,True)) as c:
                self.assertLessEqual(c.execute('SELECT max(length(data)) FROM payload').fetchone()[0],65536)
            self.assertEqual([r['chunk_id'] for r in s.search([1.],4)],['a','b','c','d'])

if __name__=='__main__':unittest.main()
