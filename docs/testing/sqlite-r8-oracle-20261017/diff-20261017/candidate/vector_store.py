"""SQLite snapshot adapter. Private R8 candidate; not a production switch."""
from __future__ import annotations
import json, math, sqlite3, heapq, tempfile, pickle, functools, hashlib, hmac
from contextlib import closing
from pathlib import Path
import numpy as np
from vector_errors import VectorStoreError, VectorInputError, VectorStorageError
from parser_port import parse
from sqlite_vector_payload import temporary_directory

DEFAULT_COLLECTION='rag_docs'
DEFAULT_DIM=512
VECTORDB_DIR=str(Path(__file__).parent/'output'/'vectordb')


def boundary(operation):
    def decorate(fn):
        @functools.wraps(fn)
        def call(*a,**kw):
            try:return fn(*a,**kw)
            except VectorStoreError:raise
            except Exception as exc:raise VectorStorageError('storage_unavailable',operation) from exc
        return call
    return decorate


def fail(code='invalid_input',op='encode'):raise VectorInputError(code,op)


def ingress(v, query=False):
    if type(v) not in (int,float):return v
    try:
        if not query and type(v) is int and not -(2**63)<=v<2**63:v=float(v)
        tag,value=parse(json.dumps(v))
        if query and tag=='u64' and value>=2**63:fail('invalid_filter','compile')
        return 0.0 if not query and type(value) is float and value==0 else value
    except (ValueError,OverflowError) as exc:raise VectorInputError('invalid_filter' if query else 'invalid_input','compile' if query else 'encode') from exc


def compile_where(where):
    if where is None:return lambda m:True
    stack=[(where,False)]; result=[]; active=set()
    while stack:
        node,done=stack.pop()
        if done:
            active.remove(id(node)); key,value=next(iter(node.items())); count=len(value)
            children=result[-count:];del result[-count:]
            result.append((key,children));continue
        if type(node) is not dict or len(node)!=1:fail('invalid_filter','compile')
        key,value=next(iter(node.items()))
        if type(key) is not str:fail('invalid_filter','compile')
        if key in ('$and','$or'):
            if type(value) is not list or len(value)<2 or id(node) in active:fail('invalid_filter','compile')
            active.add(id(node));stack.append((node,True));stack.extend((x,False) for x in reversed(value));continue
        if key.startswith('$'):fail('invalid_filter','compile')
        if type(value) is not dict:value={'$eq':value}
        if len(value)!=1:fail('invalid_filter','compile')
        op,arg=next(iter(value.items()))
        if op not in ('$eq','$ne','$gt','$gte','$lt','$lte','$in','$nin'):fail('invalid_filter','compile')
        args=arg if op in ('$in','$nin') else [arg]
        if type(args) is not list or not args or any(type(x) is not type(args[0]) for x in args):fail('invalid_filter','compile')
        if type(args[0]) not in (str,bool,int,float):fail('invalid_filter','compile')
        if op in ('$gt','$gte','$lt','$lte') and type(arg) not in (int,float):fail('invalid_filter','compile')
        if op in ('$in','$nin') and type(args[0]) in (int,float):
            try:values=[parse(json.dumps(x)) for x in args]
            except (ValueError,OverflowError) as exc:raise VectorInputError('invalid_filter','compile') from exc
            if values[0][0]=='f64':args=[float(v) for _,v in values]
            else:
                if any(t=='f64' or v>=2**63 for t,v in values):fail('invalid_filter','compile')
                args=[v for _,v in values]
        else:args=[ingress(x,True) for x in args]
        result.append(('leaf',key,op,args))
    tree=result[0]
    def match(meta):
        todo=[(tree,False)];values=[]
        while todo:
            node,done=todo.pop()
            if node[0]!='leaf':
                if not done:todo.append((node,True));todo.extend((x,False) for x in reversed(node[1]));continue
                n=len(node[1]);xs=values[-n:];del values[-n:];values.append(all(xs) if node[0]=='$and' else any(xs));continue
            _,key,op,args=node
            def scalar(q):
                negative=op in ('$ne','$nin')
                if key not in meta:return negative
                stored=meta[key]
                if type(q) in (int,float):
                    if type(stored) not in (int,float):return negative
                    q=min(2**63-1,max(-(2**63),math.trunc(q))) if type(stored) is int else float(q)
                elif type(stored) is not type(q):return negative
                if op in ('$eq','$in'):return stored==q
                if negative:return stored!=q
                if op=='$gt':return stored>q
                if op=='$gte':return stored>=q
                if op=='$lt':return stored<q
                return stored<=q
            values.append(all(scalar(q) for q in args) if op=='$nin' else any(scalar(q) for q in args))
        return values[0]
    return match


def connect(path,ro=False):
    c=sqlite3.connect(Path(path).resolve().as_uri()+('?mode=ro' if ro else '?mode=rwc'),uri=True,timeout=.5)
    try:
        if sqlite3.sqlite_version_info<(3,53,2):raise RuntimeError('SQLite安全版本不足')
        for option,value in ((sqlite3.SQLITE_DBCONFIG_DEFENSIVE,True),(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA,False),(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION,False)):
            c.setconfig(option,value)
            if c.getconfig(option)!=value:raise RuntimeError('连接硬化失败')
        c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA trusted_schema=OFF')
        return c
    except BaseException:c.close();raise


# Logical payloads are split into 64KiB database rows. Public logical lengths
# are not constrained by this internal segment target.
SEGMENT=65536

def put_stream(c,seq,field,chunks):
    pending=bytearray();part=0
    for chunk in chunks:
        for offset in range(0,len(chunk),SEGMENT):
            pending.extend(chunk[offset:offset+SEGMENT])
            while len(pending)>=SEGMENT:
                c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,bytes(pending[:SEGMENT])));del pending[:SEGMENT];part+=1
    if pending:c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,bytes(pending)))


def read_payload(c,seq,field):
    return b''.join(row[0] for row in c.execute('SELECT data FROM payload WHERE seq=? AND field=? ORDER BY part',(seq,field)))


def text_parts(text):
    for i in range(0,len(text),8192):yield text[i:i+8192].encode('utf8')


def json_parts(meta):
    # Flat metadata only: encode string windows without a logical-string-sized
    # JSON escaped copy. Numeric formatting remains the existing parser contract.
    def string_parts(value):
        yield b'"'
        for i in range(0,len(value),8192):yield json.dumps(value[i:i+8192],ensure_ascii=False)[1:-1].encode('utf8')
        yield b'"'
    yield b'{'
    for index,(key,value) in enumerate(meta.items()):
        if index:yield b','
        yield from string_parts(key);yield b':'
        if type(value) is str:yield from string_parts(value)
        else:yield json.dumps(value,allow_nan=False).encode('ascii')
    yield b'}'


def vector_parts(v,query=False):
    # Inspect container and scalar types before any NumPy coercion hook.
    if type(v) not in (list,tuple,np.ndarray):fail()
    if type(v) is np.ndarray and (v.ndim!=1 or v.dtype.kind not in 'iuf'):fail()
    if not len(v):fail('invalid_dimension')
    for start in range(0,len(v),8192):
        part=v[start:start+8192]
        if type(v) is not np.ndarray and any(type(x) not in (int,float) for x in part):fail()
        try:
            if not all(math.isfinite(x) for x in part):fail()
            with np.errstate(over='ignore'):a=np.array(part,dtype='<f4')
        except (ValueError,OverflowError,TypeError) as exc:raise VectorInputError('invalid_input','encode') from exc
        # finite binary64 that overflows f32 follows actual add oracle rejection.
        if not query and not np.isfinite(a).all():fail()
        yield a.tobytes()


class Collection:
    def __init__(self,store):self.s=store
    @boundary('encode')
    def add(self,ids,embeddings,documents=None,metadatas=None):
        if type(ids) is not list or not ids or any(type(i) is not str or not i for i in ids) or len(set(ids))!=len(ids):fail()
        if type(embeddings) not in (list,tuple,np.ndarray) or len(embeddings)!=len(ids):fail()
        if documents is not None and len(documents)!=len(ids):fail()
        if metadatas is not None and len(metadatas)!=len(ids):fail()
        # A private on-disk SQLite stage validates the complete batch before the
        # target transaction; no batch-sized vector matrix or encoded payload.
        with temporary_directory(dir=self.s.persist_dir) as directory:
            stage=Path(directory)/'stage.sqlite'
            with closing(connect(stage)) as t:
                t.execute('CREATE TABLE payload(seq INTEGER,field TEXT,part INTEGER,data BLOB,PRIMARY KEY(seq,field,part))')
                t.execute('CREATE TABLE staged(seq INTEGER,id TEXT,dimension INTEGER)')
                dimension=None
                for index,identifier in enumerate(ids):
                    vector=embeddings[index]
                    for count,blob in enumerate(vector_parts(vector)):
                        t.execute('INSERT INTO payload VALUES (?,?,?,?)',(index,'vector',count,blob))
                    dim=len(vector)
                    if dimension is not None and dim!=dimension:fail('invalid_dimension')
                    dimension=dim
                    text='' if documents is None else documents[index]
                    if type(text) is not str:fail()
                    meta={} if metadatas is None else metadatas[index]
                    if type(meta) is not dict or any(type(k) is not str or type(v) not in (str,int,float,bool) for k,v in meta.items()):fail()
                    compatible={k:ingress(v) for k,v in meta.items()}
                    put_stream(t,index,'document',text_parts(text))
                    put_stream(t,index,'metadata',json_parts(compatible))
                    t.execute('INSERT INTO staged VALUES (?,?,?)',(index,identifier,dim))
                t.commit()
                with closing(connect(self.s.path)) as c,c:
                    c.execute('BEGIN IMMEDIATE')
                    old=c.execute('SELECT dimension FROM collections WHERE name=?',(self.s.collection_name,)).fetchone()[0]
                    if old is not None and old!=dimension:fail('invalid_dimension')
                    c.execute('UPDATE collections SET dimension=? WHERE name=?',(dimension,self.s.collection_name))
                    for index,identifier,dim in t.execute('SELECT * FROM staged ORDER BY seq'):
                        cursor=c.execute('INSERT OR IGNORE INTO records(collection,id) VALUES (?,?)',(self.s.collection_name,identifier))
                        if cursor.rowcount==0:continue
                        seq=cursor.lastrowid
                        for field,part,data in t.execute('SELECT field,part,data FROM payload WHERE seq=? ORDER BY field,part',(index,)):
                            c.execute('INSERT INTO payload VALUES (?,?,?,?)',(seq,field,part,data))
    def count(self):return self.s.count()
    def get(self,ids=None,where=None,include=None,limit=None,offset=0):
        if ids is not None and (type(ids) is not list or not ids or len(set(ids))!=len(ids)):fail(op='read')
        if type(offset) is not int or offset<0 or (limit is not None and (type(limit) is not int or limit<0)):fail(op='read')
        match=compile_where(where); wanted=None if ids is None else set(ids)
        out={'ids':[],'documents':[],'metadatas':[]};seen=0
        pages=self.s.iter_record_pages()
        try:
            for page in pages:
                for identifier,text,meta in zip(page['ids'],page['documents'],page['metadatas']):
                    if (wanted is not None and identifier not in wanted) or not match(meta):continue
                    if seen<offset:seen+=1;continue
                    if limit is not None and len(out['ids'])>=limit:return out
                    out['ids'].append(identifier);out['documents'].append(text);out['metadatas'].append(meta)
            return out
        finally:pages.close()
    @boundary('encode')
    def delete(self,ids=None,where=None):
        match=compile_where(where); wanted=None if ids is None else set(ids)
        with closing(connect(self.s.path)) as c,c:
            for seq,identifier in c.execute('SELECT seq,id FROM records WHERE collection=?',(self.s.collection_name,)):
                if wanted is not None and identifier not in wanted:continue
                if match(json.loads(read_payload(c,seq,'metadata'))):c.execute('DELETE FROM records WHERE seq=?',(seq,))


class VectorStore:
    @boundary('open')
    def __init__(self,collection_name=DEFAULT_COLLECTION,persist_dir=None,embedding_dim=DEFAULT_DIM):
        if type(collection_name) is not str or not collection_name or type(embedding_dim) is not int or embedding_dim<1:fail()
        self.collection_name=collection_name;self.persist_dir=str(Path(persist_dir or VECTORDB_DIR).resolve());self.embedding_dim=embedding_dim
        Path(self.persist_dir).mkdir(parents=True,exist_ok=True);self.path=Path(self.persist_dir)/'vectors.sqlite'
        with closing(connect(self.path)) as c,c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS collections(name TEXT PRIMARY KEY,dimension INTEGER)')
            c.execute('CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT,collection TEXT NOT NULL,id TEXT NOT NULL,UNIQUE(collection,id))')
            c.execute('CREATE TABLE IF NOT EXISTS payload(seq INTEGER REFERENCES records(seq) ON DELETE CASCADE,field TEXT,part INTEGER,data BLOB,PRIMARY KEY(seq,field,part))')
            c.execute('INSERT OR IGNORE INTO collections VALUES (?,NULL)',(collection_name,))
        self._collection=Collection(self)
    def iter_record_pages(self,page_size=256):
        if type(page_size) is not int or page_size<1:fail(op='scan')
        def pages():
            try:
                with closing(connect(self.path,True)) as c:
                    c.execute('BEGIN')
                    out={'ids':[],'documents':[],'metadatas':[]};page_bytes=0
                    for seq,identifier in c.execute('SELECT seq,id FROM records WHERE collection=? ORDER BY seq',(self.collection_name,)):
                        logical=c.execute("SELECT COALESCE(SUM(length(data)),0) FROM payload WHERE seq=? AND field IN ('document','metadata')",(seq,)).fetchone()[0]+len(identifier)*4
                        if out['ids'] and (len(out['ids'])>=page_size or page_bytes+logical>8*1024*1024):
                            yield out
                            out={'ids':[],'documents':[],'metadatas':[]};page_bytes=0
                        out['ids'].append(identifier);out['documents'].append(read_payload(c,seq,'document').decode('utf8'));out['metadatas'].append(json.loads(read_payload(c,seq,'metadata')));page_bytes+=logical
                    if out['ids']:yield out
            except VectorStoreError:raise
            except Exception as exc:raise VectorStorageError('storage_unavailable','scan') from exc
        return pages()
    @boundary('count')
    def count(self):
        with closing(connect(self.path,True)) as c:return c.execute('SELECT COUNT(*) FROM records WHERE collection=?',(self.collection_name,)).fetchone()[0]
    def add_chunks(self,chunks,embeddings):
        if len(chunks)!=len(embeddings):raise VectorInputError('invalid_input','encode',length_mismatch=True)
        if not chunks:return
        self._collection.add(ids=[x.chunk_id for x in chunks],embeddings=embeddings,documents=[x.text for x in chunks],metadatas=[{k:('' if v is None else v) for k,v in _build_chroma_metadata(x).items()} for x in chunks])
    def delete_by_source(self,source_file):self._collection.delete(where={'source_file':source_file})
    def delete_by_chunk_ids(self,chunk_ids):
        if chunk_ids:self._collection.delete(ids=chunk_ids)
    def get_by_ids(self,chunk_ids):
        if not chunk_ids:return []
        r=self._collection.get(ids=chunk_ids)
        return [dict(chunk_id=i,text=t,metadata=_parse_chroma_metadata(m)) for i,t,m in zip(r['ids'],r['documents'],r['metadatas'])]
    def list_sources(self):
        sources=set();pages=self.iter_record_pages()
        try:
            for p in pages:
                sources.update(m['source_file'] for m in p['metadatas'] if m.get('source_file'))
        finally:pages.close()
        return sorted(sources)
    def get_collection_info(self):return dict(name=self.collection_name,count=self.count(),dimension=self.embedding_dim,sources=len(self.list_sources()),persist_dir=self.persist_dir)
    def create_migration_collection(self,new_dim,suffix='_v2'):return VectorStore(self.collection_name+suffix,self.persist_dir,new_dim)
    @boundary('read')
    def backup(self,snapshot):
        snapshot=Path(snapshot)
        with snapshot.open('xb'):pass
        try:
            with closing(connect(self.path,True)) as source,closing(connect(snapshot)) as dest:
                source.backup(dest,pages=256)
                if dest.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:fail(op='read')
            digest=hashlib.sha256();size=0
            with snapshot.open('rb') as f:
                while block:=f.read(65536):digest.update(block);size+=len(block)
            return dict(sha256=digest.hexdigest(),size=size)
        except BaseException:snapshot.unlink(missing_ok=True);raise
    @staticmethod
    @boundary('open')
    def restore(snapshot,target,*,sha256,size,collection_name=DEFAULT_COLLECTION,embedding_dim=DEFAULT_DIM):
        target=Path(target)
        if target.exists():fail(op='open')
        if type(size) is not int or size<1 or type(sha256) is not str:fail(op='open')
        with temporary_directory(dir=target.parent) as stage_dir:
            stage=Path(stage_dir)/'verified.sqlite';digest=hashlib.sha256();actual=0
            with Path(snapshot).open('rb') as src,stage.open('xb') as dst:
                while block:=src.read(65536):
                    actual+=len(block)
                    if actual>size:fail(op='open')
                    digest.update(block);dst.write(block)
            if actual!=size or not hmac.compare_digest(digest.hexdigest(),sha256):fail(op='open')
            with closing(connect(stage,True)) as c:
                if c.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:fail(op='open')
                if set(r[0] for r in c.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"))!={'collections','records','payload'}:fail(op='open')
            target.mkdir()
            try:
                with closing(connect(stage,True)) as src,closing(connect(target/'vectors.sqlite')) as dst:src.backup(dst,pages=256)
                return VectorStore(collection_name,str(target),embedding_dim)
            except BaseException:
                import shutil
                shutil.rmtree(target)
                raise
    @boundary('search')
    def search(self,query_vector,top_k=20,where=None,text_char_limit=None,metadata_keys=None):
        if type(top_k) is not int or top_k<1:fail(op='search')
        match=compile_where(where)
        # HNSW cosine preprocessing uses f32 norm and f32 arithmetic.
        qnorm=np.float32(0)
        for blob in vector_parts(query_vector,query=True):
            with np.errstate(over='ignore',invalid='ignore'):
                for x in np.frombuffer(blob,dtype='<f4'):qnorm=np.float32(qnorm+np.float32(x*x))
        qnorm=np.float32(np.sqrt(qnorm)+np.float32(1e-30))
        heap=[]
        with closing(connect(self.path,True)) as c:
            c.execute('BEGIN')
            dim=c.execute('SELECT dimension FROM collections WHERE name=?',(self.collection_name,)).fetchone()[0]
            if dim is not None and dim!=len(query_vector):fail('invalid_dimension','search')
            for seq,identifier in c.execute('SELECT seq,id FROM records WHERE collection=? ORDER BY seq',(self.collection_name,)):
                meta=json.loads(read_payload(c,seq,'metadata'))
                if not match(meta):continue
                norm=np.float32(0)
                for blob, in c.execute("SELECT data FROM payload WHERE seq=? AND field='vector' ORDER BY part",(seq,)):
                    for x in np.frombuffer(blob,dtype='<f4'):norm=np.float32(norm+np.float32(x*x))
                norm=np.float32(np.sqrt(norm)+np.float32(1e-30));dot=np.float32(0);start=0
                for blob, in c.execute("SELECT data FROM payload WHERE seq=? AND field='vector' ORDER BY part",(seq,)):
                    v=np.frombuffer(blob,dtype='<f4')/norm
                    with np.errstate(over='ignore',invalid='ignore'):
                        q=np.array(query_vector[start:start+len(v)],dtype='<f4')/qnorm
                        for a,b in zip(q,v):dot=np.float32(dot+np.float32(a*b))
                    start+=len(v)
                distance=float(np.float32(np.float32(1)-dot));score=1-distance/2
                item=(score,-seq,seq,identifier)
                if len(heap)<top_k:heapq.heappush(heap,item)
                elif item>heap[0]:heapq.heapreplace(heap,item)
            output=[]
            for score,_,seq,identifier in sorted(heap,reverse=True):
                text=read_payload(c,seq,'document').decode('utf8');meta=_parse_chroma_metadata(json.loads(read_payload(c,seq,'metadata')))
                if text_char_limit is not None:text=text[:text_char_limit]
                if metadata_keys is not None:meta={k:meta[k] for k in metadata_keys if k in meta}
                output.append(dict(chunk_id=identifier,text=text,score=round(score,4),source='vector',metadata=meta))
            return output


def create_vector_store(collection_name=DEFAULT_COLLECTION,embedding_dim=DEFAULT_DIM,persist_dir=None):return VectorStore(collection_name,persist_dir,embedding_dim)
def _build_chroma_metadata(chunk) -> dict:
    """Convert Chunk metadata to ChromaDB-compatible flat dict.

    ChromaDB metadata must be str, int, float, or bool only.
    Lists and dicts are serialized to JSON strings.
    """
    if chunk.metadata is None:
        return {
            "source_file": "",
            "source_format": "",
            "content_type": chunk.content_type,
            "page_idx": 0,
        }

    meta = chunk.metadata
    entity_types_json = json.dumps(meta.entity_types) if meta.entity_types else "[]"
    section_path_json = json.dumps(meta.section_path) if meta.section_path else "[]"
    entity_ids_json = json.dumps(getattr(meta, "entity_ids", [])) if getattr(meta, "entity_ids", None) else "[]"

    return {
        "source_file": meta.source_file or "",
        "source_format": meta.source_format or "",
        "page_idx": meta.page_idx if meta.page_idx is not None else 0,
        "content_type": meta.content_type or chunk.content_type,
        "project_id": meta.project_id or "",
        "token_count": meta.token_count,
        "entity_types": entity_types_json,
        "section_path": section_path_json,
        "entity_ids": entity_ids_json,
        "char_start": meta.char_start,
        "char_end": meta.char_end,
    }


def _parse_chroma_metadata(meta: dict) -> dict:
    """Parse ChromaDB flat metadata back to structured dict."""
    if not meta:
        return {}

    result = dict(meta)

    # Deserialize JSON fields
    for field in ["entity_types", "section_path", "entity_ids"]:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                result[field] = []

    return result




