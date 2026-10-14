"""Exact source matching and read-only Chroma snapshot audit, without Chroma imports.

No offset repair or corpus ingestion. A text match does not establish document
identity, production retrieval membership, citation entailment or absence.
"""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sqlite3


def _normalize(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


def map_text(source_text, chunk_text, stored_span=None):
    source, chunk = _normalize(source_text), _normalize(chunk_text)
    candidates = []
    if chunk:
        cursor = 0
        while True:
            start = source.find(chunk, cursor)
            if start < 0:
                break
            candidates.append([start, start + len(chunk)])
            cursor = start + 1  # Preserve overlapping candidates.
    verified = False
    if stored_span is not None:
        if isinstance(stored_span, (tuple, list)) and len(stored_span) == 2:
            a, b = stored_span
            verified = (type(a) is int and type(b) is int and 0 <= a < b <= len(source)
                        and bool(chunk) and source[a:b] == chunk)
    if verified:
        status, resolved = 'EXACT_STORED_SPAN', list(stored_span)
    elif len(candidates) > 1:
        status, resolved = 'AMBIGUOUS_TEXT_MATCH', None
    elif len(candidates) == 1:
        status = ('UNIQUE_TEXT_MATCH_STORED_SPAN_INVALID' if stored_span is not None
                  else 'UNIQUE_EXACT_TEXT_MATCH')
        resolved = candidates[0] if stored_span is None else None
    else:
        status, resolved = 'LOCATION_UNVERIFIED', None
    return {'status': status, 'stored_span_verified': verified,
            'candidates': candidates, 'resolved_span': resolved}


def _snapshot_hashes(path):
    # Sidecars matter for active WAL-backed snapshots; main DB alone is not identity.
    result = {}
    for suffix in ('', '-wal', '-shm'):
        target = Path(str(path) + suffix)
        result[suffix or 'database'] = (hashlib.sha256(target.read_bytes()).hexdigest()
                                      if target.exists() else None)
    return result


@contextmanager
def readonly_sqlite(path):
    path = Path(path).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        yield connection
    finally:
        connection.close()


def audit_chroma(path, sources, min_chars=20, collection=None):
    """Counts only; never exports original text or arbitrary stored metadata.

    min_chars bounds short accidental matches, not scientific identity proof.
    Unsupported schema raises sqlite3 errors; caller must not label it missing
    corpus. A selected collection filters this offline snapshot, not production.
    """
    if type(min_chars) is not int or min_chars < 1:
        raise ValueError('INVALID_MIN_CHARS')
    path = Path(path).resolve(strict=True)
    before = _snapshot_hashes(path)
    counts = {key: {'exact_substring_chunks': 0, 'unique_substring_chunks': 0,
                    'ambiguous_substring_chunks': 0, 'stored_span_verified_chunks': 0,
                    'invalid_stored_span_chunks': 0} for key in sources}
    texts = {key: _normalize(value) for key, value in sources.items()}
    with readonly_sqlite(path) as connection:
        collections = [{'name': name, 'dimension': dimension} for name, dimension in
                       connection.execute('SELECT name, dimension FROM collections ORDER BY name')]
        sql = '''SELECT e.id,e.embedding_id,c.name,m.key,m.string_value,m.int_value
                 FROM embeddings e JOIN segments s ON s.id=e.segment_id
                 JOIN collections c ON c.id=s.collection
                 JOIN embedding_metadata m ON m.id=e.id
                 WHERE m.key IN ('chroma:document','char_start','char_end')'''
        params = ()
        if collection is not None:
            sql += ' AND c.name=?'
            params = (collection,)
        sql += ' ORDER BY e.id,m.key'
        records = {}
        for internal_id, chunk_id, collection_name, key, string_value, int_value in connection.execute(sql, params):
            record = records.setdefault(internal_id, {})
            record[key] = string_value if key == 'chroma:document' else int_value
        checked = 0
        for record in records.values():
            chunk = record.get('chroma:document')
            if not isinstance(chunk, str) or len(_normalize(chunk).strip()) < min_chars:
                continue
            checked += 1
            stored = (record.get('char_start'), record.get('char_end'))
            for key, text in texts.items():
                mapped = map_text(text, chunk, stored)
                if mapped['candidates']:
                    stats = counts[key]
                    stats['exact_substring_chunks'] += 1
                    stats['unique_substring_chunks' if len(mapped['candidates']) == 1
                          else 'ambiguous_substring_chunks'] += 1
                    stats['stored_span_verified_chunks'] += int(mapped['stored_span_verified'])
                    stats['invalid_stored_span_chunks'] += int(not mapped['stored_span_verified'])
    after = _snapshot_hashes(path)
    unchanged = before == after
    return {'status': 'READ_ONLY_SNAPSHOT_AUDIT' if unchanged else 'SNAPSHOT_CHANGED_DURING_AUDIT',
            'database_unchanged': unchanged, 'hashes_before': before, 'hashes_after': after,
            'collections': collections, 'selected_collection': collection,
            'chunk_records': len(records), 'checked_nonempty_chunks': checked,
            'min_chars': min_chars, 'sources': counts,
            'runtime_membership': 'UNKNOWN',
            'interpretation': 'Text matches are not corpus identity; zero matches are not absence proof. '
                              'Invalid stored offsets are never repaired by this tool.'}
