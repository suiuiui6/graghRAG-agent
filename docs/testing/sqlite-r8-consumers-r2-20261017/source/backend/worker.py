"""
Real document indexing worker — MinerU → BridgePipeline → LangExtract → KG.

Replaces the simulated pipeline in routes/ingest.py.
Uses curl subprocess for network calls (Python requests blocked in this env).
"""

import glob
import html
import json
import os
import csv

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=True)  # Force override system environment variables
import re
import sys
import time
import yaml
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from bridge import (
    _item_to_text, _table_body_to_text, build_documents, build_position_map, find_section_boundaries,
    load_content_list, load_full_md,
)
from errors import (
    ErrorCode, ErrorContext, PipelineError, PipelineStage,
    StageBridgeError, StageExtractionError, StageGroundingError, StageKGBuildError,
    StageMinerUError, classify_external_error,
)
from grounding import grounding_stats, resolve_grounding
from kg_builder import build_knowledge_graph, serialize_kg
from logging_config import get_logger
from config import non_thinking_provider_options
# MinerU 传输层已抽到独立模块（mineru_client）。这三个符号在这里**再导出**，
# 因为既有的 tests/test_errors.py 从 worker 导入 `_http_status_error`，
# 且 worker.py 自身仍在用。实现只有一份，在 mineru_client 里。
from mineru_client import (  # noqa: F401  (re-export)
    MineruRoute, _HttpStatusError, _http_status_error, _split_curl_status,
    download_and_extract, poll_until_done, submit_local_file, submit_url_task,
)

logger = get_logger(__name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")


@dataclass
class ExtractionOutcome:
    node_count: int
    edge_count: int
    batches_total: int
    batches_failed: int
    first_error: PipelineError | None = None

    @property
    def all_failed(self) -> bool:
        return self.batches_total > 0 and self.batches_failed == self.batches_total

    @property
    def partial(self) -> bool:
        return 0 < self.batches_failed < self.batches_total


def run_real_pipeline(task_id: str, filepath: str, filename: str, progress_callback,
                      ingest_options: dict | None = None):
    """顶层入口：绑定 task_id 日志上下文，并把 StageError 转成任务终态信号。

    `PipelineError` 在这里记日志 + 回调后**继续向上抛** —— 由
    `routes/ingest.py` 决定任务终态（failed）。改造前失败的 return None
    会被调用方当成"已处理"，与"零实体成功"无法区分。
    """
    from logging_config import get_logger, task_scope
    log = get_logger(__name__)
    with task_scope(task_id):
        try:
            return _run_real_pipeline_inner(task_id, filepath, filename,
                                            progress_callback, ingest_options)
        except PipelineError as exc:
            log.error("pipeline_failed", task_id=task_id, error_code=exc.code.value,
                      stage=exc.stage.value if exc.stage else None, exc_info=True)
            progress_callback(
                exc.stage.value if exc.stage else "unknown",
                f"Pipeline Error ({exc.stage.value if exc.stage else 'unknown'})",
                0, {}, error=exc.message, error_code=exc.code.value,
            )
            raise       # 由 routes/ingest.py 决定任务终态


def _run_real_pipeline_inner(task_id: str, filepath: str, filename: str, progress_callback, ingest_options: dict | None = None):
    """Execute the full MinerU → BridgePipeline → LangExtract → KG pipeline.

    PDF: MinerU API → BridgePipeline → LangExtract → KG (existing flow)
    DOCX/XLSX: Local parsing via python-docx/openpyxl → chunks → embedding → vector store
    """

    ext = os.path.splitext(filename.lower())[1] if filename else ""

    # ── DOCX/XLSX: Local parsing path (skip MinerU) ──
    if ext in (".docx", ".xlsx", ".doc"):
        return _run_local_parse_pipeline(task_id, filepath, filename, ext, progress_callback)

    # ── Stage 0: 确定 MinerU 输出目录 ──
    mineru_dir = _resolve_mineru_dir(task_id, filepath, ingest_options, progress_callback)


    # ── Stage 3: Format Bridge ──
    progress_callback("bridge", "Format Bridge 分段", 2, {"bridge": "running"})
    try:
        full_md_path = os.path.join(mineru_dir, "full.md")
        cl_pattern = os.path.join(mineru_dir, "*_content_list.json")
        cl_files = [f for f in glob.glob(cl_pattern) if "_v2" not in f]
        if not cl_files or not os.path.exists(full_md_path):
            raise FileNotFoundError("MinerU output missing")
        content_list = load_content_list(cl_files[0])
        full_md = load_full_md(full_md_path)
        position_map = build_position_map(content_list, full_md)
        sections = find_section_boundaries(content_list, full_md, position_map, min_level=2)
        documents, doc_offsets = build_documents(sections, full_md)
        progress_callback("bridge", "Format Bridge 分段", 2, {"bridge": "done"})
    except Exception as exc:
        raise StageBridgeError(
            "MinerU 输出解析/分段失败",
            code=ErrorCode.PIPELINE_BRIDGE_PARSE,
            context=ErrorContext(stage=PipelineStage.BRIDGE, task_id=task_id),
        ) from exc

    try:
        _build_runtime_indexes_from_mineru_output(mineru_dir, filename, source_path=filepath)
    except Exception:  # noqa: BLE001  # 运行时索引为旁路产物，构建失败只降级检索质量，不阻断入库主流程
        # 运行时索引为旁路产物，构建失败只降级检索质量，不阻断入库主流程
        logger.warning("runtime_index_build_failed", task_id=task_id, exc_info=True)

    # ── Stage 4: LangExtract ──
    progress_callback("extraction", "LangExtract 实体抽取", 3, {"extraction": "running"})
    try:
        annotated = _run_langextract(documents)
        progress_callback("extraction", "LangExtract 实体抽取", 3, {"extraction": "done"})
    except Exception as exc:
        raise StageExtractionError(
            "LangExtract 实体抽取失败",
            code=ErrorCode.PIPELINE_EXTRACTION_UNKNOWN,
            context=ErrorContext(provider="deepseek", stage=PipelineStage.EXTRACTION,
                                 task_id=task_id),
        ) from exc

    # ── Stage 5: Grounding + KG ──
    progress_callback("grounding", "Grounding 溯源解析", 4, {"grounding": "running"})
    try:
        grounded = resolve_grounding(annotated, position_map, doc_offsets)
        stats = grounding_stats(grounded)
        progress_callback("grounding", "Grounding 溯源解析", 4, {"grounding": "done"})
    except Exception as exc:
        raise StageGroundingError(
            "溯源解析失败",
            code=ErrorCode.PIPELINE_GROUNDING_ERROR,
            context=ErrorContext(stage=PipelineStage.GROUNDING, task_id=task_id),
        ) from exc

    progress_callback("kg_build", "KG 知识图谱构建", 5, {"kg_build": "running"})
    try:
        nodes, edges = build_knowledge_graph(grounded)
        kg_dir = os.path.join(os.path.dirname(__file__), "output", "kg", f"doc_{task_id}")
        nodes_path, _ = serialize_kg(nodes, edges, {}, kg_dir)
        progress_callback("kg_build", "KG 知识图谱构建", 5, {"kg_build": "done"})
    except Exception as exc:
        raise StageKGBuildError(
            "知识图谱构建或落盘失败",
            code=ErrorCode.PIPELINE_KG_BUILD_IO,
            context=ErrorContext(stage=PipelineStage.KG_BUILD, task_id=task_id),
        ) from exc

    # Publish event + audit log
    try:
        from services.event_bus import get_event_bus
        get_event_bus().publish("doc.ingested", {
            "doc_id": f"doc_{task_id}",
            "filename": filename,
            "task_id": task_id,
            "kg_nodes": len(nodes),
            "kg_edges": len(edges),
            "kg_version": 1,
            "pages_parsed": len(sections),
            "duration_seconds": int(time.time()),
        })
    except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响入库完成
        pass
    try:
        from services.audit_logger import get_audit_logger
        get_audit_logger().log("doc.ingested", doc_id=f"doc_{task_id}",
                               filename=filename, kg_nodes=len(nodes), kg_edges=len(edges))
    except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
        pass

    return {
        "document_id": f"doc_{task_id}",
        "kg_nodes": len(nodes),
        "kg_edges": len(edges),
        "grounded_entities": stats["grounded"],
        "entity_types": len(set(n.entity_type for n in nodes)),
        "pages_parsed": len(sections),
        "kg_path": kg_dir,
        "partial": False,
        "warnings": [],
    }


def _resolve_mineru_dir(task_id: str, filepath: str, ingest_options: dict | None,
                        progress_callback) -> str:
    """确定 MinerU 输出目录（Stage 0）。

    本地文件走 MinerU 直传（默认）→ OSS 上传后走 URL 模式。
    两条路径均失败则报错；禁止使用未经文档身份校验的历史缓存。
    公网 URL 输入直接走 URL 模式（不经直传/OSS）。

    抽成独立函数是为了让"哪一级被选中、失败后是否回退"可被单独测试 ——
    内联在流水线里时，任何桩都会先被 bridge/KG 阶段的 except 捕获重包，
    导致测试测不到真正的判定逻辑。
    """
    is_remote = filepath.startswith("http://") or filepath.startswith("https://")
    token = os.getenv("MINERU_API_TOKEN", "")
    upload_errors: list[str] = []

    if is_remote:
        # ── Path B: 输入本身是公网 URL ──
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "running"})
        mineru_dir = _call_mineru_api(filepath, token, task_id, ingest_options)
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
        return mineru_dir

    # ── Path A: 本地文件，直传及 OSS 回退 ──
    #
    # ① MinerU 直传（**默认**）—— POST /file-urls/batch 拿预签名 URL，PUT 直传，
    #    无需自建对象存储。这是当前唯一可用的主路径：OSS AccessKey 已被禁用
    #    （403 InvalidAccessKeyId: disabled）。
    # ② OSS 上传后走 URL 模式 —— 保留为回退；若将来重新启用 OSS 凭据即可生效。
    # 两条上传路径都失败时明确报错，历史产物不能作为本次文档结果。
    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "uploading"})
    try:
        mineru_dir = _call_mineru_local_file(filepath, token, task_id, ingest_options)
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
        return mineru_dir
    except PipelineError as exc:
        # 鉴权/参数类失败不是"换个通道就能好"——直传与 URL 模式共用同一个 Token
        # 与同一套参数，回退只会用同样的坏凭据再失败一次。立即上抛，把 OSS 的
        # 回退预算留给真正可恢复的失败（网络/限流/5xx）。
        if exc.code in (ErrorCode.PIPELINE_MINERU_AUTH, ErrorCode.PIPELINE_MINERU_PARSE):
            raise
        upload_errors.append(f"mineru-direct:{exc.code.value}")
        logger.warning("mineru_direct_upload_failed", task_id=task_id,
                       error_code=exc.code.value, exc_info=True)

    # ② OSS → URL 模式
    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "uploading_to_oss"})
    try:
        public_url = _upload_to_public(filepath)
        if public_url:
            mineru_dir = _call_mineru_api(public_url, token, task_id, ingest_options)
            progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
            return mineru_dir
        upload_errors.append("oss:upload_returned_none")
        logger.warning("oss_upload_unavailable", task_id=task_id)
    except PipelineError as exc:
        if exc.code in (ErrorCode.PIPELINE_MINERU_AUTH, ErrorCode.PIPELINE_MINERU_PARSE):
            raise
        upload_errors.append(f"oss-url:{exc.code.value}")
        logger.warning("oss_url_mode_failed", task_id=task_id,
                       error_code=exc.code.value, exc_info=True)

    # 兼容接收 allow_cached_mineru_output，但不得开启无身份校验的缓存复用。
    # 上传链路全败（禁止无匹配缓存参与）。根因归 mineru（主路径）而非 oss。
    raise StageMinerUError(
        "文档上传失败：MinerU 直传与 OSS 回退均不可用",
        code=ErrorCode.PIPELINE_MINERU_IO,
        context=ErrorContext(
            provider="mineru", stage=PipelineStage.MINERU, task_id=task_id,
            details={"attempts": upload_errors,
                     "hint": "检查 MINERU_API_TOKEN 与网络；或提供公网 URL 走 URL 模式。"
                             "未经文档身份校验的历史缓存已禁用，显式开启参数也不生效。"},
        ),
    )



def _build_runtime_indexes_from_mineru_output(mineru_dir: str, filename: str, source_path: str | None = None):
    """Build runtime BM25/Table indexes from MinerU output for PDF ingest."""
    from doc_processor import chunk_sections, deduplicate_chunks
    from index_registry import (
        build_bm25_from_chunks,
        build_table_index_from_chunks,
        set_bm25_index,
        set_table_index,
    )

    sections = _mineru_output_to_sections(mineru_dir, filename, source_path=source_path)
    chunks = chunk_sections(
        sections,
        source_file=filename,
        source_format="pdf",
        level=2,
    )
    chunks = deduplicate_chunks(chunks)

    bm25 = build_bm25_from_chunks(chunks)
    if bm25 is not None:
        set_bm25_index(bm25)

    table_index = build_table_index_from_chunks(chunks)
    if table_index is not None:
        set_table_index(table_index)

    return chunks


_SCENARIO_ALIAS_RE = re.compile(r"\b(W\d+S\d+)\b", flags=re.IGNORECASE)
_SUPPORT_ARTIFACT_REF_RE = re.compile(r"\b([A-Za-z0-9_.-]+\.(?:csv|txt|md|json))\b", flags=re.IGNORECASE)
_SIDECAR_TABLE_BATCH_ROWS = 100


def _support_artifact_runtime_sections(sections: list, *, base_title: str):
    """Project appendix support-artifact lines into synthetic table sections when possible."""
    from doc_processor import Section

    synthetic_sections = []
    current_marker = ""
    pending_rows: list[list[str]] = []
    pending_page_idx = None
    pending_char_start = 0
    pending_char_end = 0

    def flush_pending_rows():
        nonlocal pending_rows, pending_page_idx, pending_char_start, pending_char_end
        if not pending_rows:
            return

        table_json = {
            "headers": ["场景", "索引说明"],
            "rows": list(pending_rows),
            "caption": "scenario_summary support artifact",
        }
        table_text = "\n".join(
            [
                "scenario_summary support artifact",
                "场景 | 索引说明",
                *[f"{alias} | {description}" for alias, description in pending_rows],
            ]
        )
        synthetic_sections.append(
            Section(
                title=base_title or "support_artifact",
                level=2,
                text=table_text,
                content_type="table",
                table_json=table_json,
                page_idx=pending_page_idx,
                char_start=pending_char_start,
                char_end=pending_char_end,
            )
        )
        pending_rows = []
        pending_page_idx = None
        pending_char_start = 0
        pending_char_end = 0

    for section in sections:
        text = str(getattr(section, "text", "") or "").strip()
        if not text:
            continue

        if "scenario_summary.csv" in text:
            flush_pending_rows()
            current_marker = "scenario_summary"
            continue

        aliases = _SCENARIO_ALIAS_RE.findall(text)
        if current_marker != "scenario_summary":
            continue

        if not aliases:
            if pending_rows:
                flush_pending_rows()
            current_marker = ""
            continue

        normalized_text = re.sub(r"\s+", " ", text)
        if not pending_rows:
            pending_page_idx = getattr(section, "page_idx", None)
            pending_char_start = int(getattr(section, "char_start", 0) or 0)
        pending_char_end = int(getattr(section, "char_end", 0) or 0)
        pending_rows.extend([[alias.upper(), normalized_text] for alias in aliases])

    flush_pending_rows()

    return synthetic_sections


def _extract_support_artifact_references(sections: list) -> list[str]:
    ordered_refs: list[str] = []
    seen: set[str] = set()
    for section in sections:
        text = str(getattr(section, "text", "") or "")
        for ref in _SUPPORT_ARTIFACT_REF_RE.findall(text):
            normalized = ref.strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            ordered_refs.append(normalized)
    return ordered_refs


def _discover_support_artifact_paths(
    mineru_dir: str,
    *,
    source_path: str | None,
    references: list[str],
) -> list[Path]:
    candidate_dirs: list[Path] = []
    seen_dirs: set[str] = set()
    for raw_dir in [mineru_dir, str(Path(source_path).parent) if source_path else None]:
        if not raw_dir:
            continue
        path = Path(raw_dir)
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        candidate_dirs.append(path)

    discovered: list[Path] = []
    seen_files: set[str] = set()
    for reference in references:
        for directory in candidate_dirs:
            candidate = directory / reference
            if candidate.is_file():
                key = str(candidate.resolve())
                if key not in seen_files:
                    seen_files.add(key)
                    discovered.append(candidate)
                break
    return discovered


def _sidecar_table_sections(path: Path, *, base_title: str, char_offset: int):
    from doc_processor import Section

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_rows = [
            [str(cell).strip() for cell in row]
            for row in csv.reader(handle)
            if any(str(cell).strip() for cell in row)
        ]

    if len(raw_rows) < 2:
        return [], char_offset

    headers = [cell.strip() or f"col_{idx + 1}" for idx, cell in enumerate(raw_rows[0])]
    data_rows = []
    for row in raw_rows[1:]:
        normalized = [cell.strip() for cell in row[:len(headers)]]
        while len(normalized) < len(headers):
            normalized.append("")
        if any(normalized):
            data_rows.append(normalized)

    if not data_rows:
        return [], char_offset

    sections = []
    for batch_start in range(0, len(data_rows), _SIDECAR_TABLE_BATCH_ROWS):
        batch_rows = data_rows[batch_start: batch_start + _SIDECAR_TABLE_BATCH_ROWS]
        row_range_end = batch_start + len(batch_rows)
        caption = (
            path.name
            if len(data_rows) <= _SIDECAR_TABLE_BATCH_ROWS
            else f"{path.name} (rows {batch_start + 1}-{row_range_end})"
        )
        text = "\n".join(
            [
                caption,
                " | ".join(headers),
                *[" | ".join(row) for row in batch_rows],
            ]
        )
        sections.append(
            Section(
                title=base_title or path.stem or "support_artifact",
                level=2,
                text=text,
                content_type="table",
                table_json={
                    "headers": headers,
                    "rows": batch_rows,
                    "caption": caption,
                },
                page_idx=None,
                char_start=char_offset,
                char_end=char_offset + len(text),
            )
        )
        char_offset += len(text)

    return sections, char_offset


def _sidecar_text_section(path: Path, *, base_title: str, char_offset: int):
    from doc_processor import Section

    body = path.read_text(encoding="utf-8-sig").strip()
    if not body:
        return None, char_offset

    text = f"{path.name}\n{body}"
    section = Section(
        title=base_title or path.stem or "support_artifact",
        level=2,
        text=text,
        content_type="text",
        table_json=None,
        page_idx=None,
        char_start=char_offset,
        char_end=char_offset + len(text),
    )
    return section, char_offset + len(text)


def _load_sidecar_sections(
    mineru_dir: str,
    *,
    source_path: str | None,
    reference_sections: list,
    base_title: str,
    char_offset: int,
):
    sidecar_sections = []
    references = _extract_support_artifact_references(reference_sections)
    artifact_paths = _discover_support_artifact_paths(
        mineru_dir,
        source_path=source_path,
        references=references,
    )

    for artifact_path in artifact_paths:
        suffix = artifact_path.suffix.lower()
        if suffix == ".csv":
            parsed_sections, char_offset = _sidecar_table_sections(
                artifact_path,
                base_title=base_title,
                char_offset=char_offset,
            )
            sidecar_sections.extend(parsed_sections)
            continue

        if suffix in {".txt", ".md", ".json"}:
            parsed_section, char_offset = _sidecar_text_section(
                artifact_path,
                base_title=base_title,
                char_offset=char_offset,
            )
            if parsed_section is not None:
                sidecar_sections.append(parsed_section)

    return sidecar_sections, char_offset


def _mineru_output_to_sections(mineru_dir: str, filename: str, source_path: str | None = None):
    """Project MinerU content_list items into doc_processor Sections."""
    from doc_processor import Section

    full_md_path = os.path.join(mineru_dir, "full.md")
    cl_pattern = os.path.join(mineru_dir, "*_content_list.json")
    cl_files = [f for f in glob.glob(cl_pattern) if "_v2" not in f]
    cl_v2_pattern = os.path.join(mineru_dir, "*_content_list_v2.json")
    cl_v2_files = list(glob.glob(cl_v2_pattern))
    if not cl_files or not os.path.exists(full_md_path):
        raise FileNotFoundError("MinerU output missing")

    content_list = load_content_list(cl_files[0])
    current_title = os.path.splitext(filename)[0] or "document"
    current_level = 1
    char_offset = 0
    sections = []

    for item in content_list:
        text = _item_to_text(item).strip()
        item_type = item.get("type", "")
        if item.get("text_level") and item.get("text"):
            current_title = item["text"].strip() or current_title
            current_level = item.get("text_level", current_level)

        if not text:
            continue

        table_json = None
        content_type = "text"
        if item_type == "table":
            table_json = _mineru_table_item_to_table_json(item)
            if table_json:
                content_type = "table"

        sections.append(Section(
            title=current_title,
            level=current_level,
            text=text,
            content_type=content_type,
            table_json=table_json,
            page_idx=item.get("page_idx"),
            char_start=char_offset,
            char_end=char_offset + len(text),
        ))
        char_offset += len(text)

    if cl_v2_files:
        v2_sections, char_offset = _mineru_v2_support_sections(
            cl_v2_files[0],
            current_title=current_title,
            current_level=current_level,
            char_offset=char_offset,
        )
        sections.extend(v2_sections)
        sidecar_sections, char_offset = _load_sidecar_sections(
            mineru_dir,
            source_path=source_path,
            reference_sections=v2_sections,
            base_title=current_title,
            char_offset=char_offset,
        )
        sections.extend(sidecar_sections)
        sections.extend(
            _support_artifact_runtime_sections(
                v2_sections,
                base_title=current_title,
            )
        )

    return sections


def _mineru_v2_support_sections(
    content_list_v2_path: str,
    *,
    current_title: str,
    current_level: int,
    char_offset: int,
):
    """Extract appendix/support text from MinerU v2 content list for runtime indexing."""
    from doc_processor import Section

    raw = json.loads(Path(content_list_v2_path).read_text(encoding="utf-8"))
    sections = []
    title = current_title
    level = current_level

    for page_items in raw:
        if not isinstance(page_items, list):
            continue
        for item in page_items:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type", "") or "")
            content = item.get("content", {}) or {}

            if item_type == "title":
                title_text = _mineru_v2_inline_text(content.get("title_content", []))
                if title_text:
                    title = title_text
                    level = int(content.get("level", level) or level)
                continue

            text = ""
            content_type = "text"
            table_json = None

            if item_type == "paragraph":
                text = _mineru_v2_inline_text(content.get("paragraph_content", []))
            elif item_type == "list":
                list_items = content.get("list_items", []) or []
                text = "\n".join(
                    filter(
                        None,
                        (_mineru_v2_inline_text(list_item.get("item_content", [])) for list_item in list_items if isinstance(list_item, dict)),
                    )
                )
            elif item_type == "table":
                table_caption = _mineru_v2_inline_text(content.get("table_caption", []))
                table_body = str(content.get("html", "") or "")
                body_text = _table_body_to_text(table_body)
                text_parts = [part for part in (table_caption, body_text) if part]
                text = "\n".join(text_parts)
                table_json = _mineru_table_item_to_table_json(
                    {
                        "table_caption": [table_caption] if table_caption else [],
                        "table_body": table_body,
                    }
                )
                if table_json:
                    content_type = "table"

            text = (text or "").strip()
            if not text:
                continue

            sections.append(
                Section(
                    title=title,
                    level=level,
                    text=text,
                    content_type=content_type,
                    table_json=table_json,
                    page_idx=item.get("page_idx"),
                    char_start=char_offset,
                    char_end=char_offset + len(text),
                )
            )
            char_offset += len(text)

    return sections, char_offset


def _mineru_v2_inline_text(items: list[dict]) -> str:
    parts = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if content:
            parts.append(str(content))
    return " ".join(part.strip() for part in parts if str(part).strip())


def _mineru_table_item_to_table_json(item: dict) -> dict | None:
    """Parse a MinerU table item into structured headers/rows for TableIndex."""
    table_body = str(item.get("table_body", "") or "")
    rows = _parse_html_table_rows(table_body)
    if not rows:
        return None

    headers = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    if not data_rows:
        return None

    if not any(cell.strip() for cell in headers):
        headers = [f"col_{idx + 1}" for idx in range(max(len(row) for row in rows))]
        data_rows = rows
    else:
        width = max(len(headers), max(len(row) for row in rows))
        headers = [
            cell.strip() if cell.strip() else f"col_{idx + 1}"
            for idx, cell in enumerate(headers + [""] * (width - len(headers)))
        ]

    normalized_rows = []
    width = len(headers)
    for row in data_rows:
        values = [cell.strip() for cell in row[:width]]
        while len(values) < width:
            values.append("")
        if any(values):
            normalized_rows.append(values)

    if not normalized_rows:
        return None

    return {
        "headers": headers,
        "rows": normalized_rows,
        "caption": " ".join(item.get("table_caption", [])),
    }


def _parse_html_table_rows(table_body: str) -> list[list[str]]:
    if not table_body:
        return []

    rows = []
    for row_match in re.findall(r"<tr[^>]*>(.*?)</tr>", table_body, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_match, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        normalized = []
        for cell in cells:
            text = re.sub(r"<[^>]+>", " ", cell)
            text = html.unescape(re.sub(r"\s+", " ", text)).strip()
            normalized.append(text)
        if any(normalized):
            rows.append(normalized)
    return rows


def _run_local_parse_pipeline(task_id: str, filepath: str, filename: str, ext: str, progress_callback):
    """DOCX/XLSX local parsing → chunks → embedding → vector store (no MinerU)."""

    progress_callback("parse", "本地文档解析", 1, {"parse": "running"})
    try:
        from doc_processor import parse_document, chunk_sections, deduplicate_chunks

        sections = parse_document(filepath)
        chunks = chunk_sections(
            sections,
            source_file=filename,
            source_format=ext.lstrip("."),
            level=2,
        )
        chunks = deduplicate_chunks(chunks)
        progress_callback("parse", "本地文档解析", 1, {"parse": "done"})
    except Exception as e:  # noqa: BLE001  # 本地解析失败已通过 progress_callback 上报 failed 并终止该任务，异常不再上抛
        progress_callback("parse", "本地文档解析", 1, {"parse": "failed"}, error=str(e))
        return

    progress_callback("chunk", "文档分块", 2, {"chunk": "running"})
    chunk_count = len(chunks)
    progress_callback("chunk", "文档分块", 2, {"chunk": "done", "count": chunk_count})

    progress_callback("embed", "向量化与存储", 3, {"embed": "running"})
    try:
        from embedding import EmbeddingClient
        from vector_store import VectorStore

        embedding_client = EmbeddingClient()
        texts = [c.text for c in chunks]
        embeddings = embedding_client.embed_texts(texts)

        vector_store = VectorStore()
        vector_store.add_chunks(chunks, embeddings)

        progress_callback("embed", "向量化与存储", 3, {"embed": "done", "chunks": chunk_count})
    except ImportError as e:
        # 向量化是**可选**增强：缺依赖时降级为"仅落盘 chunks"，入库本身仍成功。
        # 必须用 degraded=True —— 否则 progress() 会把任务标成 FAILED，而本函数随后
        # 仍继续执行并返回成功 dict，最终留下一个 status=DONE 却挂着 error 的脏任务。
        progress_callback("embed", "向量化与存储", 3, {"embed": "skipped"},
                         error=f"Missing dependency: {e}. Chunks saved to disk only.",
                         error_code=ErrorCode.PIPELINE_EXTRACTION_ERROR.value,
                         degraded=True)
    except Exception as e:
        logger.error("embed_failed", task_id=task_id, exc_info=True)
        # 同上：这条分支之后仍继续建 BM25/Table 索引并返回成功 dict，
        # 因此也走 degraded 而非 FAILED，避免留下 DONE + 残留 error 的脏任务。
        # 代价是更严重故障不会把任务标失败 —— 待 plan 收尾项评估是否改为 raise 终止。
        progress_callback("embed", "向量化与存储", 3, {"embed": "failed"},
                         error=str(e),
                         error_code=ErrorCode.PIPELINE_EXTRACTION_ERROR.value,
                         degraded=True)

    # Build BM25 + TableIndex after embedding for query-time availability
    progress_callback("index", "BM25 + Table 索引构建", 4, {"index": "running"})
    try:
        from index_registry import (
            build_bm25_from_chunks, build_table_index_from_chunks,
            set_bm25_index, set_table_index,
        )

        bm25 = build_bm25_from_chunks(chunks)
        if bm25 is not None:
            set_bm25_index(bm25)

        ti = build_table_index_from_chunks(chunks)
        if ti is not None:
            set_table_index(ti)

        progress_callback("index", "BM25 + Table 索引构建", 4, {
            "index": "done",
            "bm25_docs": len(chunks) if bm25 else 0,
            "table_rows": ti.count() if ti else 0,
        })
    except Exception as e:
        logger.error("bm25_table_index_failed", task_id=task_id, exc_info=True)
        # BM25/Table 索引是查询期增强，构建失败不影响入库结果本身；
        # 用 degraded 而非 FAILED，避免本函数随后返回成功 dict 留下残留 error。
        progress_callback("index", "BM25 + Table 索引构建", 4, {"index": "failed"},
                         error=str(e),
                         error_code=ErrorCode.PIPELINE_KG_BUILD_ERROR.value,
                         degraded=True)

    # ── Entity extraction + KG build for DOCX/XLSX ──
    progress_callback("extraction", "实体抽取与KG构建", 5, {"extraction": "running"})

    # 全批次失败 → StageExtractionError 冒泡到 run_real_pipeline 顶层包装，
    # 由 routes/ingest.py 判定任务终态；此处不捕获。
    outcome = _extract_and_build_kg(chunks, task_id, filename)
    kg_nodes, kg_edges = outcome.node_count, outcome.edge_count

    if outcome.partial:
        progress_callback(
            "extraction", "实体抽取与KG构建", 5,
            {"extraction": "degraded", "kg_nodes": kg_nodes, "kg_edges": kg_edges,
             "batches_failed": outcome.batches_failed,
             "batches_total": outcome.batches_total},
            error=f"{outcome.batches_failed}/{outcome.batches_total} 批次抽取失败，结果不完整",
            error_code=ErrorCode.PIPELINE_EXTRACTION_EMPTY.value,
            degraded=True,
        )
    elif kg_nodes == 0:
        progress_callback(
            "extraction", "实体抽取与KG构建", 5,
            {"extraction": "done", "kg_nodes": 0, "kg_edges": 0},
            error="未抽取到实体（文档可能非安全生产领域）",
            error_code=ErrorCode.PIPELINE_EXTRACTION_EMPTY.value,
            degraded=True,
        )
    else:
        progress_callback("extraction", "实体抽取与KG构建", 5,
                          {"extraction": "done", "kg_nodes": kg_nodes,
                           "kg_edges": kg_edges})

    doc_id = f"doc_{task_id}"
    # Publish event + audit log
    try:
        from services.event_bus import get_event_bus
        get_event_bus().publish("doc.ingested", {
            "doc_id": doc_id,
            "filename": filename,
            "task_id": task_id,
            "kg_nodes": kg_nodes,
            "kg_edges": kg_edges,
            "kg_version": 1,
            "pages_parsed": len(chunks),
            "duration_seconds": int(time.time()),
        })
    except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，投递失败不影响入库完成
        pass
    try:
        from services.audit_logger import get_audit_logger
        get_audit_logger().log("doc.ingested", doc_id=doc_id,
                               filename=filename, chunks=chunk_count)
    except Exception:  # noqa: S110, BLE001  # 审计写入失败不阻断业务主流程
        pass

    return {
        "document_id": doc_id,
        "kg_nodes": kg_nodes,
        "kg_edges": kg_edges,
        "grounded_entities": kg_nodes,
        "entity_types": 0,
        "pages_parsed": len(chunks),
        "kg_path": os.path.join(os.path.dirname(__file__), "output", "kg", f"doc_{task_id}"),
        "chunks": chunk_count,
        "partial": outcome.partial,
        "warnings": ([f"{outcome.batches_failed}/{outcome.batches_total} 批次抽取失败"]
                     if outcome.partial else []),
    }


def _extract_and_build_kg(chunks, task_id: str, filename: str) -> ExtractionOutcome:
    """用 Ollama qwen2.5:7b 对 chunks 做实体关系抽取，构建 KG。

    失败语义（显式，不再用 (0,0) 掩盖）：
      - 全部批次失败 → raise StageExtractionError（携带首个根因）
      - 部分批次失败 → 返回 batches_failed > 0 的 outcome，调用方标 degraded
      - 成功但零实体 → 返回 0/0 的 outcome，调用方记 EMPTY 提示
    """
    MAX_CHUNKS = 50
    BATCH_SIZE = 5
    OLLAMA_URL = "http://localhost:11434/api/chat"
    MODEL = "qwen2.5:7b"

    PROMPT = (
        "从以下文本中抽取安全生产领域的实体和关系。只输出合法JSON。"
        "实体类型: 制度, 机构, 人员, 行为, 设备, 场所, 标准, 其他。"
        "关系类型: 建立, 监管, 执行, 违反, 包含, 关联。"
        '输出格式: {"entities":[{"name":"实体名","type":"类型"}],'
        '"relations":[{"subject":"主体","predicate":"关系","object":"客体"}]}'
        "\n\n文本:\n"
    )

    sample = chunks[:MAX_CHUNKS]
    all_entities: dict[str, dict] = {}
    all_edges: list[dict] = []
    edge_set: set[tuple] = set()

    batches_total = 0
    batches_failed = 0
    first_error: PipelineError | None = None

    for i in range(0, len(sample), BATCH_SIZE):
        batch = sample[i:i + BATCH_SIZE]
        text = "\n\n".join(c.text for c in batch if hasattr(c, "text"))
        if not text.strip():
            continue

        batches_total += 1

        try:
            import requests
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL,
                      "messages": [{"role": "user", "content": PROMPT + text[:4000]}],
                      "format": "json", "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            result = json.loads(resp.json()["message"]["content"])
        except Exception as exc:  # noqa: BLE001  # 批次抽取失败已显式计数并保留根因，不再静默跳过
            # 改造前这里是 `except Exception: continue` —— 批次失败被静默跳过，
            # 调用方看到 (0,0) 会误判为"文档无实体"。现在显式计数并留根因。
            batches_failed += 1
            mapped = classify_external_error(
                exc, stage=PipelineStage.EXTRACTION, provider="ollama",
                task_id=task_id,
            )
            if first_error is None:
                first_error = mapped
            logger.warning(
                "extraction_batch_failed", task_id=task_id, batch_index=i,
                batch_size=len(batch), error_code=mapped.code.value,
                provider="ollama", exc_info=True,
            )
            continue

        for e in result.get("entities", []):
            name = e.get("name", "")
            if name and name not in all_entities:
                all_entities[name] = {
                    "node_id": f"n{len(all_entities)+1:05d}",
                    "label": name,
                    "entity_type": e.get("type", "其他"),
                    "grounding_status": "grounded",
                    "page_idx": 0,
                    "bbox_norm": None,
                }

        for r in result.get("relations", []):
            subj = r.get("subject", "")
            obj = r.get("object", "")
            pred = r.get("predicate", "关联")
            if subj and obj and subj in all_entities and obj in all_entities:
                key = (subj, obj, pred)
                if key not in edge_set:
                    edge_set.add(key)
                    all_edges.append({
                        "source_node_id": all_entities[subj]["node_id"],
                        "target_node_id": all_entities[obj]["node_id"],
                        "relation_type": pred,
                    })

    # 全部批次都失败 → 这是失败，不是"零实体"
    if batches_total and batches_failed == batches_total:
        raise StageExtractionError(
            "实体抽取全部批次失败",
            code=ErrorCode.PIPELINE_EXTRACTION_EMPTY,
            context=ErrorContext(
                provider="ollama", stage=PipelineStage.EXTRACTION,
                task_id=task_id, retryable=True,
                details={
                    "batches_total": batches_total,
                    "batches_failed": batches_failed,
                    "root_error": first_error.code.value if first_error else None,
                },
            ),
        ) from first_error

    if not all_entities:
        # 成功执行但确实没抽到实体 —— 正常返回，由调用方记 EMPTY 提示
        return ExtractionOutcome(0, 0, batches_total, batches_failed, first_error)

    kg_dir = os.path.join(os.path.dirname(__file__), "output", "kg", f"doc_{task_id}")
    os.makedirs(kg_dir, exist_ok=True)
    with open(os.path.join(kg_dir, "nodes.json"), "w", encoding="utf-8") as f:
        json.dump({"nodes": list(all_entities.values())}, f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(kg_dir, "edges.json"), "w", encoding="utf-8") as f:
        json.dump({"edges": all_edges}, f, ensure_ascii=False, indent=2)

    return ExtractionOutcome(len(all_entities), len(all_edges),
                             batches_total, batches_failed, first_error)


def _upload_to_public(filepath: str) -> str | None:
    """Upload file to public hosting via OSS (阿里云OSS) - NO FALLBACK."""

    logger.info("oss_upload_started", filepath=filepath)

    # 只使用OSS，不使用其他fallback
    try:
        from oss_uploader import upload_to_oss
        import uuid

        # 生成唯一文件名
        filename = os.path.basename(filepath)
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"

        logger.info("oss_upload_calling", object_name=unique_name)
        url = upload_to_oss(filepath, unique_name)
        logger.info("oss_upload_ok", url=url)
        return url
    except Exception as e:
        logger.error("oss_upload_failed", filepath=filepath, error=str(e), exc_info=True)
        # 不再fallback到file.io或transfer.sh
        return None


def _find_cached_mineru_output(root: str | None = None) -> str | None:
    """兼容旧调用方；未提供内容哈希及配置版本匹配契约前禁止缓存复用。"""
    return None


def _mineru_output_dir(task_id: str) -> str:
    """完整任务标识作为目录名；拒绝路径字符及 Windows 保留设备名。"""
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", task_id)
            or task_id.upper() in reserved):
        raise StageMinerUError(
            "任务标识包含不安全字符或保留名称",
            code=ErrorCode.PIPELINE_MINERU_PARSE,
            context=ErrorContext(provider="mineru", stage=PipelineStage.MINERU,
                                 task_id=task_id, retryable=False),
        )
    return os.path.join(os.path.dirname(__file__), "output", "mineru", task_id)


def _call_mineru_api(file_url: str, token: str, task_id: str,
                     ingest_options: dict | None = None) -> str:
    """URL 模式：提交公网 URL → 轮询 → 下载解压，返回输出目录。

    传输细节见 mineru_client；本函数只剩编排（提交→轮询→落盘）。
    失败一律 raise StageMinerUError，使调用方能区分 401 / 429 / 5xx / 超时 / 业务码。
    """
    output_dir = _mineru_output_dir(task_id)
    handle = submit_url_task(file_url, token, task_id, ingest_options)
    zip_url = poll_until_done(handle, token, task_id=task_id)
    return download_and_extract(
        zip_url,
        output_dir,
        task_id=task_id,
    )


def _call_mineru_local_file(filepath: str, token: str, task_id: str,
                            ingest_options: dict | None = None) -> str:
    """本地文件模式：**直传 MinerU**（默认路径）→ 轮询 → 下载解压。

    与 `_call_mineru_api` 契约一致（成功返回目录，失败 raise StageMinerUError），
    调用方可用同一个 except 处理。

    为何走直传而非自建对象存储：MinerU 提供预签名上传 URL
    （POST /api/v4/file-urls/batch），本地文件可直传，无需 OSS。
    2026-09-18 实测：OSS AccessKey 被禁用（403 InvalidAccessKeyId: disabled），
    而直传全链路 24 秒通过。
    """
    output_dir = _mineru_output_dir(task_id)
    handle = submit_local_file(
        token, local_path=filepath, filename=os.path.basename(filepath),
        task_id=task_id, ingest_options=ingest_options,
    )
    zip_url = poll_until_done(handle, token, task_id=task_id)
    return download_and_extract(
        zip_url,
        output_dir,
        task_id=task_id,
    )


def _run_langextract(documents):
    """Run LangExtract on the documents using DeepSeek."""
    import langextract as lx
    from langextract.factory import ModelConfig

    examples_path = os.path.join(os.path.dirname(__file__), "config", "extraction_examples.yaml")
    with open(examples_path, encoding="utf-8") as f:
        examples_data = yaml.safe_load(f)

    examples = []
    for ex in examples_data.get("examples", []):
        import langextract.core.data as lxdata
        extractions = []
        for ext in ex.get("extractions", []):
            extractions.append(lxdata.Extraction(
                extraction_class=ext["extraction_class"],
                extraction_text=ext["extraction_text"],
                attributes=ext.get("attributes"),
            ))
        examples.append(lxdata.ExampleData(text=ex["text"], extractions=extractions))

    config = ModelConfig(
        model_id=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-flash"),
        provider="openai",
        provider_kwargs={
            "api_key": os.getenv("LANGEXTRACT_API_KEY"),
            "base_url": os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
            **non_thinking_provider_options(os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-flash")),
        },
    )

    prompt = (
        "Extract structured entities from enterprise project documents: "
        "project_metadata (project_id/name/type/phase/budget), "
        "person_role (name/role/department/contact), "
        "process_step (step_name/order/approver/deadline), "
        "metric (name/value/unit/target/actual), "
        "milestone (name/planned_date/actual_date/status), "
        "deliverable (name/type/acceptance_criteria/status), "
        "risk_item (risk_desc/level/probability/impact/mitigation), "
        "regulation_ref (title/doc_id/version/effective_date), "
        "department (dept_name/parent_dept/head/responsibilities), "
        "timeline_event (event_name/date/related_entities). "
        "Use exact text for extraction_text. Provide meaningful attributes."
    )

    results = lx.extract(
        text_or_documents=documents,
        prompt_description=prompt,
        examples=examples,
        config=config,
        temperature=0.0,
        max_char_buffer=3000,
        context_window_chars=200,
        use_schema_constraints=False,
        fence_output=True,
        batch_length=5,
        max_workers=3,
        show_progress=False,
    )
    return results if isinstance(results, list) else [results]
