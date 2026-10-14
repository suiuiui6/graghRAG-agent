#!/usr/bin/env python3
"""
MinerU → LangExtract 集成 Pipeline

Stage 1: MinerU cloud API parsing (or reuse cached output)
Stage 2: Format bridge — full.md → list[Document] + PositionMap
Stage 3: LangExtract entity extraction via DeepSeek
Stage 4: Source grounding — char_interval → bbox + page_idx
Stage 5: Knowledge graph construction → nodes.json + edges.json

Usage:
    # Full pipeline (with MinerU API call)
    python pipeline.py --pdf ./input/sample.pdf

    # Skip MinerU (use cached output)
    python pipeline.py --cached ./mineru_output/87bc1f56
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Add LangExtract to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "langextract"))

import langextract as lx
import yaml
from langextract.core.data import Document, ExampleData, Extraction
from langextract.factory import ModelConfig

from bridge import (
    build_documents,
    build_position_map,
    find_section_boundaries,
    load_content_list,
    load_full_md,
)
from grounding import grounding_stats, resolve_grounding
from kg_builder import build_knowledge_graph, print_kg_summary, serialize_kg
from schema import KGNode, PositionMap


# ============================================================
# Stage 1: MinerU (reuse existing runner or load cached)
# ============================================================

def run_mineru(local_pdf: str | None = None, file_url: str | None = None) -> str:
    """Run MinerU API and return output directory path.

    Uses curl-based approach (Python requests blocked in this env).
    """
    import subprocess
    import tempfile

    token = os.getenv("MINERU_API_TOKEN", "")
    base = os.getenv("MINERU_API_BASE_URL", "https://mineru.net/api/v4/extract/task")
    language = os.getenv("MINERU_LANGUAGE", "en")
    model_ver = os.getenv("MINERU_MODEL_VERSION", "pipeline")
    max_wait = int(os.getenv("MINERU_MAX_WAIT_SECONDS", "600"))
    poll_interval = int(os.getenv("MINERU_POLL_INTERVAL", "5"))

    # Resolve file to URL
    if file_url:
        the_url = file_url
    elif local_pdf:
        # Try uploading
        the_url = _upload_local(local_pdf)
    else:
        raise ValueError("Need --pdf or --url")

    print(f"[Stage 1] Submitting: {the_url[:80]}...")

    # Submit
    payload = json.dumps({
        "url": the_url,
        "language": language,
        "enable_formula": True,
        "enable_table": True,
        "model_version": model_ver,
    })
    submit_result = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-X", "POST", base,
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Bearer {token}",
         "-d", payload],
        capture_output=True, text=True, timeout=35,
    )
    task_data = json.loads(submit_result.stdout)
    if task_data.get("code") != 0:
        raise RuntimeError(f"Submit failed: {task_data}")
    task_id = task_data["data"]["task_id"]
    print(f"  task_id: {task_id}")

    # Poll
    elapsed = 0
    while elapsed < max_wait:
        poll_result = subprocess.run(
            ["curl", "-s", "--max-time", "20", f"{base}/{task_id}",
             "-H", f"Authorization: Bearer {token}"],
            capture_output=True, text=True, timeout=25,
        )
        poll_data = json.loads(poll_result.stdout)["data"]
        state = poll_data["state"]
        progress = poll_data.get("extract_progress", {})
        pages = f"{progress.get('extracted_pages', '?')}/{progress.get('total_pages', '?')}"
        sys.stdout.write(f"\r  [{state}] {elapsed}s | Pages: {pages}  ")
        sys.stdout.flush()

        if state == "done":
            zip_url = poll_data["full_zip_url"]
            print()
            break
        if state == "failed":
            raise RuntimeError(f"Parse failed: {poll_data.get('err_msg')}")
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Timeout after {max_wait}s")

    # Download & extract
    output_dir = os.path.join(os.path.dirname(__file__), "output", "mineru", task_id[:8])
    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, "result.zip")

    subprocess.run(
        ["curl", "-s", "-o", zip_path, zip_url],
        check=True, timeout=120,
    )
    subprocess.run(
        ["unzip", "-o", zip_path, "-d", output_dir],
        check=True, timeout=30,
    )
    os.remove(zip_path)
    print(f"  Output: {output_dir}")
    return output_dir


def _upload_local(pdf_path: str) -> str:
    """Upload local PDF to get public URL."""
    import subprocess

    # Try file.io
    result = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-F", f"file=@{pdf_path}",
         "https://file.io"],
        capture_output=True, text=True, timeout=35,
    )
    try:
        data = json.loads(result.stdout)
        if data.get("success"):
            return data["link"]
    except (json.JSONDecodeError, KeyError):
        pass

    raise RuntimeError(
        "Cannot upload PDF automatically. Please set FILE_URL in .env "
        "to a publicly accessible URL of your PDF."
    )


# ============================================================
# Stage 2: Format Bridge
# ============================================================

def run_bridge(mineru_output_dir: str) -> tuple[list[Document], dict, PositionMap, str]:
    """Convert MinerU output to LangExtract input."""
    print(f"\n[Stage 2] Building format bridge...")

    # Locate files
    md_path = os.path.join(mineru_output_dir, "full.md")
    cl_pattern = os.path.join(mineru_output_dir, "*_content_list.json")
    cl_files = glob.glob(cl_pattern)
    cl_files = [f for f in cl_files if "_v2" not in f]  # Use v1

    if not cl_files:
        raise FileNotFoundError(f"No content_list found in {mineru_output_dir}")

    cl_path = cl_files[0]
    print(f"  full.md:     {md_path}")
    print(f"  content_list:{os.path.basename(cl_path)}")

    content_list = load_content_list(cl_path)
    full_md = load_full_md(md_path)
    print(f"  Content items: {len(content_list)}")
    print(f"  Full.md chars: {len(full_md)}")

    # Build position map
    position_map = build_position_map(content_list, full_md)
    print(f"  PositionMap segments: {len(position_map.segments)}")

    # Find section boundaries
    min_level = int(os.getenv("SECTION_MIN_LEVEL", "2"))
    sections = find_section_boundaries(content_list, full_md, position_map, min_level)
    print(f"  Sections: {len(sections)}")

    for s in sections:
        sec_len = s.char_end - s.char_start
        print(f"    [{s.document_id}] L{s.heading_level} "
              f"\"{s.title[:50]}\" ({sec_len} chars)")

    # Build Documents
    documents, offsets = build_documents(sections, full_md)
    print(f"  Documents built: {len(documents)}")

    return documents, offsets, position_map, full_md


# ============================================================
# Stage 3: LangExtract
# ============================================================

def load_examples(examples_path: str):
    """Load few-shot examples from YAML file."""
    with open(examples_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    examples = []
    for ex_data in data.get("examples", []):
        extractions = []
        for ext in ex_data.get("extractions", []):
            extractions.append(Extraction(
                extraction_class=ext["extraction_class"],
                extraction_text=ext["extraction_text"],
                attributes=ext.get("attributes"),
            ))
        examples.append(ExampleData(
            text=ex_data["text"],
            extractions=extractions,
        ))
    return examples


def run_langextract(
    documents: list[Document],
    examples_path: str,
    prompt_description: str,
) -> list:
    """Run LangExtract entity extraction."""
    print(f"\n[Stage 3] Running LangExtract extraction...")
    print(f"  Documents: {len(documents)}")
    print(f"  Examples:  {examples_path}")

    examples = load_examples(examples_path)
    print(f"  Few-shot examples loaded: {len(examples)}")

    config = ModelConfig(
        model_id=os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
        provider="openai",
        provider_kwargs={
            "api_key": os.getenv("LANGEXTRACT_API_KEY"),
            "base_url": os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
        },
    )

    total_chars = sum(len(d.text) for d in documents)
    print(f"  Total chars: {total_chars}")

    results = lx.extract(
        text_or_documents=documents,
        prompt_description=prompt_description,
        examples=examples,
        config=config,
        temperature=float(os.getenv("LANGEXTRACT_TEMPERATURE", "0.0")),
        max_char_buffer=int(os.getenv("LANGEXTRACT_MAX_CHAR_BUFFER", "3000")),
        context_window_chars=int(os.getenv("LANGEXTRACT_CONTEXT_WINDOW_CHARS", "200")),
        extraction_passes=int(os.getenv("LANGEXTRACT_EXTRACTION_PASSES", "1")),
        use_schema_constraints=False,
        fence_output=True,
        batch_length=5,
        max_workers=5,
        show_progress=True,
    )

    results_list = results if isinstance(results, list) else [results]

    # Print per-document summary
    total_extractions = 0
    total_grounded = 0
    for adoc in results_list:
        exts = adoc.extractions or []
        grounded = sum(1 for e in exts if e.char_interval is not None)
        total_extractions += len(exts)
        total_grounded += grounded

    print(f"  Total extractions: {total_extractions}")
    print(f"  Grounded: {total_grounded}")
    print(f"  Ungrounded: {total_extractions - total_grounded}")

    return results_list


# ============================================================
# Stage 4 + 5: Grounding + KG
# ============================================================

def run_grounding_and_kg(
    annotated_docs: list,
    position_map,
    document_offsets: dict,
    output_dir: str,
) -> tuple[str, str]:
    """Run grounding resolution and KG construction."""
    print(f"\n[Stage 4] Resolving source grounding...")
    grounded = resolve_grounding(annotated_docs, position_map, document_offsets)
    stats = grounding_stats(grounded)
    print(f"  Total: {stats['total']}, Grounded: {stats['grounded']}, "
          f"Rate: {stats['grounding_rate']:.1%}")

    print(f"\n[Stage 5] Building Knowledge Graph...")
    nodes, edges = build_knowledge_graph(grounded)

    metadata = {
        "pipeline": "MinerU → LangExtract",
        "model": os.getenv("LANGEXTRACT_MODEL_ID", "deepseek-chat"),
        "timestamp": datetime.now().isoformat(),
    }

    nodes_path, edges_path = serialize_kg(nodes, edges, metadata, output_dir)
    print_kg_summary(nodes, edges)

    return nodes_path, edges_path


# ============================================================
# Main
# ============================================================

DEFAULT_PROMPT = """\
Extract structured entities from the academic paper text:

- paper_metadata: title, author names/affiliations, venue, date
- section_header: section headings with hierarchy level (1-6)
- model_component: named model parts (layers, mechanisms, modules, functions)
- metric: quantitative results (score, percentage, measurement) with context
- dataset: referenced datasets/benchmarks with task name
- method: techniques, algorithms, training strategies
- definition: explicitly defined terms, notations, or concepts
- equation: important mathematical formulas in LaTeX
- reference: citations with paper key and context
- claim: key findings, observations, or conclusions

Use exact text from the source for extraction_text. Do not paraphrase.
Provide meaningful attributes for each entity type."""


def main():
    parser = argparse.ArgumentParser(description="MinerU → LangExtract KG Pipeline")
    parser.add_argument("--pdf", help="Local PDF to parse")
    parser.add_argument("--url", help="Public URL of PDF")
    parser.add_argument("--cached", help="Use cached MinerU output directory")
    parser.add_argument("--examples", default="./config/extraction_examples.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    output_base = args.output or os.getenv("OUTPUT_DIR", "./output/kg")
    os.makedirs(output_base, exist_ok=True)

    print("=" * 60)
    print("  MinerU → LangExtract Knowledge Graph Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Stage 1: MinerU
    if args.cached:
        mineru_dir = args.cached
        print(f"\n[Stage 1] SKIP — using cached: {mineru_dir}")
    elif args.pdf or args.url:
        mineru_dir = run_mineru(local_pdf=args.pdf, file_url=args.url)
    else:
        print("[ERROR] Need --pdf, --url, or --cached")
        sys.exit(1)

    # Stage 2: Bridge
    documents, offsets, position_map, full_md = run_bridge(mineru_dir)

    # Stage 3: LangExtract
    annotated = run_langextract(documents, args.examples, args.prompt)

    # Save intermediate JSONL
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = os.path.join(output_base, f"integrated_{ts}.jsonl")
    lx.io.save_annotated_documents(annotated, output_dir=output_base,
                                    output_name=os.path.basename(jsonl_path),
                                    show_progress=False)
    print(f"\n  Intermediate JSONL: {jsonl_path}")

    # Stage 4 + 5: Grounding + KG
    nodes_path, edges_path = run_grounding_and_kg(
        annotated, position_map, offsets, output_base,
    )

    print(f"\n{'=' * 60}")
    print(f"  Pipeline Complete")
    print(f"  Nodes: {nodes_path}")
    print(f"  Edges: {edges_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
