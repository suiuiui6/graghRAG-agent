from retrieval import preprocess_query


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyCache:
    def get(self, cache_key):
        return None

    def set(self, cache_key, payload):
        return None


def test_preprocess_query_rejects_generic_english_rewrite_for_chinese_title_query(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"rewritten":"enterprise project report analysis","intent":"hybrid","entity_types":["project_metadata","metric"]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("retrieval.get_query_rewrite_cache", lambda path=None: DummyCache())

    result = preprocess_query("这篇论文的标题是什么？", api_key="x", base_url="https://example.com")

    assert result.rewritten == "这篇论文的标题是什么？"
    assert "paper_metadata" in result.entity_types


def test_preprocess_query_rejects_generic_project_report_rewrite_for_alias_query(monkeypatch):
    def fake_post(*args, **kwargs):
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"rewritten":"wind 4 solar 1 project report","intent":"metric","entity_types":["project_metadata","metric"]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("retrieval.get_query_rewrite_cache", lambda path=None: DummyCache())

    result = preprocess_query("论文中提到的wind 4 solar 1场景代表什么含义?", api_key="x", base_url="https://example.com")

    assert result.rewritten == "论文中提到的wind 4 solar 1场景代表什么含义? (W4S1)"
    assert "dataset" in result.entity_types


def test_preprocess_query_rejects_bad_cached_rewrite(monkeypatch):
    class BadCache:
        def get(self, cache_key):
            return {
                "original": "这篇论文的标题是什么？",
                "rewritten": "enterprise project report analysis",
                "intent": "hybrid",
                "entity_types": ["project_metadata", "metric"],
                "table_conditions": [],
            }

        def set(self, cache_key, payload):
            return None

    monkeypatch.setattr("retrieval.get_query_rewrite_cache", lambda path=None: BadCache())

    result = preprocess_query("这篇论文的标题是什么？", api_key="x", base_url="https://example.com")

    assert result.rewritten == "这篇论文的标题是什么？"
    assert "paper_metadata" in result.entity_types
