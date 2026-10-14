"""Temporary audit port: serde_json 1.0.149 default de.rs numeric path, valid JSON tokens only."""
import re,math
MAX=(1<<64)-1
POW10=tuple(float('1e'+str(i)) for i in range(309))
def parse(token):
    m=re.fullmatch(r'(-?)(0|[1-9][0-9]*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?',token)
    if not m: raise ValueError('invalid numeric token')
    sign,whole,frac,exp=m.groups(); sig=0; exponent=0; overflow=False
    for c in whole:
        n=sig*10+int(c)
        if overflow or n>MAX: overflow=True;exponent+=1
        else: sig=n
    if frac is not None:
        for c in frac:
            n=sig*10+int(c)
            if n>MAX: break
            sig=n;exponent-=1
    if frac is None and exp is None and not overflow:
        if not sign:return 'u64',sig
        if 0<sig<=1<<63:return 'i64',-sig
        return 'f64',-float(sig)
    exponent+=int(exp or 0)
    f=float(sig)
    while abs(exponent)>308:
        if not f:break
        if exponent>=0:raise ValueError('number out of range')
        f/=1e308;exponent+=308
    else:
        f=f*POW10[exponent] if exponent>=0 else f/POW10[-exponent]
    if math.isinf(f):raise ValueError('number out of range')
    return 'f64',-f if sign else f
