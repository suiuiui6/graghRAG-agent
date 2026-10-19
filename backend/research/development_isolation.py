"""Public development adapter; no production indexes or server lifespan are used.

Commands (execute in fresh processes with the existing backend interpreter):
  prepare --repo-root PATH --run-root NEW_PATH
  preflight --run-root SEPARATE_SIMULATION_PATH --sources SOURCES_JSON --pdf-xml NIST_XML
  index --run-root PATH --sources SOURCES_JSON --pdf-xml NIST_XML --ledger PATH
  query --run-root PATH --document-id ID --question TEXT --question-id ID --ledger PATH

The caller injects LANGEXTRACT_API_KEY in process environment; this module never
opens .env. All command output contains safe status only. Index/query share one
BudgetGuard ledger. prepare is offline and does not need a key.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys


def checked_path(root: str | Path, path: str | Path) -> Path:
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('写入路径越出隔离根')
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def prepare(repo_root, run_root):
    """Copy Python/static configuration only, refusing symlinks and reuse."""
    repo, root = Path(repo_root).resolve(), Path(run_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    excluded = {'.venv', 'venv', 'output', 'uploads', 'tests', '__pycache__', '.git', '.pytest_cache', 'node_modules'}
    manifest = {'repo_root': str(repo), 'run_root': str(root), 'files': {}, 'isolation': 'audit-only-windows'}
    for origin, destination in ((repo / 'backend', root / 'backend'), (repo / 'langextract/langextract', root / 'langextract/langextract')):
        for directory, dirs, files in os.walk(origin):
            dirs[:] = sorted(d for d in dirs if d not in excluded and not (Path(directory) / d).is_symlink())
            for name in sorted(files):
                source = Path(directory) / name
                relative = source.relative_to(origin)
                allowed = source.suffix == '.py' or (origin.name == 'backend' and relative.parts[0] == 'config' and source.suffix in {'.yaml', '.yml', '.json'})
                if not allowed or source.is_symlink():
                    continue
                target = checked_path(root, destination / relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                manifest['files'][str(target.relative_to(root)).replace('\\', '/')] = sha(target)
    for name in ('backend/output', 'backend/uploads', 'temp', 'cache', 'artifacts'):
        checked_path(root, root / name).mkdir(parents=True, exist_ok=True)
    write_json(root / 'snapshot.json', manifest)
    return manifest


def verify_snapshot(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'snapshot.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['files'].items():
        if sha(checked_path(root, root / relative)) != expected:
            raise RuntimeError('隔离源码快照发生变化')
    if (root / 'backend/.env').exists() or (root / 'langextract/.env').exists():
        raise RuntimeError('隔离副本不得包含.env')
    return manifest


def module_identity(root, modules):
    """Verify effective native/editable imports against the copied snapshot."""
    root = Path(root).resolve()
    manifest = json.loads((root / 'snapshot.json').read_text(encoding='utf-8'))
    result = {}
    for name in modules:
        path = checked_path(root, importlib.import_module(name).__file__)
        relative = str(path.relative_to(root)).replace('\\', '/')
        actual = sha(path)
        if manifest['files'].get(relative) != actual:
            raise RuntimeError('有效原生模块未绑定隔离源码快照')
        result[name] = {'path': str(path), 'sha256': actual}
    return result


def activate(run_root):
    """Must run before native backend/LangExtract imports in a fresh process."""
    root = Path(run_root).resolve()
    verify_snapshot(root)
    backend = root / 'backend'
    for module_name in ('worker', 'routes', 'schema', 'langextract', 'generator', 'retrieval'):
        if module_name in sys.modules:
            raise RuntimeError('必须在原生模块导入前激活独占副本')
    for variable in ('TMP', 'TEMP', 'TMPDIR'):
        os.environ[variable] = str(root / 'temp')
    for variable in ('HF_HOME', 'TRANSFORMERS_CACHE', 'SENTENCE_TRANSFORMERS_HOME', 'XDG_CACHE_HOME'):
        os.environ[variable] = str(root / 'cache')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                      LANGEXTRACT_MODEL_ID='deepseek-flash', LANGEXTRACT_BASE_URL='https://api.deepseek.com')
    sys.path[:0] = [str(backend), str(root / 'langextract')]
    os.chdir(backend)
    import tempfile
    tempfile.tempdir = str(root / 'temp')
    return root


def grounding_evidence(text, grounded):
    interval = grounded.char_interval
    valid = bool(interval and len(interval) == 2 and all(type(x) is int for x in interval) and 0 <= interval[0] < interval[1] <= len(text))
    source_slice = text[interval[0]:interval[1]] if valid else None
    return {'native_grounding_status': grounded.grounding_status,
            'source_interval_valid': valid, 'exact_text_match': valid and source_slice == grounded.extraction_text,
            'source_slice': source_slice,
            'source_slice_sha256': hashlib.sha256(source_slice.encode()).hexdigest() if valid else None}


@contextlib.contextmanager
def bounded_langextract(http_client_factory=None):
    """Adapt the actual factory and SDK rather than ignored language_model_params."""
    import langextract as lx
    import langextract.factory as factory
    original_factory, original_extract = factory.create_model, lx.extract
    details = []

    def create(config, *args, **kwargs):
        config = dataclasses.replace(config, provider_kwargs={**config.provider_kwargs,
                                     'max_output_tokens': 4096, 'max_workers': 1})
        result = original_factory(config, *args, **kwargs)
        provider = result[0] if isinstance(result, tuple) else result
        client_options = {'timeout': 30, 'max_retries': 0}
        if http_client_factory is not None:
            client_options['http_client'] = http_client_factory()
        provider._client = provider._client.with_options(**client_options)
        original_create = provider._client.chat.completions.create

        def completion(*positional, **parameters):
            parameters['extra_body'] = {**parameters.get('extra_body', {}), 'thinking': {'type': 'disabled'}}
            return original_create(*positional, **parameters)

        provider._client.chat.completions.create = completion
        if provider._extra_kwargs.get('max_output_tokens') != 4096 or provider.max_workers != 1 or provider._client.max_retries != 0:
            raise RuntimeError('索引供应商配置未生效')
        details.append({'provider_file': importlib.import_module(type(provider).__module__).__file__,
                        'provider_workers': provider.max_workers, 'max_output_tokens': provider._extra_kwargs['max_output_tokens'],
                        'sdk_max_retries': provider._client.max_retries, 'sdk_timeout': 30,
                        'thinking': 'disabled', 'extract_workers': 1})
        return result

    def extract(*args, **kwargs):
        kwargs['max_workers'] = 1
        return original_extract(*args, **kwargs)

    factory.create_model, lx.extract = create, extract
    try:
        yield details
    finally:
        factory.create_model, lx.extract = original_factory, original_extract


def _source_units(manifest_path):
    path = Path(manifest_path).resolve()
    units = []
    for record in json.loads(path.read_text(encoding='utf-8')):
        canonical, raw = (path.parent / record['canonical_file']).resolve(), (path.parent / record['raw_file']).resolve()
        if sha(canonical) != record['canonical_sha256'] or sha(raw) != record['source_sha256']:
            raise RuntimeError('公开来源身份不匹配')
        # newline='' retains the frozen Unicode/LF coordinates exactly.
        with canonical.open(encoding='utf-8', newline='') as handle: text = handle.read()
        units.append((record, text, raw, json.loads((path.parent / record['section_or_page_map']).read_text(encoding='utf-8'))))
    return units


def _bridge_source(record, text, raw, mapping, pdf_xml):
    from bridge import build_documents
    from schema import SectionSplit, PositionMap, Segment
    from research.scope_v2 import Source
    from research.development_structure import build_html_structure, build_pdf_structure
    sid = record['source_id']
    source = Source(sid, text)
    is_html = raw.suffix.lower() == '.html'
    entries = mapping['blocks' if is_html else 'pages'] if isinstance(mapping, dict) else mapping
    structure = (build_html_structure(source, raw.read_bytes(), entries) if is_html
                 else build_pdf_structure(source, entries, Path(pdf_xml).read_bytes()))
    boundaries = sorted({0, len(text), *(n.start for n in structure.nodes if n.kind == 'heading')})
    sections = [SectionSplit(f'{sid}-section-{i:03d}', sid, 1, start, end)
                for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])) if end > start]
    segments = [Segment(e['start'], e['end'], i, None if is_html else e['pdf_page_zero_based'], None,
                        'html_text' if is_html else 'pdf_text', text=text[e['start']:e['end']]) for i, e in enumerate(entries)]
    position_map = PositionMap(segments)
    documents, offsets = build_documents(sections, text)
    bridge = {'sections': [dataclasses.asdict(x) for x in sections], 'position_map': dataclasses.asdict(position_map),
              'offsets': offsets, 'documents': [{'document_id': d.document_id, 'text': d.text,
              'additional_context': d.additional_context} for d in documents], 'structure': dataclasses.asdict(structure)}
    return documents, position_map, offsets, bridge


def preflight_sources(root, manifest_path, pdf_xml):
    """Actual native extraction chunker/SDK with local empty-result responses.

    This counts input prompts, never provider tokens or successful indexing. It
    uses a separate prepared root, no ledger/registration/KG, and a fake key.
    Empty output means data-dependent continuation is not predicted.
    """
    from research.development_budget import openai_transport_module
    sdk_http = openai_transport_module()
    import socket
    import worker
    root = Path(root)
    if (root / 'artifacts/preflight.json').exists():
        raise FileExistsError('模拟预检产物已存在')
    captured, source_results = [], []
    originals = socket.socket.connect, socket.socket.connect_ex, socket.create_connection
    original_key = os.environ.get('LANGEXTRACT_API_KEY')
    os.environ['LANGEXTRACT_API_KEY'] = 'development-simulation-not-a-real-key'
    current_source = None
    identity = module_identity(root, ('worker', 'bridge', 'grounding', 'schema', 'langextract',
                               'langextract.extraction', 'langextract.annotation', 'langextract.providers.openai'))

    def simulate(request):
        payload = json.loads(request.content)
        captured.append({'phase': 'index', 'source_id': current_source, 'input_bytes': len(request.content),
                         'request_sha256': hashlib.sha256(request.content).hexdigest(), 'request': payload})
        return sdk_http.Response(200, request=request, json={'id': 'SIMULATED', 'object': 'chat.completion',
                              'created': 0, 'model': 'SIMULATED', 'choices': [{'index': 0,
                              'finish_reason': 'stop', 'message': {'role': 'assistant',
                              'content': '```json\n{"extractions": []}\n```'}}]})

    def deny_socket(*args, **kwargs):
        raise RuntimeError('离线预检禁止真实socket连接')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = deny_socket
    try:
        for record, text, raw, mapping in _source_units(manifest_path):
            current_source = record['source_id']
            documents, _, _, bridge = _bridge_source(record, text, raw, mapping, pdf_xml)
            before = len(captured)
            with bounded_langextract(http_client_factory=lambda: sdk_http.Client(transport=sdk_http.MockTransport(simulate), trust_env=False)):
                worker._run_langextract(documents)
            source_results.append({'source_id': current_source, 'documents': len(documents),
                                   'planned_requests': len(captured) - before, 'bridge': bridge})
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = originals
        if original_key is None: os.environ.pop('LANGEXTRACT_API_KEY', None)
        else: os.environ['LANGEXTRACT_API_KEY'] = original_key
    result = {'mode': 'SIMULATED_NO_PROVIDER_USAGE', 'planned_requests': len(captured),
              'planned_input_bytes': sum(x['input_bytes'] for x in captured), 'requests': captured,
              'sources': source_results, 'modules': identity,
              'sdk_transport_module': sdk_http.__name__,
              'limitation': 'Empty local extraction output; excludes data-dependent continuation and real usage.'}
    verify_snapshot(root)
    write_json(root / 'artifacts/preflight.json', result)
    return result


def index_sources(root, manifest_path, pdf_xml, guard):
    """Full-source canonical bridge into the genuine native PDF extraction chain."""
    root = Path(root)
    import worker
    import routes
    from grounding import resolve_grounding
    from kg_builder import build_knowledge_graph, serialize_kg
    identity = module_identity(root, ('worker', 'bridge', 'grounding', 'schema', 'kg_builder', 'langextract',
                               'langextract.extraction', 'langextract.annotation', 'langextract.providers.openai'))
    if routes.get_docs_snapshot():
        raise RuntimeError('独占文档库非空，禁止重复索引')
    results = []
    for record, text, raw, mapping in _source_units(manifest_path):
        sid = record['source_id']
        documents, position_map, offsets, bridge = _bridge_source(record, text, raw, mapping, pdf_xml)
        output = checked_path(root, root / 'artifacts' / sid)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / 'bridge.json', bridge)
        with guard.phase('index', sid), bounded_langextract() as provider_details:
            annotated = worker._run_langextract(documents)
        if guard.closed:
            raise RuntimeError('模型预算已关闭，不得继续索引')
        grounded = resolve_grounding(annotated, position_map, offsets)
        annotated_rows, evidence = [], []
        flat = 0
        for adoc in annotated:
            annotated_rows.append(dataclasses.asdict(adoc))
            for ext in adoc.extractions or []:
                row = {'extraction_index': flat, 'node_id': f'n{flat + 1:04d}',
                       'document_id': adoc.document_id, 'local_interval': dataclasses.asdict(ext.char_interval) if ext.char_interval else None,
                       'alignment_status': str(getattr(ext, 'alignment_status', None)),
                       'grounded': dataclasses.asdict(grounded[flat]), **grounding_evidence(text, grounded[flat])}
                evidence.append(row); flat += 1
        nodes, edges = build_knowledge_graph(grounded)
        kg_path = checked_path(root, root / 'backend/output/kg' / sid)
        metadata = {'document_id': sid, 'filename': raw.name, 'source_sha256': record['source_sha256'],
                    'canonical_sha256': record['canonical_sha256'], 'development_adapter': 'canonical_to_pdf_native_extraction'}
        serialize_kg(nodes, edges, metadata, str(kg_path))
        write_json(output / 'annotated.json', annotated_rows)
        write_json(output / 'grounding-evidence.json', evidence)
        write_json(output / 'provider.json', provider_details)
        routes.add_doc({'document_id': sid, 'filename': raw.name, 'kg_path': str(kg_path),
                        'owner_id': 'development-admin', 'org_id': None, 'project_id': None,
                        'status': 'completed', **metadata})
        results.append({'source_id': sid, 'documents': len(documents), 'nodes': len(nodes), 'edges': len(edges),
                        'grounded': sum(g.grounding_status == 'grounded' for g in grounded),
                        'exact': sum(e['exact_text_match'] for e in evidence)})
    verify_snapshot(root)
    write_json(root / 'artifacts/index-result.json', {'sources': results, 'modules': identity})
    return results


async def query_source(root, document_id, question, question_id, guard):
    from starlette.requests import Request
    from models import QueryRequest, QueryOptions
    import generator
    from routes.rag_query import rag_query
    identity = module_identity(root, ('generator', 'retrieval', 'routes', 'routes.rag_query', 'routes.query', 'prompt_builder'))
    trace = {}
    original_generate = generator.RAGGenerator.generate

    def generate(instance, *args, **kwargs):
        result = original_generate(instance, *args, **kwargs)
        trace['native_generator_result'] = result
        return result

    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/v1/rag/query', 'headers': []})
    request.state.user = {'user_id': 'development-admin', 'roles': ['admin'], 'auth_type': 'research_fixture'}
    generator.RAGGenerator.generate = generate
    try:
        with guard.phase('p0', question_id):
            result = await rag_query(QueryRequest(query=question, document_id=document_id,
                                    options=QueryOptions(language='ch', enabled_sources=['kg'], include_evidence_trace=True)), request)
    finally:
        generator.RAGGenerator.generate = original_generate
    artifact = {'arm': 'P0_NATIVE_SCOPED_KG', 'question_id': question_id, 'document_id': document_id,
                'authorization': 'ASGI Request administrator fixture; not JWT/HTTP verification',
                'response': result.model_dump(mode='json'), 'trace': trace, 'modules': identity}
    write_json(checked_path(root, Path(root) / 'artifacts' / f'{question_id}.p0.json'), artifact)
    verify_snapshot(root)
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'preflight', 'index', 'query'))
    parser.add_argument('--repo-root'); parser.add_argument('--run-root', required=True)
    parser.add_argument('--sources'); parser.add_argument('--pdf-xml'); parser.add_argument('--ledger')
    parser.add_argument('--document-id'); parser.add_argument('--question'); parser.add_argument('--question-id')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.repo_root, args.run_root)
        print(json.dumps({'status': 'PREPARED'}, ensure_ascii=False)); return
    root = activate(args.run_root)
    if args.command == 'preflight':
        result = preflight_sources(root, args.sources, args.pdf_xml)
        print(json.dumps({k: result[k] for k in ('mode', 'planned_requests', 'planned_input_bytes')}, ensure_ascii=False)); return
    from research.development_budget import BudgetGuard
    guard = BudgetGuard(args.ledger, os.environ.get('LANGEXTRACT_API_KEY', ''))
    # Safe boundary: suppress upstream exception text and never print keys.
    try:
        with guard.install():
            if args.command == 'index':
                index_sources(root, args.sources, args.pdf_xml, guard)
            else:
                import asyncio
                asyncio.run(query_source(root, args.document_id, args.question, args.question_id, guard))
            if guard.closed:
                raise RuntimeError('模型预算已关闭，原生回退不能记成功')
    except Exception as exc:
        print(json.dumps({'status': 'FAILED', 'error_type': type(exc).__name__}, ensure_ascii=False))
        raise SystemExit(1) from None
    print(json.dumps({'status': 'COMPLETED', 'actual_attempts': guard.actual_attempts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
