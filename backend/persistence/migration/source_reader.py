"""Read and strictly validate legacy JSON/KG sources without mutating them."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .domain import ParsedLegacy, SourceFile
from .errors import LegacyFormatError


_JSON_NAMES = ("output/tasks_store.json", "output/docs_store.json")
_DEFAULT_SCOPE = {
    "owner_id": "legacy",
    "tenant_id": "default/default",
    "org_id": "default",
    "project_id": "default",
}
_TASK_FIELDS = {
    "task_id",
    "status",
    "lifecycle_status",
    "stage",
    "filename",
    "file_size_bytes",
    "source_filepath",
    "progress",
    "result",
    "error",
    "created_at",
    "updated_at",
    "row_version",
    *_DEFAULT_SCOPE,
}
_DOCUMENT_FIELDS = {
    "document_id",
    "filename",
    "status",
    "kg_nodes",
    "kg_edges",
    "pages",
    "indexed_at",
    "file_size_bytes",
    "filepath",
    "active_kg_version",
    "metadata",
    "created_at",
    "updated_at",
    "deleted_at",
    "deletion_reason",
    "reason",
    *_DEFAULT_SCOPE,
}
_KG_STATES = {"staged", "ready", "active", "obsolete", "deleted"}
_SERIALIZER_NODE_FIELDS = {
    "node_id",
    "entity_type",
    "label",
    "properties",
    "page_idx",
    "bbox_norm",
    "grounding_status",
}
_SERIALIZER_EDGE_FIELDS = {
    "edge_id",
    "source_node_id",
    "target_node_id",
    "relation_type",
    "properties",
}
_HEX_SHA256_LENGTH = 64


def _safe_path(path: Path, root: Path) -> Path:
    """Resolve a source path while rejecting traversal and symlink indirection."""
    root = root.resolve()
    if root.is_symlink():
        raise LegacyFormatError("source root must not be a symlink")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise LegacyFormatError("source path escapes source root") from error
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise LegacyFormatError("source path contains an unsafe component")

    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise LegacyFormatError(f"source path uses a symlink: {relative.as_posix()}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise LegacyFormatError(f"cannot resolve legacy source {path}") from error
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise LegacyFormatError(f"legacy source is not a regular file: {relative.as_posix()}")
    return resolved


def _read_file(path: Path, root: Path) -> SourceFile:
    safe = _safe_path(path, root)
    try:
        content = safe.read_bytes()
    except OSError as error:
        raise LegacyFormatError(f"cannot read legacy source {safe.relative_to(root).as_posix()}") from error
    return SourceFile(
        source_path=str(safe),
        relative_path=safe.relative_to(root).as_posix(),
        content=content,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _walk_kg_json(root: Path) -> list[Path]:
    """Enumerate KG files and reject symlinked directories/files."""
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise LegacyFormatError("output/kg must be a real directory")

    files: list[Path] = []
    for directory, directories, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        if directory_path.is_symlink():
            raise LegacyFormatError("KG source tree must not contain symlink directories")
        for name in directories:
            if (directory_path / name).is_symlink():
                raise LegacyFormatError("KG source tree must not contain symlinks")
        for name in filenames:
            path = directory_path / name
            if path.is_symlink():
                raise LegacyFormatError("KG source tree must not contain symlink files")
            if path.suffix.lower() != ".json":
                raise LegacyFormatError(f"unsupported non-JSON KG file: {path.name}")
            files.append(path)
    return sorted(files)


def enumerate_sources(source_root: str | Path) -> tuple[SourceFile, ...]:
    root_input = Path(source_root)
    if root_input.is_symlink():
        raise LegacyFormatError("source root must not be a symlink")
    root = root_input.resolve()
    if not root.exists() or not root.is_dir() or root.is_symlink():
        raise LegacyFormatError("source root must be an existing real directory")

    candidates = [root / relative for relative in _JSON_NAMES]
    candidates.extend(_walk_kg_json(root / "output" / "kg"))
    sources = tuple(_read_file(path, root) for path in candidates)
    if len(sources) < len(_JSON_NAMES):
        raise LegacyFormatError("tasks_store.json and docs_store.json are required")
    return sources


def _duplicate_key_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _json(source: SourceFile) -> Any:
    try:
        return json.loads(
            source.content.decode("utf-8"),
            object_pairs_hook=_duplicate_key_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise LegacyFormatError(f"invalid JSON: {source.relative_path}") from error


def _strict_json(value: Any, field_name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise LegacyFormatError(f"{field_name} must be JSON serializable") from error


def _aware_datetime(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise LegacyFormatError(f"{field_name} is required")
        return None
    if not isinstance(value, str):
        raise LegacyFormatError(f"{field_name} must be an ISO datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise LegacyFormatError(f"{field_name} is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LegacyFormatError(f"{field_name} must be timezone-aware")
    return parsed.isoformat()


def _identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LegacyFormatError(f"{field_name} must be a non-empty string")
    if "\x00" in value or "\\" in value or "/" in value or ".." in value:
        raise LegacyFormatError(f"{field_name} contains an unsafe path sequence")
    return value


def _non_negative_int(value: Any, field_name: str, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LegacyFormatError(f"{field_name} must be a non-negative integer")
    return value


def _optional_string(value: Any, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise LegacyFormatError(f"{field_name} must be a string or null")


def _scope_check(record: dict[str, Any]) -> None:
    for key, default in _DEFAULT_SCOPE.items():
        if key in record:
            if not isinstance(record[key], str) or record[key] != default:
                raise LegacyFormatError(f"explicit non-default scope is unsafe: {key}")


def _reject_unknown(record: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise LegacyFormatError(f"{name} contains unsupported fields: {', '.join(unknown)}")


def _validate_task(record: dict[str, Any], map_key: str) -> dict[str, Any]:
    _reject_unknown(record, _TASK_FIELDS, "task")
    _scope_check(record)
    task_id = _identifier(record.get("task_id"), "task_id")
    if task_id != map_key:
        raise LegacyFormatError("task_id must match its tasks_store map key")
    status = record.get("status", "pending")
    if not isinstance(status, str) or status not in {"pending", "running", "done", "failed"}:
        raise LegacyFormatError("task status is invalid")
    lifecycle_status = record.get("lifecycle_status", "active")
    if not isinstance(lifecycle_status, str) or lifecycle_status not in {"active", "stale", "deleted"}:
        raise LegacyFormatError("task lifecycle_status is invalid")
    for field_name in ("stage", "filename", "source_filepath"):
        _optional_string(record.get(field_name), f"task {field_name}")
    for field_name in ("progress", "result", "error"):
        value = record.get(field_name)
        if value is not None and not isinstance(value, dict):
            raise LegacyFormatError(f"task {field_name} must be an object or null")
        _strict_json(value, f"task {field_name}")
    for field_name in ("file_size_bytes", "row_version"):
        _non_negative_int(record.get(field_name), f"task {field_name}")
    created_at = _aware_datetime(record.get("created_at"), "task created_at")
    updated_at = _aware_datetime(record.get("updated_at"), "task updated_at")
    return {
        **record,
        "task_id": task_id,
        "status": status,
        "lifecycle_status": lifecycle_status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _validate_document(record: dict[str, Any]) -> dict[str, Any]:
    _reject_unknown(record, _DOCUMENT_FIELDS, "document")
    _scope_check(record)
    document_id = _identifier(record.get("document_id"), "document_id")
    status = record.get("status", "pending")
    if not isinstance(status, str) or status not in {"pending", "indexed", "failed", "deleted"}:
        raise LegacyFormatError("document status is invalid")
    for field_name in ("filename", "filepath", "deletion_reason", "reason"):
        _optional_string(record.get(field_name), f"document {field_name}")
    for field_name in ("kg_nodes", "kg_edges", "pages", "file_size_bytes", "active_kg_version"):
        _non_negative_int(record.get(field_name), f"document {field_name}")
    metadata = record.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise LegacyFormatError("document metadata must be an object or null")
    _strict_json(metadata, "document metadata")
    indexed_at = _aware_datetime(record.get("indexed_at"), "document indexed_at")
    created_at = _aware_datetime(record.get("created_at"), "document created_at")
    updated_at = _aware_datetime(record.get("updated_at"), "document updated_at")
    deleted_at = _aware_datetime(record.get("deleted_at"), "document deleted_at")
    if status == "deleted" and record.get("active_kg_version") is not None:
        raise LegacyFormatError("deleted documents cannot have an active KG version")
    return {
        **record,
        "document_id": document_id,
        "status": status,
        "indexed_at": indexed_at,
        "created_at": created_at,
        "updated_at": updated_at,
        "deleted_at": deleted_at,
    }


def _artifact_sha256(nodes_source: SourceFile, edges_source: SourceFile) -> str:
    digest = hashlib.sha256()
    digest.update(nodes_source.content)
    digest.update(edges_source.content)
    return digest.hexdigest()


def _kg_array(source: SourceFile, key: str) -> tuple[list[Any], bool]:
    payload = _json(source)
    count_key = "node_count" if key == "nodes" else "edge_count"
    serializer_envelope = False
    if isinstance(payload, dict):
        # The current kg_builder serializer identifies its envelope with
        # metadata.schema_version.  Keep the legacy object form permissive, but
        # do not let a real serializer envelope omit its declared count.
        allowed = {"metadata", count_key, key}
        unknown = set(payload) - allowed
        if unknown or key not in payload:
            raise LegacyFormatError(
                f"KG {source.relative_path} contains unsupported envelope fields"
            )
        if "metadata" in payload:
            serializer_envelope = True
            metadata = payload["metadata"]
            if not isinstance(metadata, dict):
                raise LegacyFormatError(f"KG {key} metadata must be an object")
            schema_version = metadata.get("schema_version")
            if not isinstance(schema_version, str) or not schema_version.strip():
                raise LegacyFormatError(f"KG {key} schema_version must be a non-empty string")
        values = payload[key]
        if serializer_envelope and count_key not in payload:
            raise LegacyFormatError(f"KG {count_key} is required for serializer envelope")
        declared_count = payload.get(count_key)
    else:
        values = payload
        declared_count = None
    if not isinstance(values, list):
        raise LegacyFormatError(f"KG {key} must be an array")
    if declared_count is not None:
        if _non_negative_int(declared_count, f"KG {count_key}") != len(values):
            raise LegacyFormatError(f"KG {count_key} count does not match the artifact")
    return values, serializer_envelope


def _kg_string_alias(record: dict[str, Any], names: tuple[str, ...], field_name: str) -> str:
    """Read a required KG string, accepting only equivalent legacy aliases."""
    present = [name for name in names if name in record]
    if not present:
        raise LegacyFormatError(f"KG {field_name} is required")
    values = [record[name] for name in present]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise LegacyFormatError(f"KG {field_name} must be a non-empty string")
    if len(set(values)) != 1:
        raise LegacyFormatError(f"KG {field_name} aliases disagree")
    return values[0]


def _parse_kg_pair(
    nodes_source: SourceFile,
    edges_source: SourceFile,
    *,
    document_id: str,
    version: int,
    state: str,
    artifact_relpath: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node_list, node_serializer_envelope = _kg_array(nodes_source, "nodes")
    edge_list, edge_serializer_envelope = _kg_array(edges_source, "edges")
    ids: set[str] = set()
    for node in node_list:
        if not isinstance(node, dict):
            raise LegacyFormatError("KG node must be an object")
        _strict_json(node, "KG node")
        if node_serializer_envelope:
            _reject_unknown(node, _SERIALIZER_NODE_FIELDS, "KG node")
        node_id = _kg_string_alias(
            node,
            ("node_id",) if node_serializer_envelope else ("node_id", "id"),
            "node id",
        )
        entity_type = node.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type.strip():
            raise LegacyFormatError("KG node entity_type must be a non-empty string")
        label = node.get("label")
        if not isinstance(label, str):
            raise LegacyFormatError("KG node label must be a string")
        if node_serializer_envelope and "properties" not in node:
            raise LegacyFormatError("KG node properties is required")
        properties = node.get("properties")
        if node_serializer_envelope and not isinstance(properties, dict):
            raise LegacyFormatError("KG node properties must be an object")
        if not node_serializer_envelope and properties is not None and not isinstance(properties, dict):
            raise LegacyFormatError("KG node properties must be an object")
        if node_serializer_envelope and "page_idx" not in node:
            raise LegacyFormatError("KG node page_idx is required")
        page_idx = node.get("page_idx")
        if page_idx is not None and (isinstance(page_idx, bool) or not isinstance(page_idx, int)):
            raise LegacyFormatError("KG node page_idx must be an integer or null")
        if node_serializer_envelope and "bbox_norm" not in node:
            raise LegacyFormatError("KG node bbox_norm is required")
        bbox_norm = node.get("bbox_norm")
        if bbox_norm is not None:
            if not isinstance(bbox_norm, list) or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in bbox_norm
            ):
                raise LegacyFormatError("KG node bbox_norm must be a numeric array or null")
        if node_serializer_envelope and "grounding_status" not in node:
            raise LegacyFormatError("KG node grounding_status is required")
        grounding_status = node.get("grounding_status")
        if node_serializer_envelope and (
            not isinstance(grounding_status, str) or not grounding_status.strip()
        ):
            raise LegacyFormatError("KG node grounding_status must be a non-empty string")
        if node_id in ids:
            raise LegacyFormatError("KG node ids must be unique non-empty strings")
        ids.add(node_id)

    edge_ids: set[str] = set()
    edge_identity: set[tuple[str, str, str]] = set()
    for edge in edge_list:
        if not isinstance(edge, dict):
            raise LegacyFormatError("KG edge must be an object")
        _strict_json(edge, "KG edge")
        if edge_serializer_envelope:
            _reject_unknown(edge, _SERIALIZER_EDGE_FIELDS, "KG edge")
        endpoint_names = (
            ("source_node_id",) if edge_serializer_envelope else ("source_node_id", "from"),
            ("target_node_id",) if edge_serializer_envelope else ("target_node_id", "to"),
        )
        source = _kg_string_alias(edge, endpoint_names[0], "edge source endpoint")
        target = _kg_string_alias(edge, endpoint_names[1], "edge target endpoint")
        relation_type = _kg_string_alias(edge, ("relation_type",), "edge relation_type")
        if source not in ids or target not in ids:
            raise LegacyFormatError("KG edge endpoints must reference nodes")
        if edge_serializer_envelope and "edge_id" not in edge:
            raise LegacyFormatError("KG edge_id is required")
        edge_id = edge.get("edge_id")
        if edge_serializer_envelope or edge_id is not None:
            if not isinstance(edge_id, str) or not edge_id.strip():
                raise LegacyFormatError("KG edge_id must be a non-empty string")
            if edge_id in edge_ids:
                raise LegacyFormatError("KG edge_ids must be unique")
            edge_ids.add(edge_id)
        identity = (source, target, relation_type)
        if identity in edge_identity:
            raise LegacyFormatError("KG edge identity must be unique")
        edge_identity.add(identity)
        if edge_serializer_envelope and "properties" not in edge:
            raise LegacyFormatError("KG edge properties is required")
        properties = edge.get("properties")
        if edge_serializer_envelope and not isinstance(properties, dict):
            raise LegacyFormatError("KG edge properties must be an object")
        if not edge_serializer_envelope and properties is not None and not isinstance(properties, dict):
            raise LegacyFormatError("KG edge properties must be an object")

    version_metadata = metadata is not None
    metadata = dict(metadata or {})
    node_count = len(node_list)
    edge_count = len(edge_list)
    for field_name, actual in (("nodes", node_count), ("edges", edge_count)):
        if field_name not in metadata:
            if version_metadata:
                raise LegacyFormatError(f"KG version metadata {field_name} is required")
            continue
        if _non_negative_int(metadata[field_name], f"KG {field_name}") != actual:
            raise LegacyFormatError(f"KG {field_name} count does not match the artifact")
    created_at = _aware_datetime(metadata.get("created_at"), "KG created_at")
    manifest_sha256 = _artifact_sha256(nodes_source, edges_source)
    declared_hash = metadata.get("manifest_sha256")
    if declared_hash is not None:
        if (
            not isinstance(declared_hash, str)
            or len(declared_hash) != _HEX_SHA256_LENGTH
            or any(character not in "0123456789abcdef" for character in declared_hash.lower())
            or declared_hash.lower() != manifest_sha256
        ):
            raise LegacyFormatError("KG manifest_sha256 does not match nodes and edges bytes")
    return {
        "document_id": document_id,
        "version": version,
        "state": state,
        "artifact_relpath": artifact_relpath,
        "manifest_sha256": manifest_sha256,
        "node_count": node_count,
        "edge_count": edge_count,
        "metadata": metadata,
        "created_at": created_at,
        "nodes_source": nodes_source,
        "edges_source": edges_source,
    }


def _parse_kg_documents(
    by_path: dict[str, SourceFile],
    document_ids: set[str],
    deleted_document_ids: set[str],
) -> list[dict[str, Any]]:
    kg_paths = [Path(relative) for relative in by_path if relative.startswith("output/kg/")]
    if not kg_paths:
        return []
    if any(path.parts[2:] in (("nodes.json",), ("edges.json",)) for path in kg_paths):
        raise LegacyFormatError("global flat KG cannot be associated with a document")

    doc_dirs: set[Path] = set()
    for path in kg_paths:
        if len(path.parts) < 4 or not path.parts[2].startswith("doc_"):
            raise LegacyFormatError("KG files must be under a document-scoped doc_{id} directory")
        if path.parts[2] == "doc_":
            raise LegacyFormatError("KG document directory has an empty document id")
        doc_dirs.add(Path(*path.parts[:3]))

    results: list[dict[str, Any]] = []
    seen_versions: set[tuple[str, int]] = set()
    for doc_dir in sorted(doc_dirs):
        document_id = doc_dir.name[4:]
        if document_id not in document_ids:
            raise LegacyFormatError("KG directory cannot be associated with a document")
        own_paths = {path for path in kg_paths if Path(*path.parts[:3]) == doc_dir}
        versions_path = doc_dir / "versions.json"
        if str(versions_path).replace("\\", "/") in by_path:
            versions_source = by_path[str(versions_path).replace("\\", "/")]
            metadata_root = _json(versions_source)
            if not isinstance(metadata_root, dict) or set(metadata_root) != {"doc_id", "versions", "active_version"}:
                raise LegacyFormatError("KG versions.json has an invalid shape")
            if metadata_root["doc_id"] != document_id:
                raise LegacyFormatError("KG versions doc_id does not match path")
            versions = metadata_root["versions"]
            active = metadata_root["active_version"]
            if not isinstance(versions, list) or isinstance(active, bool) or not isinstance(active, int) or active <= 0:
                raise LegacyFormatError("versioned KG requires a positive active_version and versions array")
            if not versions:
                raise LegacyFormatError("versioned KG requires at least one version")
            declared_versions: set[int] = set()
            for item in versions:
                if not isinstance(item, dict):
                    raise LegacyFormatError("KG version metadata must be an object")
                version = item.get("version")
                if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
                    raise LegacyFormatError("KG version number is invalid")
                if version in declared_versions:
                    raise LegacyFormatError("duplicate KG version")
                declared_versions.add(version)
            if active not in declared_versions:
                raise LegacyFormatError("active_version must exist in KG version metadata")
            active_versions = 0
            expected_paths: set[Path] = {versions_path}
            for item in versions:
                if not isinstance(item, dict):
                    raise LegacyFormatError("KG version metadata must be an object")
                allowed = {"version", "created_at", "nodes", "edges", "status", "manifest_sha256", *_DEFAULT_SCOPE}
                _reject_unknown(item, allowed, "KG version metadata")
                version = item.get("version")
                if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
                    raise LegacyFormatError("KG version number is invalid")
                key = (document_id, version)
                if key in seen_versions:
                    raise LegacyFormatError("duplicate KG version")
                seen_versions.add(key)
                _scope_check(item)
                status = item.get("status")
                if status not in _KG_STATES:
                    raise LegacyFormatError("KG version state is invalid")
                if document_id in deleted_document_ids:
                    status = "deleted"
                elif status == "active" and version != active:
                    raise LegacyFormatError("only active_version may have active status")
                if document_id not in deleted_document_ids and version == active:
                    if status != "active":
                        raise LegacyFormatError("active_version must point to an active version")
                    active_versions += 1
                created_at = _aware_datetime(item.get("created_at"), "KG created_at", required=True)
                item = {**item, "created_at": created_at}
                nodes_key = (doc_dir / f"v{version}" / "nodes.json").as_posix()
                edges_key = (doc_dir / f"v{version}" / "edges.json").as_posix()
                if nodes_key not in by_path or edges_key not in by_path:
                    raise LegacyFormatError("versioned KG requires paired nodes.json and edges.json")
                expected_paths.update({Path(nodes_key), Path(edges_key)})
                results.append(
                    _parse_kg_pair(
                        by_path[nodes_key],
                        by_path[edges_key],
                        document_id=document_id,
                        version=version,
                        state=status,
                        artifact_relpath=(doc_dir / f"v{version}").as_posix(),
                        metadata=item,
                    )
                )
            if document_id not in deleted_document_ids and (
                active_versions != 1 or active not in {version for doc, version in seen_versions if doc == document_id}
            ):
                raise LegacyFormatError("versioned KG must have exactly one active version")
            if own_paths != expected_paths:
                raise LegacyFormatError("versioned KG contains unexpected JSON files")
        else:
            nodes_path = doc_dir / "nodes.json"
            edges_path = doc_dir / "edges.json"
            expected_paths = {nodes_path, edges_path}
            if str(nodes_path).replace("\\", "/") not in by_path or str(edges_path).replace("\\", "/") not in by_path:
                raise LegacyFormatError("flat document KG requires paired nodes.json and edges.json")
            if own_paths != expected_paths:
                raise LegacyFormatError("flat document KG contains unexpected JSON files")
            results.append(
                _parse_kg_pair(
                    by_path[nodes_path.as_posix()],
                    by_path[edges_path.as_posix()],
                    document_id=document_id,
                    version=1,
                    state="active",
                    artifact_relpath=doc_dir.as_posix(),
                )
            )
    return results


def parse_sources(sources: tuple[SourceFile, ...]) -> ParsedLegacy:
    by_path: dict[str, SourceFile] = {}
    for source in sources:
        if not isinstance(source, SourceFile):
            raise LegacyFormatError("sources must contain SourceFile values")
        if not isinstance(source.relative_path, str) or not source.relative_path:
            raise LegacyFormatError("source relative_path is invalid")
        relative_path = source.relative_path.replace("\\", "/")
        if relative_path in by_path:
            raise LegacyFormatError(f"duplicate source relative_path: {relative_path}")
        if not isinstance(source.source_path, str) or not source.source_path:
            raise LegacyFormatError(f"source_path is invalid: {relative_path}")
        if not isinstance(source.content, bytes):
            raise LegacyFormatError(f"source content is not bytes: {relative_path}")
        if isinstance(source.size, bool) or not isinstance(source.size, int) or source.size < 0:
            raise LegacyFormatError(f"source size is invalid: {relative_path}")
        if not isinstance(source.sha256, str):
            raise LegacyFormatError(f"source sha256 is invalid: {relative_path}")
        try:
            actual_content = Path(source.source_path).read_bytes()
        except OSError as error:
            raise LegacyFormatError(f"cannot read source file: {relative_path}") from error
        if (
            actual_content != source.content
            or source.size != len(source.content)
            or source.sha256 != hashlib.sha256(source.content).hexdigest()
        ):
            raise LegacyFormatError(f"source file metadata is inconsistent: {relative_path}")
        by_path[relative_path] = source
    task_source = by_path.get("output/tasks_store.json")
    doc_source = by_path.get("output/docs_store.json")
    if task_source is None or doc_source is None:
        raise LegacyFormatError("tasks_store.json and docs_store.json are required")

    raw_tasks = _json(task_source)
    if not isinstance(raw_tasks, dict):
        raise LegacyFormatError("tasks_store.json root must be an object map")
    tasks: list[dict[str, Any]] = []
    for map_key, record in raw_tasks.items():
        if not isinstance(map_key, str) or not isinstance(record, dict):
            raise LegacyFormatError("tasks_store.json must map string ids to objects")
        tasks.append(_validate_task(record, map_key))

    raw_docs = _json(doc_source)
    if not isinstance(raw_docs, list):
        raise LegacyFormatError("docs_store.json root must be an array")
    documents: list[dict[str, Any]] = []
    document_ids: set[str] = set()
    for record in raw_docs:
        if not isinstance(record, dict):
            raise LegacyFormatError("docs_store.json contains a non-object record")
        document = _validate_document(record)
        if document["document_id"] in document_ids:
            raise LegacyFormatError("duplicate document_id in docs_store.json")
        document_ids.add(document["document_id"])
        documents.append(document)

    deleted_document_ids = {document["document_id"] for document in documents if document["status"] == "deleted"}
    kg_versions = _parse_kg_documents(by_path, document_ids, deleted_document_ids)
    by_document: dict[str, list[dict[str, Any]]] = {}
    for kg in kg_versions:
        by_document.setdefault(kg["document_id"], []).append(kg)
    for document in documents:
        versions = by_document.get(document["document_id"], [])
        active = next((kg for kg in versions if kg["state"] == "active"), None)
        if document["status"] == "deleted" and active is not None:
            raise LegacyFormatError("deleted documents cannot have an active KG version")
        declared = document.get("active_kg_version")
        if declared is not None and (active is None or declared != active["version"]):
            raise LegacyFormatError("document active_kg_version does not match KG metadata")
        if active is not None:
            for field_name, count_key in (("kg_nodes", "node_count"), ("kg_edges", "edge_count")):
                if field_name in document and document[field_name] != active[count_key]:
                    raise LegacyFormatError(f"document {field_name} does not match the active KG artifact")
        if document["status"] == "deleted":
            for kg in versions:
                kg["state"] = "deleted"

    return ParsedLegacy(tuple(tasks), tuple(documents), tuple(kg_versions))


def aggregate_sha256(sources: tuple[SourceFile, ...]) -> str:
    digest = hashlib.sha256()
    for source in sorted(sources, key=lambda item: item.relative_path):
        digest.update(source.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.content)
        digest.update(b"\0")
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
