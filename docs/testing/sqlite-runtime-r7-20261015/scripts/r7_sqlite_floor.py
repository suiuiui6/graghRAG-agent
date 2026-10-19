import json,sqlite3,sys
print(json.dumps({'executable':sys.executable,'sqlite_version':sqlite3.sqlite_version,'required_floor':[3,53,2],'passed':sqlite3.sqlite_version_info>=(3,53,2)}))
assert sqlite3.sqlite_version_info >= (3,53,2),'SQLite runtime does not meet pinned remediation floor'
