import json,pathlib,tempfile,unittest
from probe_store import ProbeStore
from vector_errors import VectorInputError
r=pathlib.Path(__file__).parent
class Facade(unittest.TestCase):
 def test_scores(self):
  rows=[{'id':x,'metadata':{'kind':x}} for x in ['same','orthogonal','opposite']]
  s=ProbeStore(tempfile.mkdtemp(prefix='facade-',dir=r),rows,[[1.,0.,0.],[0.,1.,0.],[-1.,0.,0.]])
  got=s.search([1.,0.,0.],top_k=3)
  self.assertEqual([(x['chunk_id'],x['score']) for x in got],[('same',1.),('orthogonal',.5),('opposite',0.)])
  self.assertEqual([(x['chunk_id'],x['score']) for x in s.search([1.,0.,0.],top_k=1,where={'kind':'opposite'})],[('opposite',0.)])
 def test_huge_vector(self):
  s=ProbeStore(tempfile.mkdtemp(prefix='facade-',dir=r),[{'id':'a','metadata':{}}])
  with self.assertRaises(VectorInputError) as e:s.search([10**309,0,0])
  self.assertEqual(e.exception.code,'invalid_input')
if __name__=='__main__':unittest.main(verbosity=2)
