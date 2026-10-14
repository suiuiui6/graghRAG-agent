from pathlib import Path

import vector_store as vector_store_module


def test_vector_store_falls_back_to_sqlite_safe_temp_mirror(monkeypatch):
    source_dir = Path(r"D:\virtual\vector-store\source\vectordb")
    fallback_dir = Path(r"D:\virtual\vector-store\temp\graphrag_chroma\vectordb")

    attempted_paths: list[str] = []
    prepared = {}

    class DummyPersistentClient:
        def __init__(self, path, settings):
            attempted_paths.append(path)
            if path == str(source_dir):
                raise RuntimeError("disk I/O error")
            self.path = path

        def get_or_create_collection(self, name, metadata):
            return {"name": name, "metadata": metadata}

    monkeypatch.setattr(vector_store_module, "HAS_CHROMADB", True)
    monkeypatch.setattr(vector_store_module.chromadb, "PersistentClient", DummyPersistentClient)
    monkeypatch.setattr(vector_store_module, "ChromaSettings", lambda anonymized_telemetry=False: object())
    monkeypatch.setattr(vector_store_module.os, "makedirs", lambda *args, **kwargs: None)

    def fake_prepare_sqlite_safe_mirror(persist_dir):
        prepared["persist_dir"] = persist_dir
        return str(fallback_dir)

    monkeypatch.setattr(
        vector_store_module,
        "_prepare_sqlite_safe_mirror",
        fake_prepare_sqlite_safe_mirror,
    )

    store = vector_store_module.VectorStore(persist_dir=str(source_dir))

    assert attempted_paths[0] == str(source_dir)
    assert prepared["persist_dir"] == str(source_dir)
    assert attempted_paths[1] == str(fallback_dir)
    assert store.persist_dir == str(fallback_dir)


def test_vector_store_fallback_reuses_existing_temp_mirror_directory(monkeypatch):
    source_dir = Path(r"D:\virtual\vector-store\source\vectordb")
    mirror_dir = Path(r"D:\virtual\vector-store\temp\graphrag_chroma\vectordb")

    attempted_paths: list[str] = []
    prepared = {}

    class DummyPersistentClient:
        def __init__(self, path, settings):
            attempted_paths.append(path)
            if path == str(source_dir):
                raise RuntimeError("disk I/O error")
            self.path = path

        def get_or_create_collection(self, name, metadata):
            return {"name": name, "metadata": metadata}

    monkeypatch.setattr(vector_store_module, "HAS_CHROMADB", True)
    monkeypatch.setattr(vector_store_module.chromadb, "PersistentClient", DummyPersistentClient)
    monkeypatch.setattr(vector_store_module, "ChromaSettings", lambda anonymized_telemetry=False: object())
    monkeypatch.setattr(vector_store_module.os, "makedirs", lambda *args, **kwargs: None)

    def fake_prepare_sqlite_safe_mirror(persist_dir):
        prepared["persist_dir"] = persist_dir
        return str(mirror_dir)

    monkeypatch.setattr(
        vector_store_module,
        "_prepare_sqlite_safe_mirror",
        fake_prepare_sqlite_safe_mirror,
    )

    store = vector_store_module.VectorStore(persist_dir=str(source_dir))

    assert attempted_paths == [str(source_dir), str(mirror_dir)]
    assert prepared["persist_dir"] == str(source_dir)
    assert store.persist_dir == str(mirror_dir)
