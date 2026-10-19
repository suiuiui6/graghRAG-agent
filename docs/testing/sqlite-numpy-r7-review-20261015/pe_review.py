"""Read PE structures only; never load or execute inspected DLLs."""
import hashlib
import json
from pathlib import Path
import struct
import sys


def inspect(path):
    raw = Path(path).read_bytes()
    u16 = lambda p: struct.unpack_from('<H', raw, p)[0]
    u32 = lambda p: struct.unpack_from('<I', raw, p)[0]
    pe = u32(0x3c)
    assert raw[:2] == b'MZ' and raw[pe:pe+4] == b'PE\0\0'
    machine, count = u16(pe+4), u16(pe+6)
    opt = pe+24
    magic = u16(opt)
    assert magic in (0x10b, 0x20b)
    dirs = opt + (112 if magic == 0x20b else 96)
    section = opt + u16(pe+20)
    sections = []
    for i in range(count):
        p = section+40*i
        sections.append((u32(p+12), max(u32(p+8), u32(p+16)), u32(p+20)))

    def offset(rva):
        for start, size, ptr in sections:
            if start <= rva < start+size:
                return ptr+rva-start
        if rva < u32(opt+60):
            return rva
        raise ValueError(f'Unmapped RVA {rva}')

    def string(rva):
        p = offset(rva)
        return raw[p:raw.index(b'\0', p)].decode('ascii')

    exports = []
    er = u32(dirs)
    if er:
        p = offset(er)
        n, names = u32(p+24), offset(u32(p+32))
        exports = sorted(string(u32(names+4*i)) for i in range(n))
    imports = {}
    ir = u32(dirs+8)
    if ir:
        p = offset(ir)
        while any(raw[p:p+20]):
            thunk, name, first = u32(p), u32(p+12), u32(p+16)
            q = offset(thunk or first)
            names = []
            width = 8 if magic == 0x20b else 4
            while True:
                value = int.from_bytes(raw[q:q+width], 'little')
                if not value:
                    break
                if value & (1 << (width*8-1)):
                    names.append(f'ordinal:{value & 0xffff}')
                else:
                    names.append(string(value+2))
                q += width
            imports[string(name)] = sorted(names)
            p += 20
    return dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw), machine=hex(machine), magic=hex(magic),
                exports=exports, imports=imports)


if __name__ == '__main__':
    binding, library = map(inspect, sys.argv[1:3])
    required = []
    for dll, names in binding['imports'].items():
        if dll.lower() == 'sqlite3.dll':
            required.extend(names)
    missing = sorted(set(required)-set(library['exports']))
    result = dict(binding=binding, library=library, required_sqlite_exports=required,
                  missing_sqlite_exports=missing,
                  compatible_machine=binding['machine'] == library['machine'] == '0x8664')
    print(json.dumps(result, indent=2))
    assert required and not missing and result['compatible_machine']
