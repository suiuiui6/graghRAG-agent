import os,uuid,shutil
from pathlib import Path
import pytest
from vector_store import VectorStore
from doc_processor import Chunk
ROOT=Path(__file__).resolve().parent
os.environ['GRAPHRAG_RUNTIME_ARTIFACTS_DIR']=str(ROOT/'artifacts')
@pytest.mark.parametrize('entry',['rag','build','eval'])
def test_real_adapter_three_consumers(entry):
    path=ROOT/('db-'+uuid.uuid4().hex);path.mkdir()
    try:
        store=VectorStore(persist_dir=str(path))
        chunks=[Chunk(str(i),f'alpha beta item{i}','text') for i in range(137)]
        store.add_chunks(chunks,[[1.,0.]]*137)
        def forbidden(*a,**k):raise AssertionError('full get forbidden in candidate consumer')
        store._collection.get=forbidden
        if entry=='rag':
            from routes.rag_query import _build_bm25_index_from_vector_store
            result=_build_bm25_index_from_vector_store(store)
        elif entry=='build':
            from build_indices import build_indices
            result,_=build_indices(store)
        else:
            from run_evaluation import build_optional_indices
            result,_=build_optional_indices(store,bm25_index=None,table_index=None)
        assert [c.chunk_id for c in result[1]]==[str(i) for i in range(137)]
        assert result[1][-1].text=='alpha beta item136'
        assert len(result[0].get_scores(['alpha']))==137
    finally:shutil.rmtree(path)
