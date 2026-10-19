import ctypes, datetime, hashlib, json, pathlib, sqlite3, sys, ssl, zlib, pyexpat, _sqlite3, _ssl, _ctypes

out = pathlib.Path(__file__).resolve().parent
c = sqlite3.connect(':memory:')
r = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'executable': sys.executable, 'python': sys.version, 'base_prefix': sys.base_prefix, 'sqlite_version': sqlite3.sqlite_version, 'sqlite_source_id': c.execute('select sqlite_source_id()').fetchone()[0], 'sqlite_threadsafety': sqlite3.threadsafety, 'compile_options': [v[0] for v in c.execute('pragma compile_options')], 'module_paths': {m.__name__: m.__file__ for m in [sqlite3, _sqlite3, _ssl, _ctypes]}, 'openssl': ssl.OPENSSL_VERSION, 'zlib_compiled': zlib.ZLIB_VERSION, 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION, 'expat': pyexpat.EXPAT_VERSION}
r['defensive_initial'] = c.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE)
c.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
r['defensive_hardened'] = c.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE)
r['trusted_schema_initial'] = c.execute('pragma trusted_schema').fetchone()[0]
c.execute('pragma trusted_schema=off')
r['trusted_schema_hardened'] = c.execute('pragma trusted_schema').fetchone()[0]
r['extension_initial'] = c.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION)
c.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False)
r['extension_hardened'] = c.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION)
try:
    c.execute("select load_extension('r7_nonexistent_forbidden')")
except sqlite3.Error as e:
    r['extension_sql_rejection'] = str(e)
c.execute('create table checkdata(id text primary key, payload blob)')
c.execute('insert into checkdata values (?,?)', ('synthetic', b'\x00\xff'))
assert c.execute('select payload from checkdata where id=?', ('synthetic',)).fetchone()[0] == b'\x00\xff'
r['synthetic_parameterized_blob_roundtrip'] = True
psapi = ctypes.WinDLL('psapi', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
process = kernel32.GetCurrentProcess()
modules = (ctypes.c_void_p * 2048)()
needed = ctypes.c_ulong()
psapi.EnumProcessModules.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
assert psapi.EnumProcessModules(process, modules, ctypes.sizeof(modules), ctypes.byref(needed))
psapi.GetModuleFileNameExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
r['loaded_modules'] = []
for handle in modules[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
    buf = ctypes.create_unicode_buffer(32768)
    assert psapi.GetModuleFileNameExW(process, handle, buf, len(buf))
    p = pathlib.Path(buf.value)
    r['loaded_modules'].append({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size})
r['runtime_files'] = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size} for p in pathlib.Path(sys.base_prefix).rglob('*') if p.is_file() and p.suffix.lower() in {'.dll', '.pyd', '.exe'}]
r['sqlite_floor_met'] = sqlite3.sqlite_version_info >= (3, 53, 2)
(out / 'runtime-native.json').write_text(json.dumps(r, indent=2), encoding='utf-8')
print(json.dumps({k: r[k] for k in ['executable', 'python', 'sqlite_version', 'sqlite_floor_met', 'defensive_initial', 'defensive_hardened', 'trusted_schema_initial', 'trusted_schema_hardened', 'extension_initial', 'extension_hardened', 'openssl', 'zlib_runtime', 'expat']}, indent=2))
