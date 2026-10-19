"""Pure stdlib public errors. Causes are internal and NOT traceback-redacted."""
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
class VectorCapabilityError(VectorStoreError, ValueError): pass

