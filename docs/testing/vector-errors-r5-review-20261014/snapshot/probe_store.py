"""Isolated static-generation facade, NOT complete VectorStore adapter."""
import json, math
import lancedb
from generic_filter import StaticProjection
from vector_errors import VectorStoreError,VectorInputError,VectorStorageError

def boundary(operation, fn):
    try:return fn()
    except VectorStoreError:raise
    except Exception as exc:raise VectorStorageError('storage_unavailable',operation) from exc

def validate_vector(vector, operation):
    if not isinstance(vector,(list,tuple)) or len(vector)!=3:raise VectorInputError('invalid_dimension',operation)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):raise VectorInputError('invalid_input',operation)
    return vector

class ProbeStore:
    def __init__(self,path,records,vectors=None):
        self.search_calls=0
        self.projection=StaticProjection(records)
        vectors=[[1.,0.,0.] for _ in records] if vectors is None else vectors
        if len(records)!=len(vectors):raise VectorInputError('invalid_input','open',length_mismatch=True)
        for vector in vectors:validate_vector(vector,'open')
        encoded=[self.projection.encode(record,vector) for record,vector in zip(records,vectors)]
        def create():
            self.db=lancedb.connect(path)
            self.table=self.db.create_table('probe',data=encoded,schema=self.projection.schema)
        boundary('open',create)
    def encode(self,record,vector=None):
        if vector is not None:validate_vector(vector,'encode')
        return self.projection.encode(record,vector)
    def search(self,query_vector,top_k=10,where=None,**kwargs):
        self.search_calls+=1
        validate_vector(query_vector,'search')
        if type(top_k) is not int or top_k<=0:raise VectorInputError('invalid_input','search')
        expr=None if where is None else self.projection.compile(where)
        def execute():
            query=self.table.search(query_vector).distance_type('cosine')
            if expr is not None:query=query.where(expr,prefilter=True)
            rows=query.limit(top_k).to_list()
            return [dict(chunk_id=row['id'],text='',metadata=json.loads(row['compat_metadata_json']),score=1.-row['_distance']) for row in rows]
        return boundary('search',execute)
    def read(self,where):
        expr=self.projection.compile(where)
        return boundary('read',lambda:self.table.search().where(expr).limit(10000).to_list())
    def count(self):return boundary('count',self.table.count_rows)
    def scan(self):return boundary('scan',lambda:self.table.search().limit(10000).to_list())
