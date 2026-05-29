"""
Real document indexing worker — MinerU → BridgePipeline → LangExtract → KG.

Replaces the simulated pipeline in routes/ingest.py.
Uses curl subprocess for network calls (Python requests blocked in this env).
"""

import glob
import json
import os
import uuid

from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=True)  # Force override system environment variables
import re
import subprocess
import sys
import time
import yaml
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from bridge import (
    build_documents, build_position_map, find_section_boundaries,
    load_content_list, load_full_md,
)
from grounding import grounding_stats, resolve_grounding
from kg_builder import build_knowledge_graph, serialize_kg

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")


def run_real_pipeline(task_id: str, filepath: str, filename: str, progress_callback):
    """Execute the full MinerU → BridgePipeline → LangExtract → KG pipeline."""

    env_file_url = os.getenv("FILE_URL", "").strip()

    # ── Stage 0: Determine MinerU output directory ──
    mineru_dir = None

    # Always try OSS upload first for local files
    if not (filepath.startswith("http://") or filepath.startswith("https://")):
        # ── Path A: Local file - upload to OSS ──
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "uploading_to_oss"})

        try:
            public_url = _upload_to_public(filepath)

            if public_url:
                # Successfully uploaded to OSS, use MinerU API
                progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "calling_api"})
                token = os.getenv("MINERU_API_TOKEN", "")
                mineru_dir = _call_mineru_api(public_url, token, task_id)

                if mineru_dir:
                    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
                else:
                    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "failed"},
                                    error="MinerU API调用失败")
                    return
            else:
                # Upload failed, try local cache
                progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "checking_cache"})
                output_mineru = os.path.join(os.path.dirname(__file__), "output", "mineru")
                if os.path.isdir(output_mineru):
                    for entry in sorted(os.listdir(output_mineru), reverse=True):
                        entry_path = os.path.join(output_mineru, entry)
                        if not os.path.isdir(entry_path):
                            continue
                        full_md_test = os.path.join(entry_path, "full.md")
                        cl_files_test = glob.glob(os.path.join(entry_path, "*_content_list.json"))
                        cl_files_test = [f for f in cl_files_test if "_v2" not in f]
                        if os.path.exists(full_md_test) and cl_files_test:
                            mineru_dir = entry_path
                            break

                if mineru_dir:
                    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})
                else:
                    progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "failed"},
                        error="OSS上传失败且无本地缓存。请检查OSS配置或使用URL模式上传。")
                    return
        except Exception as e:
            progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "failed"},
                error=f"处理失败: {str(e)}")
            return
    else:
        # ── Path B: URL mode - direct MinerU API call ──
        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "running"})
        public_url = filepath
        token = os.getenv("MINERU_API_TOKEN", "")
        mineru_dir = _call_mineru_api(public_url, token, task_id)

        if not mineru_dir:
            progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "failed"},
                            error="MinerU API调用失败")
            return

        progress_callback("mineru", "MinerU 文档解析", 1, {"mineru": "done"})

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
    except Exception as e:
        progress_callback("bridge", "Format Bridge 分段", 2, {"bridge": "failed"}, error=str(e))
        return

    # ── Stage 4: LangExtract ──
    progress_callback("extraction", "LangExtract 实体抽取", 3, {"extraction": "running"})
    try:
        annotated = _run_langextract(documents)
        progress_callback("extraction", "LangExtract 实体抽取", 3, {"extraction": "done"})
    except Exception as e:
        progress_callback("extraction", "LangExtract 实体抽取", 3, {"extraction": "failed"}, error=str(e))
        return

    # ── Stage 5: Grounding + KG ──
    progress_callback("grounding", "Grounding 溯源解析", 4, {"grounding": "running"})
    try:
        grounded = resolve_grounding(annotated, position_map, doc_offsets)
        stats = grounding_stats(grounded)
        progress_callback("grounding", "Grounding 溯源解析", 4, {"grounding": "done"})
    except Exception as e:
        progress_callback("grounding", "Grounding 溯源解析", 4, {"grounding": "failed"}, error=str(e))
        return

    progress_callback("kg_build", "KG 知识图谱构建", 5, {"kg_build": "running"})
    try:
        nodes, edges = build_knowledge_graph(grounded)
        kg_dir = os.path.join(os.path.dirname(__file__), "output", "kg", f"doc_{task_id}")
        nodes_path, _ = serialize_kg(nodes, edges, {}, kg_dir)
        progress_callback("kg_build", "KG 知识图谱构建", 5, {"kg_build": "done"})
    except Exception as e:
        progress_callback("kg_build", "KG 知识图谱构建", 5, {"kg_build": "failed"}, error=str(e))
        return

    # Return result
    return {
        "document_id": f"doc_{task_id}",
        "kg_nodes": len(nodes),
        "kg_edges": len(edges),
        "grounded_entities": stats["grounded"],
        "entity_types": len(set(n.entity_type for n in nodes)),
        "pages_parsed": len(sections),
        "kg_path": kg_dir,
    }


def _upload_to_public(filepath: str) -> str | None:
    """Upload file to public hosting via OSS (阿里云OSS) - NO FALLBACK."""

    print(f"[_upload_to_public] 开始上传文件: {filepath}")

    # 只使用OSS，不使用其他fallback
    try:
        from oss_uploader import upload_to_oss
        import uuid

        # 生成唯一文件名
        filename = os.path.basename(filepath)
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"

        print(f"[_upload_to_public] 调用 upload_to_oss: {unique_name}")
        url = upload_to_oss(filepath, unique_name)
        print(f"[_upload_to_public] ✅ OSS上传成功: {url}")
        return url
    except Exception as e:
        print(f"[_upload_to_public] ❌ OSS上传失败: {e}")
        import traceback
        traceback.print_exc()
        # 不再fallback到file.io或transfer.sh
        return None


def _call_mineru_api(file_url: str, token: str, task_id: str) -> str | None:
    """Submit to MinerU, poll, download ZIP, return output dir."""
    base = os.getenv("MINERU_API_BASE_URL", "https://mineru.net/api/v4/extract/task")

    # Submit
    payload = json.dumps({"url": file_url, "language": "en", "enable_formula": True, "enable_table": True, "model_version": "pipeline"})
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-X", "POST", base,
             "-H", "Content-Type: application/json", "-H", f"Authorization: Bearer {token}", "-d", payload],
            capture_output=True, text=True, timeout=35,
        )
        data = json.loads(result.stdout)
        if data.get("code") != 0:
            return None
        mineru_task_id = data["data"]["task_id"]
    except Exception:
        return None

    # Poll
    for _ in range(120):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "20", f"{base}/{mineru_task_id}",
                 "-H", f"Authorization: Bearer {token}"],
                capture_output=True, text=True, timeout=25,
            )
            data = json.loads(result.stdout)["data"]
            if data["state"] == "done":
                zip_url = data["full_zip_url"]
                break
            if data["state"] == "failed":
                return None
        except Exception:
            pass
        time.sleep(5)
    else:
        return None

    # Download & extract
    output_dir = os.path.join(os.path.dirname(__file__), "output", "mineru", task_id[:8])
    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, "result.zip")
    try:
        subprocess.run(["curl", "-s", "-o", zip_path, zip_url], check=True, timeout=120)
        subprocess.run(["unzip", "-o", zip_path, "-d", output_dir], check=True, timeout=30)
        os.remove(zip_path)
    except Exception:
        return None

    return output_dir


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
        model_id=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
        provider="openai",
        provider_kwargs={
            "api_key": os.getenv("LANGEXTRACT_API_KEY"),
            "base_url": os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
        },
    )

    prompt = (
        "Extract structured entities: paper_metadata (title/authors/affiliations), "
        "section_header, model_component, metric (scores/percentages), dataset, "
        "method (techniques/algorithms), definition, equation, reference, claim. "
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
