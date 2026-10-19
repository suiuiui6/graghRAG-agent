"""Fail-closed, persistent HTTP budget for the authorized public development pilot.

Use one artifact directory across index, P0 and A processes. This is an audited
transport adapter, not an operating-system network or filesystem sandbox.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


class BudgetStopped(RuntimeError):
    """A safe message that never embeds upstream response or exception text."""


def openai_transport_module():
    """Resolve the installed SDK transport, including the httpx2 SDK fork."""
    import openai._base_client as base_client
    candidates = [getattr(base_client, name, None) for name in ('httpx', 'httpx2')]
    modules = [m for m in candidates if m is not None and hasattr(m, 'Client') and hasattr(m, 'MockTransport')]
    if len(modules) != 1:
        raise BudgetStopped('无法唯一核定实际OpenAI SDK传输模块')
    return modules[0]


def http_transport_modules():
    import httpx
    sdk = openai_transport_module()
    return [httpx] if sdk is httpx else [httpx, sdk]


@dataclass(frozen=True)
class BudgetLimits:
    total_attempts: int = 72
    index_attempts: int = 40
    p0_attempts: int = 18
    a_attempts: int = 14
    input_bytes: int = 1_200_000
    window_seconds: int = 1800


class BudgetGuard:
    def __init__(self, artifact_dir: str | Path, key: str, limits: BudgetLimits | None = None):
        if not key:
            raise ValueError('运行需要环境注入的密钥')
        self.directory = Path(artifact_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.key = key
        self.limits = limits or BudgetLimits()
        self.lock = threading.RLock()
        self.phase_name = None
        self.question_id = None
        self.phase_deadline = None
        self.path = self.directory / 'ledger.json'
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if self.state['limits'] != asdict(self.limits):
                raise BudgetStopped('既有预算配置不一致')
            if any(r['status'] == 'SENT_PENDING' for r in self.state['records']):
                self.state['closed'] = True
                self.state['stop_reason'] = '既有请求结果未知，禁止自动恢复'
                self._save()
        else:
            self.state = {'schema_version': 1, 'limits': asdict(self.limits),
                          'started_epoch': time.time(), 'actual_attempts': 0,
                          'input_bytes': 0, 'phase_attempts': {'index': 0, 'p0': 0, 'a': 0},
                          'closed': False, 'records': []}
            self._save()

    @property
    def actual_attempts(self):
        return self.state['actual_attempts']

    @property
    def closed(self):
        return self.state['closed']

    def _sanitize(self, value):
        # Replace the actual secret even if the remote endpoint echoes it inside
        # ordinary answer/error text. No headers or raw exceptions are retained.
        if isinstance(value, str):
            return value.replace(self.key, '[REDACTED]')
        if isinstance(value, list):
            return [self._sanitize(x) for x in value]
        if isinstance(value, dict):
            return {k: ('[REDACTED]' if k.lower() in {'authorization', 'api_key', 'apikey', 'secret'} else self._sanitize(v)) for k, v in value.items()}
        return value

    def _save(self):
        temporary = self.path.with_suffix('.pending')
        temporary.write_text(json.dumps(self._sanitize(self.state), ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def _reject(self, reason):
        self.state['closed'] = True
        self.state['stop_reason'] = reason
        self.state['records'].append({'status': 'NOT_SENT', 'phase': self.phase_name,
                                      'question_id': self.question_id, 'reason': reason,
                                      'epoch': time.time()})
        self._save()
        raise BudgetStopped(reason)

    @contextlib.contextmanager
    def phase(self, name, question_id=None):
        normalized = name.lower()
        if normalized not in {'index', 'p0', 'a'}:
            raise ValueError('未知预算轨道')
        old = self.phase_name, self.question_id, self.phase_deadline
        self.phase_name, self.question_id = normalized, question_id
        duration = {'index': 600, 'p0': 120, 'a': 45}[normalized]
        self.phase_deadline = time.time() + duration
        try:
            yield self
        finally:
            self.phase_name, self.question_id, self.phase_deadline = old

    def _begin(self, url, raw, transport):
        with self.lock:
            if self.closed:
                self._reject('预算已关闭，拒绝后续请求')
            parsed = urlsplit(str(url))
            if parsed.scheme != 'https' or parsed.hostname != 'api.deepseek.com' or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'/chat/completions', '/v1/chat/completions'}:
                self._reject('非授权官方模型端点')
            if self.phase_name is None:
                self._reject('请求未绑定索引或查询轨道')
            try:
                wire_utf8 = raw.decode('utf-8')
                data = json.loads(wire_utf8)
            except (ValueError, TypeError):
                self._reject('请求不是有效JSON')
            if not isinstance(data, dict):
                self._reject('请求JSON顶层必须对象')
            max_tokens = data.get('max_tokens')
            phase_cap = 4096 if self.phase_name == 'index' else 2048
            if data.get('model') != 'deepseek-flash' or data.get('thinking') != {'type': 'disabled'} or type(max_tokens) is not int or not 0 < max_tokens <= phase_cap or not isinstance(data.get('messages'), list) or data.get('stream', False):
                self._reject('模型、thinking、输出限额或messages不符合契约')
            if self.phase_name == 'index' and max_tokens != 4096:
                self._reject('索引输出限额必须4096')
            if self.key.encode() in raw or self.key in json.dumps(data, ensure_ascii=False):
                self._reject('密钥不得进入模型输入')
            remaining = min(self.state['started_epoch'] + self.limits.window_seconds, self.phase_deadline) - time.time()
            phase_limit = getattr(self.limits, self.phase_name + '_attempts')
            if remaining <= 0 or self.actual_attempts >= self.limits.total_attempts or self.state['phase_attempts'][self.phase_name] >= phase_limit or self.state['input_bytes'] + len(raw) > self.limits.input_bytes:
                self._reject('请求数、输入字节或时间预算耗尽')
            record = {'id': self.actual_attempts + 1, 'phase': self.phase_name,
                      'question_id': self.question_id, 'transport': transport,
                      'status': 'SENT_PENDING', 'cost_status': 'UNKNOWN',
                      'epoch': time.time(), 'input_bytes': len(raw),
                      'request_sha256': hashlib.sha256(raw).hexdigest(),
                      'request_wire_utf8': wire_utf8,
                      'request': self._sanitize(data)}
            self.state['records'].append(record)
            self.state['actual_attempts'] += 1
            self.state['phase_attempts'][self.phase_name] += 1
            self.state['input_bytes'] += len(raw)
            self._save()  # Reserve before touching the actual transport.
            return record, min(30 if self.phase_name != 'a' else 45, remaining)

    def _finish(self, record, status, raw):
        with self.lock:
            record['elapsed_seconds'] = time.time() - record['epoch']
            record['http_status'] = status
            record['response_sha256'] = hashlib.sha256(raw).hexdigest()
            try:
                wire_utf8 = raw.decode('utf-8')
                data = json.loads(wire_utf8)
            except (ValueError, TypeError):
                data = None
            secret_detected = self.key.encode() in raw or (data is not None and self.key in json.dumps(data, ensure_ascii=False))
            # Error diagnostics are never evidence: omit their entire body.
            # A successful response that echoes the key must not reach native
            # parsers, grounding, generation repair, or another model prompt.
            record['response'] = (self._sanitize(data) if status == 200 and data is not None and not secret_detected
                                  else {'body_omitted': True, 'secret_detected': secret_detected})
            usage = data.get('usage') if isinstance(data, dict) else None
            valid_usage = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            if valid_usage and usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                valid_usage = False
            if valid_usage:
                record['usage'] = usage
                record['cost_status'] = 'KNOWN'
            choices = data.get('choices') if isinstance(data, dict) else None
            valid_choices = isinstance(choices, list) and bool(choices) and all(isinstance(c, dict) for c in choices)
            finish = [c.get('finish_reason') for c in choices] if valid_choices else []
            valid_content = valid_choices and all(isinstance(c.get('message'), dict)
                and isinstance(c['message'].get('content'), str) and c['message']['content'].strip() for c in choices)
            record['finish_reasons'] = finish
            record['status'] = 'COMPLETED' if status == 200 and valid_usage and valid_content and not secret_detected and finish and all(x == 'stop' for x in finish) else 'FAILED_CLOSED'
            if record['status'] == 'COMPLETED':
                record['response_wire_utf8'] = wire_utf8
            if record['status'] != 'COMPLETED':
                self.state['closed'] = True
                self.state['stop_reason'] = 'HTTP失败、usage缺失或输出未正常结束'
            self._save()
            if self.closed:
                raise BudgetStopped(self.state['stop_reason'])

    def _failed(self, record):
        with self.lock:
            record['status'] = 'FAILED_CLOSED'
            record['elapsed_seconds'] = time.time() - record['epoch']
            self.state['closed'] = True
            self.state['stop_reason'] = '传输异常，可能已发送，成本未知'
            self._save()

    @contextlib.contextmanager
    def install(self):
        """Patch actual requests/httpx transports, including instantiated SDK clients.

        A lock file refuses concurrent processes; sequential commands recover the
        same cumulative ledger. Redirects are forcibly disabled before send.
        """
        import requests
        modules = http_transport_modules()
        lock_path = self.directory / 'transport.lock'
        try:
            handle = lock_path.open('x', encoding='utf-8')
        except FileExistsError:
            raise BudgetStopped('预算目录已被另一运行或异常退出占用') from None
        handle.close()
        try:
            # Another sequential command may have completed after construction
            # but before this process acquired its execution lock.
            latest = json.loads(self.path.read_text(encoding='utf-8'))
            if latest['limits'] != asdict(self.limits):
                raise BudgetStopped('既有预算配置不一致')
            self.state = latest
            if any(r['status'] == 'SENT_PENDING' for r in self.state['records']):
                self.state['closed'] = True
                self.state['stop_reason'] = '既有请求结果未知，禁止自动恢复'
                self._save()
        except Exception:
            lock_path.unlink()
            raise
        old_requests = requests.Session.send
        old_sends = [(m, m.Client.send, m.AsyncClient.send) for m in modules]
        guard = self

        def requests_send(session, request, **kwargs):
            raw = request.body or b''
            if isinstance(raw, str): raw = raw.encode('utf-8')
            record, timeout = guard._begin(request.url, raw, 'requests')
            kwargs.update(allow_redirects=False, timeout=timeout)
            try:
                result = old_requests(session, request, **kwargs)
            except Exception:
                guard._failed(record)
                raise BudgetStopped('模型传输失败，预算关闭') from None
            guard._finish(record, result.status_code, result.content)
            return result

        def sync_wrapper(original, name):
            def send(client, request, **kwargs):
                record, timeout = guard._begin(request.url, request.read(), name)
                request.extensions['timeout'] = dict.fromkeys(('connect', 'read', 'write', 'pool'), timeout)
                kwargs.update(follow_redirects=False, stream=False)
                try:
                    result = original(client, request, **kwargs)
                except Exception:
                    guard._failed(record)
                    raise BudgetStopped('模型传输失败，预算关闭') from None
                guard._finish(record, result.status_code, result.content)
                return result
            return send

        def async_wrapper(original, name):
            async def send(client, request, **kwargs):
                record, timeout = guard._begin(request.url, await request.aread(), name + '_async')
                request.extensions['timeout'] = dict.fromkeys(('connect', 'read', 'write', 'pool'), timeout)
                kwargs.update(follow_redirects=False, stream=False)
                try:
                    result = await original(client, request, **kwargs)
                except Exception:
                    guard._failed(record)
                    raise BudgetStopped('模型传输失败，预算关闭') from None
                guard._finish(record, result.status_code, result.content)
                return result
            return send

        requests.Session.send = requests_send
        for module, sync, asynchronous in old_sends:
            module.Client.send = sync_wrapper(sync, module.__name__)
            module.AsyncClient.send = async_wrapper(asynchronous, module.__name__)
        try:
            yield self
        finally:
            requests.Session.send = old_requests
            for module, sync, asynchronous in old_sends:
                module.Client.send, module.AsyncClient.send = sync, asynchronous
            lock_path.unlink()
