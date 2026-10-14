"""Bounded standalone research adapter. Default dry run; no production imports.

Only --execute dispatches requests. Each of 9 questions has B1/B2/B3; there
is no retry, resume, fallback, routing experiment, or scientific auto-scoring.
The freeze manifest records current production drift without modifying it.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

import httpx

MODEL = 'deepseek-v4-pro'
ENDPOINT = 'https://api.deepseek.com/chat/completions'
PILOT_DIR = Path('docs/superpowers/plans/scope-pilot')
MAX_REQUESTS = 27
BUDGET = 8192


class PilotError(ValueError):
    """Safe static error: never contains credential or provider body."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def under(root, path):
    root = Path(root).resolve()
    path = Path(path)
    path = (path if path.is_absolute() else root / path).resolve()
    if path == root or not path.is_relative_to(root):
        raise PilotError('PATH_OUTSIDE_ALLOWED_DIRECTORY')
    return path


def verify_guards(root, guards):
    if not isinstance(guards, dict):
        raise PilotError('INVALID_GUARDS')
    for name, expected in guards.items():
        path = under(root, name)
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise PilotError('INVALID_GUARD_HASH')
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise PilotError('GUARD_HASH_DRIFT')


def filter_source(text):
    """Replace excluded line characters with newlines to retain source offsets."""
    excluded = []
    offset = 0
    output = []
    for line in text.splitlines(keepends=True):
        if '参赛编号' in line:
            excluded.append({'start': offset, 'end': offset + len(line),
                             'reason': 'participant_number_line'})
            output.append('\n' * len(line))
        else:
            output.append(line)
        offset += len(line)
    return ''.join(output), excluded


def surviving_spans(parts, original, exclusions):
    result = []
    for part in parts:
        cursor, end = part['start'], part['end']
        for exclusion in exclusions:
            left, right = exclusion['start'], exclusion['end']
            if right <= cursor or left >= end:
                continue
            if cursor < left:
                result.append({'start': cursor, 'end': left, 'text': original[cursor:left]})
            cursor = max(cursor, right)
        if cursor < end:
            result.append({'start': cursor, 'end': end, 'text': original[cursor:end]})
    return result


def make_payload(instruction, doc, query, contexts):
    return {'model': MODEL, 'messages': [
        {'role': 'system', 'content': instruction},
        {'role': 'user', 'content': canonical({'document': doc, 'query': query,
                                             'source_contexts': contexts})}],
        'thinking': {'type': 'disabled'}, 'temperature': 0,
        'max_tokens': 2048, 'stream': False}


def prepare(root, manifest_path):
    root = Path(root).resolve()
    manifest_path = under(root, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or not manifest.get('guard_files'):
        raise PilotError('INVALID_MANIFEST')
    guards = manifest['guard_files']
    verify_guards(root, guards)
    required = {str(PILOT_DIR / name).replace('\\', '/') for name in
                ('pilot.py', 'gold.yaml', 'inputs-B2.json')}
    normalized = {name.replace('\\', '/') for name in guards}
    if not required <= normalized:
        raise PilotError('MISSING_PILOT_GUARDS')
    spec = manifest.get('run_spec', {})
    for key, expected in {'model': MODEL, 'max_requests': 27,
                          'budget_utf8_bytes': BUDGET,
                          'baselines': ['B1', 'B2', 'B3']}.items():
        if key in spec and spec[key] != expected:
            raise PilotError('RUN_SPEC_MISMATCH')
    pilot_path = root / PILOT_DIR / 'pilot.py'
    module_spec = importlib.util.spec_from_file_location('_scope_pilot_offline', pilot_path)
    pilot = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(pilot)
    data = pilot.load_gold()
    if pilot.validate_gold(data):
        raise PilotError('GOLD_VALIDATION_FAILED')
    questions = data['questions']
    if len(questions) != 9 or len({q['id'] for q in questions}) != 9:
        raise PilotError('EXACTLY_NINE_QUESTIONS_REQUIRED')
    for meta in data['documents'].values():
        if meta['path'].replace('\\', '/') not in normalized:
            raise PilotError('MISSING_SOURCE_GUARD')
    instruction = json.loads((root / PILOT_DIR / 'inputs-B2.json').read_text(encoding='utf-8'))['system_instruction']
    if not isinstance(instruction, str) or not instruction:
        raise PilotError('INVALID_SYSTEM_INSTRUCTION')
    originals, filtered, exclusions = {}, {}, {}
    for doc, meta in data['documents'].items():
        original = under(root, meta['path']).read_text(encoding='utf-8')
        originals[doc] = original
        filtered[doc], exclusions[doc] = filter_source(original)
    # This private module instance is not production state. Gold validation
    # used original sources; context selection sees uniformly filtered sources.
    pilot.source = lambda unused_data, q: filtered[q['doc']]
    rows = []
    for q in questions:
        for baseline in ('B1', 'B2', 'B3'):
            parts, status = pilot.contexts(data, q, baseline, BUDGET)
            if status != 'READY':
                raise PilotError('CONTEXT_NOT_READY')
            parts = surviving_spans(parts, originals[q['doc']], exclusions[q['doc']])
            for part in parts:
                if originals[q['doc']][part['start']:part['end']] != part['text']:
                    raise PilotError('SOURCE_SPAN_MISMATCH')
            if sum(len(p['text'].encode('utf-8')) for p in parts) > BUDGET:
                raise PilotError('CONTEXT_BUDGET_EXCEEDED')
            rows.append({'qid': q['id'], 'doc': q['doc'], 'baseline': baseline,
                         'status': 'NOT_ATTEMPTED', 'context_status': status,
                         'source_sha256': data['documents'][q['doc']]['sha256'],
                         'payload': make_payload(instruction, q['doc'], q['query'], parts)})
    return {'schema_version': 1, 'manifest_sha256': digest(manifest_path.read_bytes()),
            'manifest_path': manifest_path.relative_to(root).as_posix(),
            'guard_files': guards, 'production_hash_drift': manifest.get('production_hash_drift', []),
            'scope_resolution': 'ORACLE_RESOLVED_B2_B3_NOT_AUTOMATIC_ROUTING',
            'budget_type': 'UTF8_BYTES_NOT_TOKENS', 'budget': BUDGET,
            'source_exclusions': exclusions, 'rows': rows}


def credentials(root):
    from dotenv import dotenv_values
    values = dotenv_values(Path(root) / 'backend/.env', interpolate=False)
    key = values.get('LANGEXTRACT_API_KEY')
    parsed = urlsplit(values.get('LANGEXTRACT_BASE_URL') or '')
    if (parsed.scheme != 'https' or parsed.hostname != 'api.deepseek.com'
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/', '/v1', '/v1/')):
        raise PilotError('OFFICIAL_BASE_URL_REQUIRED')
    if not isinstance(key, str) or not key.strip() or any(c.isspace() for c in key):
        raise PilotError('PRIVATE_CREDENTIAL_REQUIRED')
    return key


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as file:
        file.write(canonical(value) + '\n')
        file.flush()
        os.fsync(file.fileno())


def stamp():
    return datetime.now(timezone.utc).isoformat()


def validate_plan(plan):
    rows = plan.get('rows', [])
    if len(rows) != MAX_REQUESTS:
        raise PilotError('EXACTLY_27_REQUESTS_REQUIRED')
    pairs = {(row['qid'], row['baseline']) for row in rows}
    qids = {row['qid'] for row in rows}
    if len(qids) != 9 or pairs != {(q, b) for q in qids for b in ('B1', 'B2', 'B3')}:
        raise PilotError('INVALID_REQUEST_MATRIX')
    for row in rows:
        payload = row['payload']
        fixed = {'model': MODEL, 'thinking': {'type': 'disabled'}, 'temperature': 0,
                 'max_tokens': 2048, 'stream': False}
        if set(payload) != set(fixed) | {'messages'} or any(payload.get(k) != v for k, v in fixed.items()):
            raise PilotError('INVALID_FIXED_PAYLOAD')
        messages = payload['messages']
        if len(messages) != 2 or [m.get('role') for m in messages] != ['system', 'user']:
            raise PilotError('INVALID_MESSAGES')
        content = json.loads(messages[1]['content'])
        if set(content) != {'document', 'query', 'source_contexts'}:
            raise PilotError('INVALID_CONTEXT_PAYLOAD')
        if any(set(p) != {'start', 'end', 'text'} or '参赛编号' in p['text'] for p in content['source_contexts']):
            raise PilotError('INVALID_CONTEXT_SPANS')
        if sum(len(p['text'].encode('utf-8')) for p in content['source_contexts']) > BUDGET:
            raise PilotError('CONTEXT_BUDGET_EXCEEDED')


def run(plan, root, output_dir, execute=False, credential=None, transport=None):
    root = Path(root).resolve()
    output = under(root / PILOT_DIR / 'api-runs', output_dir)
    validate_plan(plan)
    verify_guards(root, plan['guard_files'])
    def verify_manifest():
        if 'manifest_path' in plan:
            path = under(root, plan['manifest_path'])
            if digest(path.read_bytes()) != plan['manifest_sha256']:
                raise PilotError('MANIFEST_HASH_DRIFT')
    verify_manifest()
    key = (credential or credentials(root)) if execute else None
    if key and key in canonical(plan):
        raise PilotError('SECRET_IN_PAYLOAD')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError:
        raise PilotError('OUTPUT_ALREADY_EXISTS') from None
    write_new(output / 'plan.json', plan)
    statuses = [{'index': i, 'qid': row['qid'], 'baseline': row['baseline'],
                 'status': 'NOT_ATTEMPTED'} for i, row in enumerate(plan['rows'])]
    write_new(output / 'initial-statuses.json', statuses)
    journal = (output / 'journal.jsonl').open('x', encoding='utf-8', newline='\n')
    def record(value):
        journal.write(canonical(value) + '\n')
        journal.flush()
        os.fsync(journal.fileno())
    try:
        if execute:
            with httpx.Client(timeout=httpx.Timeout(90), trust_env=False, follow_redirects=False,
                              transport=transport) as client:
                for i, row in enumerate(plan['rows']):
                    if i >= MAX_REQUESTS:
                        raise PilotError('HARD_REQUEST_LIMIT')
                    try:
                        verify_guards(root, plan['guard_files'])
                        verify_manifest()
                    except PilotError:
                        record({'event': 'STOP', 'index': i, 'error': 'GUARD_HASH_DRIFT'})
                        break
                    payload = row['payload']
                    request_hash = digest(canonical(payload).encode('utf-8'))
                    started_at = stamp()
                    record({'event': 'ATTEMPT_INTENT', 'index': i,
                            'request_sha256': request_hash, 'timestamp': started_at})
                    statuses[i]['status'] = 'ATTEMPTED_UNCONFIRMED'
                    begin = time.monotonic()
                    error = None
                    raw = None
                    try:
                        result = client.post(ENDPOINT, json=payload,
                                             headers={'Authorization': 'Bearer ' + key})
                        if result.status_code != 200:
                            error = 'HTTP_' + str(result.status_code)
                        elif key in result.text:
                            error = 'SECRET_REFLECTION'
                        else:
                            raw = result.json()
                            if not isinstance(raw, dict):
                                error = 'MALFORMED_RESPONSE'
                            elif raw.get('model') != MODEL:
                                error = 'MODEL_MISMATCH'
                            else:
                                choices = raw.get('choices')
                                if not isinstance(choices, list) or len(choices) != 1:
                                    raise ValueError('invalid choices shape')
                                choice = choices[0]
                                if (not isinstance(choice, dict)
                                        or 'finish_reason' not in choice
                                        or not isinstance(choice.get('message'), dict)
                                        or 'content' not in choice['message']):
                                    raise ValueError('invalid choice shape')
                                content = choice['message']['content']
                                if choice.get('finish_reason') != 'stop':
                                    error = 'INVALID_FINISH_REASON'
                                elif not isinstance(content, str) or not content.strip():
                                    error = 'EMPTY_ANSWER'
                                elif key in canonical(raw):
                                    error = 'SECRET_REFLECTION'
                    except httpx.HTTPError as exc:
                        error = type(exc).__name__
                    except (ValueError, TypeError, KeyError, IndexError):
                        error = 'MALFORMED_RESPONSE'
                    metadata = {'index': i, 'request_sha256': request_hash,
                                'timestamp': started_at, 'latency_seconds': time.monotonic() - begin}
                    if error:
                        statuses[i]['status'] = 'FAILED'
                        statuses[i]['error'] = error
                        record({'event': 'FAILED', **metadata, 'error': error})
                        break
                    write_new(output / f'{i:03d}-response.json', raw)
                    metadata.update({'provider_model': raw['model'], 'usage': raw.get('usage'),
                                     'system_fingerprint': raw.get('system_fingerprint')})
                    write_new(output / f'{i:03d}-metadata.json', metadata)
                    statuses[i]['status'] = 'SUCCESS'
                    record({'event': 'SUCCESS', **metadata})
        write_new(output / 'final-statuses.json', statuses)
        counts = dict(Counter(row['status'] for row in statuses))
        write_new(output / 'summary.json', {'execute': execute, 'counts': counts,
                                          'scientific_scoring': 'NOT_PERFORMED'})
        return counts
    finally:
        journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(PILOT_DIR / 'api-freeze-v1.json'))
    parser.add_argument('--output-dir')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output_dir or str(root / PILOT_DIR / 'api-runs' /
                                    datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    try:
        sys.stdout.write(canonical(run(prepare(root, args.manifest), root, output, execute=args.execute)) + '\n')
    except (PilotError, OSError, ValueError, TypeError, KeyError, ImportError):
        sys.stderr.write('STOPPED: validation or local preparation failed\n')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
