"""脱敏处理器语料测试：该脱的必须脱，不该脱的不能动。"""
import io
import json
import logging
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# 真 structlog 由 conftest.py 在任何测试模块之前 import 保证 ——
# 否则 test_community_global_mode / test_kg_indexed_recall 的模块级 stub 会先
# 占住 sys.modules["structlog"]，使 logging_config 绑定到假模块、get_logger()
# 退化成 no-op（已实测：全量跑失败、单独跑通过）。修复见 tests/conftest.py。
import logging_config


@pytest.fixture
def capture():
    logging_config.setup_logging("/tmp/test_redact_logs")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
    yield lambda: json.loads(buf.getvalue().strip().splitlines()[-1])
    logging.getLogger().removeHandler(handler)


@pytest.mark.parametrize("key", [
    "api_key", "apiKey", "access_token", "secret", "password", "passwd",
    "authorization", "Authorization", "credential", "client_secret", "file_access_token",
])
def test_sensitive_keys_are_redacted(capture, key):
    logging_config.get_logger("t").info("probe", **{key: "SUPER-SECRET-VALUE"})
    assert capture()[key] == "[REDACTED]", f"{key} 未脱敏"


def test_value_patterns_redacted_under_innocent_key(capture):
    """键名无害但值是密钥形态 —— 仍须脱敏。"""
    logging_config.get_logger("t").info("probe", note="Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    assert "[REDACTED]" in capture()["note"]


@pytest.mark.parametrize("value", [
    "sk-18f75f426082414ebd0ef1662ae2c6d7",
    "sk-abcd1234efgh5678",
    "LTAI5t7DjHhjuhJ596MXHV3P",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
])
def test_known_secret_shapes_redacted(capture, value):
    logging_config.get_logger("t").info("probe", blob=value)
    assert "[REDACTED]" in capture()["blob"]


def test_nested_dicts_are_scrubbed(capture):
    logging_config.get_logger("t").info("probe", outer={"inner": {"token": "X"}})
    assert capture()["outer"]["inner"]["token"] == "[REDACTED]"


def test_lists_are_scrubbed(capture):
    logging_config.get_logger("t").info("probe", items=[{"api_key": "X"}, "Bearer abcdefghijklmnop"])
    got = capture()["items"]
    assert got[0]["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in got[1]


def test_exc_info_secret_is_scrubbed_and_traceback_survives(capture):
    """requests/httpx 会把 Authorization 头写进异常 repr，traceback 字符串必须脱敏；
    但同时**必须保留 traceback** —— 整条丢掉比泄露更糟（诊断价值归零）。

    保护机制是**值扫描**而非键名：format_exc_info 在 redact_sensitive 之前
    已把 exc_info 键改名为 exception，故键名规则对 traceback 无效。
    """
    try:
        raise ValueError("auth failed for Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    except ValueError:
        logging_config.get_logger("t").error("boom", exc_info=True)
    entry = capture()
    rendered = json.dumps(entry)
    # 密钥形态被替换
    assert "eyJhbGciOiJIUzI1NiJ9" not in rendered
    assert "[REDACTED]" in rendered
    # traceback 本体仍在（否则本特性毫无诊断价值）
    assert "exception" in entry, "traceback 字段丢失"
    assert "Traceback" in entry["exception"] or "ValueError" in entry["exception"]
    assert "auth failed for" in entry["exception"]


def test_presigned_url_is_redacted(capture):
    """预签名 URL 的**签名**必须被脱敏（2026-09-18 实测此处曾泄出）。

    背景：MinerU 直传要先用 `POST /file/v4/file-urls/batch` 拿预签名上传 URL，
    该 URL 内嵌签名，过期前可写对应对象 —— 是凭据，不是普通 URL。
    而**键名规则抓不到它**（键叫 `upload_url` / `file_url`，不含 token/key/
    signature 段），只有值扫描能拦。

    实测教训：`OSSAccessKeyId=LTAI5t7...` 恰被 LTAI 规则拦到，但
    `Signature=...` 完好泄出 —— 所以本测试断言的是 **Signature 的值**，
    那才是真正的凭据。（只断言 "URL 里有 [REDACTED]" 是**空转**的：
    LTAI 规则会让它通过，即使签名规则缺失。）
    """
    secret_sig = "abcdef1234567890deadbeef"
    for url in (
        # 阿里云 OSS 预签名（MinerU 的 batch 上传 URL 就是这种）
        f"https://mineru.oss-cn-shanghai.aliyuncs.com/b/x.pdf"
        f"?Expires=1790000000&OSSAccessKeyId=LTAI5t7DjHhjuhJ596MXHV3P"
        f"&Signature={secret_sig}",
        # S3 形态
        f"https://s3.amazonaws.com/b/x.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        f"&X-Amz-Signature={secret_sig}&X-Amz-Expires=3600",
    ):
        logging_config.get_logger("t").info("upload_url_applied", upload_url=url)
        rendered = json.dumps(capture())
        assert secret_sig not in rendered, f"签名值泄出：{rendered[:200]}"
        assert "[REDACTED]" in rendered


def test_presigned_url_in_message_string_is_redacted(capture):
    """签名被内插进消息字符串（而非作为 kwarg）时同样要拦。

    这类写法最容易被顺手写出来：logger.info(f"uploading to {url}")。
    """
    secret_sig = "feedfacecafebabe1234"
    url = f"https://x.oss-cn-hangzhou.aliyuncs.com/a.pdf?Signature={secret_sig}"
    logging_config.get_logger("t").info(f"uploading to {url}")
    assert secret_sig not in json.dumps(capture())


def test_presigned_pattern_does_not_over_redact_plain_urls(capture):
    """反向断言：普通（无签名）URL 不得被误脱敏，否则日志失去排障价值。"""
    plain = "https://mineru.net/api/v4/extract/task"
    logging_config.get_logger("t").info("endpoint", url=plain)
    assert capture()["url"] == plain


@pytest.mark.parametrize("key", ["task_id", "stage", "latency_ms", "path", "request_id", "node_count"])
def test_benign_fields_are_not_redacted(capture, key):
    """反向断言：过度脱敏会让日志失去诊断价值。"""
    logging_config.get_logger("t").info("probe", **{key: "sensible-value"})
    assert capture()[key] == "sensible-value", f"{key} 被误脱敏"


def test_benign_value_containing_sk_prefix_survives_rest(capture):
    """值里嵌了 sk- 形态时只替换命中片段，其余内容保留。"""
    logging_config.get_logger("t").info("probe", note="entity sk-abcd1234efgh5678 appeared on page 3")
    got = capture()["note"]
    assert "[REDACTED]" in got
    assert "appeared on page 3" in got


def test_depth_bound_prevents_runaway(capture):
    deep = cur = {}
    for _ in range(12):
        cur["n"] = {}
        cur = cur["n"]
    cur["token"] = "X"
    logging_config.get_logger("t").info("probe", deep=deep)   # 不得栈溢出或超时
    assert "probe" == capture()["event"]
