from pathlib import Path
import json
import io

from embedding import EmbeddingClient


def test_embedding_cache_save_tolerates_replace_permission_error(monkeypatch):
    client = EmbeddingClient.__new__(EmbeddingClient)
    client.model = "BAAI/bge-small-zh-v1.5"
    client._cache = {"k1": [0.1, 0.2]}

    store: dict[str, str] = {}

    class MemoryFile(io.StringIO):
        def __init__(self, path: str, mode: str):
            initial = store.get(path, "") if "r" in mode else ""
            super().__init__(initial)
            self._path = path
            self._mode = mode

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type is None and any(flag in self._mode for flag in ("w", "a", "+")):
                store[self._path] = self.getvalue()
            self.close()
            return False

    cache_dir = Path(r"D:\virtual\test-embedding-cache")

    monkeypatch.setattr("embedding.CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("embedding.os.path.exists", lambda path: path in store)
    monkeypatch.setattr(
        "builtins.open",
        lambda path, mode="r", encoding=None: MemoryFile(str(path), mode),
    )
    monkeypatch.setattr("embedding.os.replace", lambda src, dst: (_ for _ in ()).throw(PermissionError("replace denied")))

    def fake_unlink(self, missing_ok=False):
        if self.name.endswith(".tmp"):
            raise PermissionError("cleanup denied")
        if missing_ok:
            store.pop(str(self), None)
            return None
        del store[str(self)]
        return None

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    client._save_cache()

    cache_path = cache_dir / "BAAI_bge_small_zh_v1.5_cache.json"
    assert str(cache_path) in store
    assert json.loads(store[str(cache_path)])["k1"] == [0.1, 0.2]
