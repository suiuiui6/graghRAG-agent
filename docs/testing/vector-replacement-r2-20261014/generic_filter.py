"""Isolated static-generation metadata projection, not a product adapter."""
import functools
import json
import math
import operator

import pyarrow as pa
from lancedb.expr import col, lit

SCALARS={bool:'bool',int:'int',float:'float',str:'str'}
OPS={'$eq':'eq','$ne':'ne','$gt':'gt','$gte':'gte','$lt':'lt','$lte':'lte'}
NUMERIC_RULES={'int_record_int_query':'signed int64 exact','int_record_float_query':'truncate float toward zero then signed int64','float_record_int_query':'binary64(query)','float_record_float_query':'binary64 exact'}

class StaticProjection:
    def __init__(self, records):
        keys=sorted({key for record in records for key in record['metadata']})
        if any(type(key) is not str for key in keys): raise ValueError('metadata keys must be strings')
        self.mapping={key:f'm{index}' for index,key in enumerate(keys)}
        fields=[('id',pa.string()),('metadata_json',pa.string()),('vector',pa.list_(pa.float32(),3))]
        for prefix in self.mapping.values():
            fields.extend([(prefix+'_present',pa.bool_()),(prefix+'_type',pa.string()),(prefix+'_bool',pa.bool_()),(prefix+'_int',pa.int64()),(prefix+'_float',pa.float64()),(prefix+'_str',pa.string())])
        self.schema=pa.schema(fields)
        # The same immutable-generation mapping is embedded in the table schema.
        self.schema=self.schema.with_metadata({b'metadata_projection':json.dumps(self.mapping,ensure_ascii=False,sort_keys=True).encode('utf-8')})

    def encode(self, record, vector=None):
        unknown=set(record['metadata'])-set(self.mapping)
        if unknown: raise ValueError('new metadata key needs new generation/backfill; not implemented')
        meta=record['metadata']
        out={'id':record['id'],'metadata_json':json.dumps(meta,ensure_ascii=False,sort_keys=True),'vector':vector or [1.,0.,0.]}
        for key,prefix in self.mapping.items():
            value=meta.get(key)
            present=key in meta
            tag=SCALARS.get(type(value),'missing') if present else 'missing'
            if present and tag=='missing': raise ValueError('unsupported metadata scalar')
            if tag=='int' and not -(2**63)<=value<2**63: raise ValueError('signed int64 overflow')
            if tag=='float' and not math.isfinite(value): raise ValueError('non-finite float')
            out.update({prefix+'_present':present,prefix+'_type':tag,prefix+'_bool':value if tag=='bool' else False,prefix+'_int':value if tag=='int' else 0,prefix+'_float':value if tag=='float' else 0.,prefix+'_str':value if tag=='str' else ''})
        return out

    def _scalar(self,key,op,value):
        tag=SCALARS.get(type(value))
        if tag is None or (tag=='float' and not math.isfinite(value)): raise ValueError('invalid scalar literal')
        if op in ('$gt','$gte','$lt','$lte') and tag not in ('int','float'): raise ValueError('range requires numeric literal')
        prefix=self.mapping.get(key)
        if prefix is None: return lit(op=='$ne')
        present=col(prefix+'_present')
        dtype=col(prefix+'_type')
        method=OPS[op]
        if tag in ('int','float'):
            # Chroma truth shows query literals are converted to the stored type.
            integer=int(value)
            if not -(2**63)<=integer<2**63: raise ValueError('query conversion exceeds tested int64 boundary')
            as_float=float(value)
            cmp_int=getattr(col(prefix+'_int'),method)(lit(integer))
            cmp_float=getattr(col(prefix+'_float'),method)(lit(as_float))
            comparable=((dtype==lit('int'))&cmp_int)|((dtype==lit('float'))&cmp_float)
            if op=='$ne':
                return (~present)|((dtype!=lit('int'))&(dtype!=lit('float')))|comparable
            return present&comparable
        comparable=(dtype==lit(tag))&getattr(col(prefix+'_'+tag),method)(lit(value))
        if op=='$ne': return (~present)|(dtype!=lit(tag))|comparable
        return present&comparable

    def compile(self,where):
        # These new resource limits are isolated-probe limits, not an accepted public contract.
        budget=[0]
        def visit(node,depth=0):
            budget[0]+=1
            if depth>16 or budget[0]>512: raise ValueError('probe resource limit')
            if not isinstance(node,dict) or len(node)!=1: raise ValueError('one key required')
            key,value=next(iter(node.items()))
            if type(key) is not str: raise ValueError('field must be string')
            if key in ('$and','$or'):
                if not isinstance(value,list) or not 2<=len(value)<=64: raise ValueError('logical operands')
                return functools.reduce(operator.and_ if key=='$and' else operator.or_,[visit(x,depth+1) for x in value])
            if key.startswith('$'): raise ValueError('unsupported logical operator')
            if not isinstance(value,dict): value={'$eq':value}
            if len(value)!=1: raise ValueError('one comparison required')
            op,arg=next(iter(value.items()))
            if op in ('$in','$nin'):
                if not isinstance(arg,list) or not 1<=len(arg)<=64 or any(type(v) is not type(arg[0]) for v in arg): raise ValueError('nonempty homogeneous list required')
                if type(arg[0]) not in SCALARS: raise ValueError('invalid member type')
                # Explicit OR of eq / AND of ne uses independently measured negative semantics.
                return functools.reduce(operator.or_ if op=='$in' else operator.and_,[self._scalar(key,'$eq' if op=='$in' else '$ne',v) for v in arg])
            if op not in OPS: raise ValueError('unsupported comparison')
            return self._scalar(key,op,arg)
        return visit(where)
