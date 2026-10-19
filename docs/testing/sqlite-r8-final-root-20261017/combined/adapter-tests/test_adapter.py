import sys, tempfile, unittest, math, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from vector_store import VectorStore
from sqlite_vector_payload import temporary_directory

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=temporary_directory(dir=Path(__file__).resolve().parents[1])
        directory=self.tmp.__enter__()
        self.s=VectorStore(persist_dir=directory)
    def tearDown(self): self.tmp.__exit__(None,None,None)
    def add(self,ids):
        self.s._collection.add(ids=ids,documents=ids,metadatas=[{'n':i} for i in range(len(ids))],embeddings=[[1.,0.]]*len(ids))
    def test_pages_snapshot_close(self):
        self.add(['z','a','m'])
        pages=self.s.iter_record_pages(page_size=1)
        self.assertEqual(next(pages)['ids'],['z'])
        self.s.delete_by_chunk_ids(['a'])
        self.add(['new'])
        self.assertEqual([x for p in pages for x in p['ids']],['a','m'])
        pages.close()
        self.assertEqual(self.s._collection.get()['ids'],['z','m','new'])
    def test_atomic_dimension_duplicates(self):
        self.add(['x'])
        with self.assertRaises(ValueError): self.s._collection.add(ids=['a','b'],embeddings=[[1.,0.],[1.,0.,0.]])
        self.assertEqual(self.s.count(),1)
        self.s._collection.add(ids=['x'],embeddings=[[0.,1.]],documents=['replacement'])
        self.assertEqual(self.s.get_by_ids(['x'])[0]['text'],'x')
    def test_zero_and_scale(self):
        self.s._collection.add(ids=['zero','unit'],embeddings=[[0.,0.],[1.,0.]])
        self.assertEqual([r['score'] for r in self.s.search([0.,0.])],[.5,.5])
        self.assertEqual(self.s.search([1.,0.])[0]['chunk_id'],'unit')
    def test_large_legal(self):
        self.add([str(i) for i in range(11001)])
        self.assertEqual(len(self.s.search([1.,0.],1001)),1001)
        other=self.s.create_migration_collection(4097)
        other._collection.add(ids=['wide'],embeddings=[[1.]*4097],documents=['a'*1048577])
        self.assertEqual(len(other.get_by_ids(['wide'])[0]['text']),1048577)
    def test_filter(self):
        self.add(['a','b','c'])
        self.assertEqual(self.s._collection.get(where={'n':{'$gt':0}})['ids'],['b','c'])
        self.assertEqual(self.s._collection.get(where={'absent':{'$ne':1}})['ids'],['a','b','c'])
        with self.assertRaises(ValueError): self.s.search([1.,0.],where={})
    def test_score_boundary(self):
        data=json.loads((Path(__file__).parent/'score-boundary.json').read_text())
        for row in data['score_mismatches']:
            s=self.s.create_migration_collection(2,suffix='_'+row['id'])
            s._collection.add(ids=['x'],embeddings=[row['vector']])
            self.assertEqual(s.search([1.,0.])[0]['score'],row['actual'])
    def test_hooks_and_last_invalid_atomic(self):
        class Hook:
            def __array__(self,*a,**k):raise AssertionError('hook ran')
            def __float__(self):raise AssertionError('hook ran')
        for vector in (Hook(),[Hook(),0.]):
            with self.assertRaises(ValueError):self.s._collection.add(ids=['x'],embeddings=[vector])
        with self.assertRaises(ValueError):self.s._collection.add(ids=['valid','bad'],embeddings=[[1.,0.],[float('nan'),0.]])
        self.assertEqual(self.s.count(),0)
        cycle={};cycle['self']=cycle
        with self.assertRaises(ValueError):self.s._collection.add(ids=['x'],embeddings=[[1.,0.]],metadatas=[cycle])
        self.assertEqual(self.s.count(),0)
    def test_early_close_and_storage_failure(self):
        self.add(['a','b']);pages=self.s.iter_record_pages(page_size=1)
        next(pages);pages.close()
        self.s.delete_by_source('missing')
        self.assertEqual(self.s.count(),2)
        self.s.path=Path(self.tmp.__class__.__name__)/'missing.sqlite'
        with self.assertRaises(Exception) as caught:self.s.count()
        self.assertEqual(caught.exception.code,'storage_unavailable')
    def test_filter_tree_and_negative_types(self):
        self.s._collection.add(ids=['bool','num','float','str','missing'],embeddings=[[1.,0.]]*5,metadatas=[{'a':True},{'a':1},{'a':1.5},{'a':'1'},{}])
        self.assertEqual(self.s._collection.get(where={'a':{'$eq':True}})['ids'],['bool'])
        self.assertEqual(self.s._collection.get(where={'a':{'$eq':1.5}})['ids'],['num','float'])
        self.assertEqual(self.s._collection.get(where={'$and':[{'a':{'$nin':[1]}},{'a':{'$ne':True}}]})['ids'],['float','str','missing'])
        w={'a':1}
        for _ in range(100):w={'$or':[w,{'none':True}]}
        self.assertEqual(self.s._collection.get(where=w)['ids'],['num'])
    def test_finite_overflow_query_separate_add(self):
        self.add(['a'])
        result=self.s.search([1e40,1.])
        self.assertTrue(math.isnan(result[0]['score']))
        with self.assertRaises(ValueError):self.s._collection.add(ids=['bad'],embeddings=[[1e40,1.]])
        self.assertEqual(self.s.count(),1)
    def test_backup_restore_hash_before_parse(self):
        self.add(['z','a'])
        snapshot=Path(self.s.persist_dir)/'snapshot.sqlite'
        identity=self.s.backup(snapshot)
        restored=VectorStore.restore(snapshot,Path(self.s.persist_dir)/'restored',**identity)
        self.assertEqual(restored._collection.get()['ids'],['z','a'])
        with self.assertRaises(ValueError):VectorStore.restore(snapshot,Path(self.s.persist_dir)/'bad',sha256='0'*64,size=identity['size'])

if __name__=='__main__':unittest.main()


