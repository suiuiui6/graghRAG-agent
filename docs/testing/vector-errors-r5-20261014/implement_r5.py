from pathlib import Path
p=Path('.tmp/vector-errors-r5-20261014')
(p/'vector_errors.py').write_text('''"""Pure stdlib public errors. Causes are internal and NOT traceback-redacted."""
MESSAGES = {'invalid_filter':'过滤条件无效','invalid_dimension':'向量维度无效','invalid_input':'输入记录或向量无效','unsupported_capability':'当前静态代不支持此操作','storage_unavailable':'向量存储暂不可用'}
OPERATIONS = {'open','compile','encode','search','read','count','scan'}
class VectorStoreError(Exception):
    def __init__(self, code, operation, *, length_mismatch=False):
        if code not in MESSAGES or operation not in OPERATIONS: raise ValueError('invalid internal error identity')
        self.code, self.operation, self.retryable = code, operation, False
        self.message = 'Length mismatch: 批次数量不一致' if length_mismatch else MESSAGES[code]
        super().__init__(self.message)
    def public_dict(self): return dict(code=self.code,operation=self.operation,retryable=self.retryable,message=self.message)
class VectorInputError(VectorStoreError, ValueError): pass
class VectorStorageError(VectorStoreError): pass
class VectorCapabilityError(VectorStoreError): pass
''',encoding='utf-8')
f=p/'generic_filter.py'
s=f.read_text();s=s.replace('from parser_port import parse','from parser_port import parse\nfrom vector_errors import VectorStoreError, VectorInputError, VectorStorageError, VectorCapabilityError\n\ndef numeric_parse(value, query=False):\n    try: return parse(json.dumps(value))\n    except (ValueError, OverflowError) as exc:\n        raise VectorInputError("invalid_filter" if query else "invalid_input", "compile" if query else "encode") from exc')
s=s.replace('parse(json.dumps(value))','numeric_parse(value, query=query)',1) if False else s
# Only replace calls in original ingress / set, not numeric_parse itself.
s=s.replace('tag, parsed=parse(json.dumps(value))','tag, parsed=numeric_parse(value, query=query)')
s=s.replace('values=[parse(json.dumps(v)) for v in arg]','values=[numeric_parse(v, query=True) for v in arg]')
s=s.replace("raise ValueError('Invalid where clause: unsigned integer outside signed int64')","raise VectorInputError('invalid_filter','compile')")
s=s.replace("keys=sorted({key for record in records for key in record['metadata']})\n        if any(type(key) is not str for key in keys): raise ValueError('metadata keys must be strings')","for record in records: self._validate_record(record)\n        keys=sorted({key for record in records for key in record['metadata']})")
s=s.replace("if unknown: raise ValueError('new metadata key needs new generation/backfill; not implemented')","if unknown: raise VectorCapabilityError('unsupported_capability','encode')")
s=s.replace("    def encode(self, record, vector=None):\n        unknown", "    def encode(self, record, vector=None):\n        self._validate_record(record)\n        unknown")
# Explicit validation branches only; expression code remains outside input catches.
lines=s.splitlines()
for i,line in enumerate(lines):
 if 'raise ValueError(' in line:
  operation='encode' if i<next(j for j,l in enumerate(lines) if 'def _scalar' in l) else 'compile'
  code='invalid_input' if operation=='encode' else 'invalid_filter'
  lines[i]=line[:line.index('raise ValueError(')]+f"raise VectorInputError('{code}','{operation}')"
s='\n'.join(lines)+'\n'
marker='    def __init__(self, records):'
validation='''    @staticmethod
    def _validate_record(record):
        if not isinstance(record,dict) or type(record.get('id')) is not str or not isinstance(record.get('metadata'),dict):
            raise VectorInputError('invalid_input','encode')
        for key,value in record['metadata'].items():
            if type(key) is not str or type(value) not in SCALARS:
                raise VectorInputError('invalid_input','encode')
            if type(value) is int and not -(2**63)<=value<2**63:
                raise VectorInputError('invalid_input','encode')
            if type(value) is float and not math.isfinite(value):
                raise VectorInputError('invalid_input','encode')

'''
s=s.replace(marker,validation+marker)
# Wrap native paths using a decorator that preserves typed validation and BaseException.
s+='''

def _public_boundary(operation):
    def decorate(fn):
        @functools.wraps(fn)
        def call(*args, **kwargs):
            try: return fn(*args, **kwargs)
            except VectorStoreError: raise
            except Exception as exc: raise VectorStorageError('storage_unavailable',operation) from exc
        return call
    return decorate
StaticProjection.__init__ = _public_boundary('open')(StaticProjection.__init__)
StaticProjection.encode = _public_boundary('encode')(StaticProjection.encode)
StaticProjection.compile = _public_boundary('compile')(StaticProjection.compile)
'''
f.write_text(s,encoding='utf-8')
