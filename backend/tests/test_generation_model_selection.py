"""Model selection at request construction; transport is blocked and caches isolated."""
import json
import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import config
import conversation
import generator
import query_optimizer
import retrieval


@pytest.fixture
def transport(monkeypatch):
    bodies = []

    def post(_url, **kwargs):
        bodies.append(kwargs["json"])
        payload = {"rewritten": "设备状态", "intent": "hybrid", "entity_types": []}
        content = json.dumps(payload) if "User query:" in kwargs["json"]["messages"][0]["content"] else '["设备状态", "运行状态"]'
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    monkeypatch.setattr("requests.post", post)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "test-placeholder")
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://example.invalid")
    monkeypatch.setattr(retrieval, "get_query_rewrite_cache", lambda: SimpleNamespace(get=lambda _: None, set=lambda *_: None))
    monkeypatch.setattr(conversation, "runtime_cache_get", lambda *_: None)
    monkeypatch.setattr(conversation, "runtime_cache_put", lambda *_: None)
    return bodies


@pytest.mark.parametrize("env_model", [None, "deepseek-v4-pro", "configured-model"])
def test_all_request_paths_resolve_model_at_call_time(monkeypatch, transport, env_model):
    if env_model is None:
        monkeypatch.delenv("LANGEXTRACT_MODEL_ID", raising=False)
    else:
        monkeypatch.setenv("LANGEXTRACT_MODEL_ID", env_model)
    expected = env_model or "deepseek-flash"
    retrieval.preprocess_query("设备状态")
    retrieval._generate_query_variants("设备状态", None)
    conversation.resolve_coreference("它的状态", [{"role": "user", "content": "设备状态"}])
    query_optimizer._llm_resolve_pronouns("它的状态", [{"role": "user", "content": "设备状态"}], 3)
    generator.generate_answer([{"role": "user", "content": "设备状态"}])
    assert len(transport) == 5
    assert [body["model"] for body in transport] == [expected] * 5
    for body in transport:
        assert "extra_body" not in body
        if expected in {"deepseek-flash", "deepseek-v4-pro"}:
            assert body["thinking"] == {"type": "disabled"}
        else:
            assert "thinking" not in body
    assert generator.GenerationConfig().model == expected
    assert config.GenerationConfig().model == expected


def test_explicit_model_overrides_environment(monkeypatch, transport):
    monkeypatch.setenv("LANGEXTRACT_MODEL_ID", "configured-model")
    retrieval.preprocess_query("设备状态", model_name="explicit-model")
    conversation.resolve_coreference("它的状态", [{"role": "user", "content": "设备状态"}], model="explicit-model")
    generator.generate_answer([{"role": "user", "content": "设备状态"}], generator.GenerationConfig(model="explicit-model", api_key="test-placeholder", base_url="https://example.invalid"))
    assert len(transport) == 3
    assert [body["model"] for body in transport] == ["explicit-model"] * 3


def test_preprocess_cache_partition_follows_resolved_model(monkeypatch, transport):
    keys = []
    monkeypatch.setattr(retrieval, "get_query_rewrite_cache", lambda: SimpleNamespace(get=lambda key: keys.append(key), set=lambda *_: None))
    for model in ["model-a", "model-b", "model-a"]:
        monkeypatch.setenv("LANGEXTRACT_MODEL_ID", model)
        retrieval.preprocess_query("设备状态")
    assert keys[0] == keys[2]
    assert keys[0] != keys[1]
    assert [body["model"] for body in transport] == ["model-a", "model-b", "model-a"]


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro", "configured-model"])
def test_legacy_sdk_uses_extra_body_only_for_deepseek(monkeypatch, model):
    # Execute the exact request factory without loading unrelated agent dependencies.
    tree = ast.parse((Path(__file__).parents[1] / "routes" / "query.py").read_text(encoding="utf-8"))
    factory = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_get_model")
    namespace = {"os": os, "ChatOpenAI": lambda **kwargs: kwargs}
    if hasattr(config, "non_thinking_options"):
        namespace["non_thinking_options"] = config.non_thinking_options
    exec(compile(ast.Module(body=[factory], type_ignores=[]), "routes/query.py", "exec"), namespace)
    monkeypatch.setenv("LANGEXTRACT_MODEL_ID", model)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "test-placeholder")
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://example.invalid")
    options = namespace["_get_model"]()
    assert options["model"] == model
    assert "thinking" not in options
    if model in {"deepseek-flash", "deepseek-v4-pro"}:
        assert options["extra_body"] == {"thinking": {"type": "disabled"}}
    else:
        assert "extra_body" not in options


@pytest.mark.parametrize("module_name", ["pipeline.py", "worker.py"])
@pytest.mark.parametrize("model_id", ["deepseek-flash", "deepseek-v4-pro", "configured-model"])
def test_native_extraction_infer_serializes_non_thinking(monkeypatch, module_name, model_id):
    import httpx
    import openai
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "langextract"))
    from langextract.factory import ModelConfig
    from langextract.providers.openai import OpenAILanguageModel
    monkeypatch.setenv("LANGEXTRACT_MODEL_ID", model_id)
    monkeypatch.setenv("LANGEXTRACT_API_KEY", "test-placeholder")
    monkeypatch.setenv("LANGEXTRACT_BASE_URL", "https://example.invalid")
    tree = ast.parse((Path(__file__).parents[1] / module_name).read_text(encoding="utf-8"))
    # Evaluate only the production ModelConfig expression, avoiding module-level dotenv.
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ModelConfig"]
    assert len(calls) == 1
    namespace = {"os": os, "ModelConfig": ModelConfig}
    if hasattr(config, "non_thinking_provider_options"):
        namespace["non_thinking_provider_options"] = config.non_thinking_provider_options
    settings = eval(compile(ast.Expression(calls[0]), module_name, "eval"), namespace)
    assert settings.provider == "openai"
    bodies = []
    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "offline", "object": "chat.completion", "created": 1, "model": model_id, "choices": [{"index": 0, "message": {"role": "assistant", "content": "{\"extractions\": []}"}, "finish_reason": "stop"}]})
    real_client = openai.OpenAI
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: real_client(**kwargs, http_client=transport, max_retries=0))
        provider = OpenAILanguageModel(model_id=settings.model_id, **settings.provider_kwargs)
        outputs = list(provider.infer(["Extract entities."]))
    assert len(outputs) == 1
    assert len(bodies) == 1 and bodies[0]["model"] == model_id
    if model_id in {"deepseek-flash", "deepseek-v4-pro"}:
        assert bodies[0]["reasoning_effort"] == "none"
    else:
        assert "reasoning_effort" not in bodies[0]
    assert "extra_body" not in bodies[0]
