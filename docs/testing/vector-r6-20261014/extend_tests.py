from pathlib import Path
p=Path('.tmp/vector-errors-r5-20261014/test_errors.py');s=p.read_text()
s=s.replace("with patch.object(generic_filter,'col',side_effect=KeyboardInterrupt()):", "for operation,action in [('read',lambda:self.store.read({'n':1})),('count',self.store.count),('scan',self.store.scan)]:\n   method='count_rows' if operation=='count' else 'search'\n   with patch.object(self.store.table,method,side_effect=ValueError(SENTINEL)):\n    self.error(action,'storage_unavailable',operation,ValueError)\n  with patch.object(generic_filter,'col',side_effect=KeyboardInterrupt()):")
s=s.replace("with self.assertRaises(KeyboardInterrupt):self.store.projection.compile({'n':1})", "with self.assertRaises(KeyboardInterrupt):self.store.projection.compile({'n':1})\n  with patch.object(self.store.table,'search',side_effect=SystemExit(9)):\n   with self.assertRaises(SystemExit):self.store.search([1.,0.,0.])")
p.write_text(s)
