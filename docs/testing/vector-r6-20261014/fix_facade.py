from pathlib import Path
p=Path('.tmp/vector-errors-r5-20261014/probe_store.py');s=p.read_text()
s=s.replace("if any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):raise VectorInputError('invalid_input',operation)", "for v in vector:\n        if type(v) not in (int,float):raise VectorInputError('invalid_input',operation)\n        try:finite=math.isfinite(v)\n        except OverflowError as exc:raise VectorInputError('invalid_input',operation) from exc\n        if not finite:raise VectorInputError('invalid_input',operation)")
s=s.replace("score=1.-row['_distance']", "score=round(1.-row['_distance']/2.,4)")
p.write_text(s)
