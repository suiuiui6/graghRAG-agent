#!/usr/bin/env python3
"""
MinerU 云端 API — MVP 测试 Pipeline

流程:
  1. 加载 .env 配置
  2. 确定文件来源（公网 URL 或本地 PDF）
  3. 若为本地文件 → 上传至临时托管服务获取公网 URL
  4. 提交 MinerU 云端解析任务
  5. 轮询等待任务完成
  6. 下载解析结果 ZIP 包并解压
  7. 输出结果摘要

依赖: pip install -r requirements.txt
"""

import io
import json
import os
import sys
import time
import zipfile
from datetime import datetime

import requests
from dotenv import load_dotenv


# ============================================================
# 配置加载
# ============================================================

def load_config() -> dict:
    """从 .env 文件加载配置，返回配置字典。"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        print("[错误] .env 文件未找到，请从 .env.example 复制并填入实际值。")
        sys.exit(1)

    load_dotenv(env_path)

    token = os.getenv("MINERU_API_TOKEN", "")
    if not token or token == "your-token-here":
        print("[错误] MINERU_API_TOKEN 未设置，请在 .env 文件中填入有效 Token。")
        sys.exit(1)

    config = {
        "api_token": token,
        "api_base_url": os.getenv("MINERU_API_BASE_URL",
                                   "https://mineru.net/api/v4/extract/task"),
        "file_url": os.getenv("FILE_URL", "").strip(),
        "local_pdf_path": os.getenv("LOCAL_PDF_PATH", "./sample.pdf").strip(),
        "language": os.getenv("LANGUAGE", "ch"),
        "is_ocr": os.getenv("IS_OCR", "false").lower() == "true",
        "enable_formula": os.getenv("ENABLE_FORMULA", "true").lower() == "true",
        "enable_table": os.getenv("ENABLE_TABLE", "true").lower() == "true",
        "model_version": os.getenv("MODEL_VERSION", "pipeline"),
        "output_dir": os.getenv("OUTPUT_DIR", "./output"),
        "max_wait_seconds": int(os.getenv("MAX_WAIT_SECONDS", "300")),
        "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "3")),
    }
    return config


# ============================================================
# 文件上传（本地 PDF → 公网 URL）
# ============================================================

def upload_to_file_io(local_path: str) -> str | None:
    """上传文件到 file.io，返回公网下载 URL。"""
    print("[上传] 正在上传到 file.io ...")
    try:
        with open(local_path, "rb") as f:
            resp = requests.post("https://file.io", files={"file": f}, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    url = data.get("link")
                    print(f"[上传] 成功: {url}")
                    return url
                else:
                    print(f"[上传] file.io 返回错误: {data}")
    except requests.RequestException as e:
        print(f"[上传] file.io 请求失败: {e}")
    return None


def upload_to_transfer_sh(local_path: str) -> str | None:
    """上传文件到 transfer.sh，返回公网下载 URL。"""
    print("[上传] 正在上传到 transfer.sh ...")
    try:
        filename = os.path.basename(local_path)
        with open(local_path, "rb") as f:
            resp = requests.put(
                f"https://transfer.sh/{filename}",
                data=f,
                timeout=120,
            )
            if resp.status_code == 200:
                url = resp.text.strip()
                print(f"[上传] 成功: {url}")
                return url
            else:
                print(f"[上传] transfer.sh 返回 {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"[上传] transfer.sh 请求失败: {e}")
    return None


def upload_local_file(local_path: str) -> str:
    """尝试多种方式上传本地文件，返回公网 URL。"""
    if not os.path.exists(local_path):
        print(f"[错误] 本地文件不存在: {local_path}")
        print("[提示] 请先运行 generate_sample_pdf.py 生成示例 PDF，")
        print("        或在 .env 的 FILE_URL 中填入已有公网文件地址。")
        sys.exit(1)

    # 尝试多种上传服务
    for uploader in (upload_to_file_io, upload_to_transfer_sh):
        url = uploader(local_path)
        if url:
            return url

    # 全部失败
    print("\n[错误] 所有上传服务均失败。请使用以下替代方案之一：")
    print("  1. 将 PDF 手动上传至云存储（阿里云 OSS / 腾讯云 COS / GitHub），")
    print(f"     在 .env 中设置 FILE_URL=<你的公网地址>")
    print("  2. 使用本地 MinerU API 部署替代云端 API")
    print(f"  3. 检查网络连接，确保可访问 file.io / transfer.sh")
    sys.exit(1)


def resolve_file_url(config: dict) -> str:
    """确定最终使用的公网文件 URL。优先使用 FILE_URL，否则上传本地文件。"""
    if config["file_url"]:
        print(f"[文件] 使用配置的公网 URL: {config['file_url'][:80]}...")
        return config["file_url"]

    local_path = config["local_pdf_path"]
    abs_path = os.path.join(os.path.dirname(__file__), local_path)
    print(f"[文件] 使用本地文件: {abs_path}")
    return upload_local_file(abs_path)


# ============================================================
# MinerU API 调用
# ============================================================

class MinerUClient:
    """MinerU 云端 API 客户端。"""

    def __init__(self, config: dict):
        self.base_url = config["api_base_url"]
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_token']}",
        }
        self.max_wait = config["max_wait_seconds"]
        self.poll_interval = config["poll_interval_seconds"]

    def submit(self, file_url: str, parse_config: dict) -> str:
        """提交解析任务，返回 task_id。"""
        payload = {"url": file_url, **parse_config}
        print(f"\n[提交] 正在提交解析任务...")
        print(f"   URL: {file_url[:80]}...")
        print(f"   参数: {json.dumps(parse_config, ensure_ascii=False)}")

        resp = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(
                f"提交失败 [code={data.get('code')}]: {data.get('msg', 'Unknown error')}"
            )

        task_id = data["data"]["task_id"]
        print(f"   task_id: {task_id}")
        return task_id

    def poll(self, task_id: str) -> dict:
        """轮询任务状态，直到完成或超时。返回完成响应 data。"""
        url = f"{self.base_url}/{task_id}"
        elapsed = 0
        print(f"\n[轮询] 等待任务完成 (最多 {self.max_wait}s)...")

        while elapsed < self.max_wait:
            resp = requests.get(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data", {})
            state = data.get("state", "unknown")

            progress = data.get("extract_progress", {})
            pages_done = progress.get("extracted_pages", "?")
            pages_total = progress.get("total_pages", "?")

            bar = "=" * (elapsed // self.poll_interval) + ">"
            sys.stdout.write(
                f"\r   [{state}] {bar} {elapsed}s | Pages: {pages_done}/{pages_total}  "
            )
            sys.stdout.flush()

            if state == "done":
                print("\n")
                return data
            if state == "failed":
                print("\n")
                raise RuntimeError(f"解析失败: {data.get('err_msg', 'Unknown error')}")

            time.sleep(self.poll_interval)
            elapsed += self.poll_interval

        raise TimeoutError(f"任务超时: 等待 {self.max_wait}s 未完成 (task_id={task_id})")


# ============================================================
# 结果下载与提取
# ============================================================

def download_and_extract(zip_url: str, output_dir: str) -> str:
    """下载 ZIP 包并解压到指定目录，返回解压后的文件夹路径。"""
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n[下载] 正在下载结果 ZIP ...")
    resp = requests.get(zip_url, timeout=120, stream=True)
    resp.raise_for_status()

    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    chunks = []

    for chunk in resp.iter_content(chunk_size=8192):
        chunks.append(chunk)
        downloaded += len(chunk)
        if total:
            pct = downloaded / total * 100
            bar_len = int(pct / 5)
            sys.stdout.write(f"\r   [{'=' * bar_len}{' ' * (20 - bar_len)}] {pct:.0f}%")
            sys.stdout.flush()
    print()

    content = b"".join(chunks)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        zf.extractall(output_dir)

    print(f"[解压] 完成 → {os.path.abspath(output_dir)}")
    return output_dir


def print_results_summary(output_dir: str):
    """打印解析结果的摘要信息。"""
    files = sorted(os.listdir(output_dir))
    print(f"\n{'=' * 60}")
    print(f"  解析结果摘要")
    print(f"{'=' * 60}")
    print(f"\n  输出目录: {os.path.abspath(output_dir)}")
    print(f"  文件数量: {len(files)}")
    print(f"\n  文件清单:")

    for fname in files:
        fpath = os.path.join(output_dir, fname)
        size_kb = os.path.getsize(fpath) / 1024

        label = ""
        if fname.endswith(".md"):
            label = "← Markdown 输出"
        elif "content_list" in fname:
            label = "← 内容列表 (content_list.json)"
        elif "layout" in fname or "middle" in fname:
            label = "← 布局中间结果 (layout.json)"
        elif "model" in fname:
            label = "← 模型原始输出 (model.json)"
        elif fname.endswith(".zip"):
            label = "← 结果压缩包"

        print(f"    {fname:40s} {size_kb:8.1f} KB  {label}")

    # 检查关键文件
    md_files = [f for f in files if f.endswith(".md")]
    json_files = [f for f in files if f.endswith(".json")]

    print(f"\n  统计:")
    print(f"    Markdown 文件: {len(md_files)}")
    print(f"    JSON 文件:     {len(json_files)}")

    # 打印 content_list 中的内容类型统计
    content_list_files = [f for f in files if "content_list" in f]
    if content_list_files:
        cl_path = os.path.join(output_dir, content_list_files[0])
        try:
            with open(cl_path, "r", encoding="utf-8") as f:
                content_list = json.load(f)
            type_counts = {}
            for item in content_list:
                t = item.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1

            print(f"\n  Content List 元素统计:")
            for t, count in sorted(type_counts.items()):
                icons = {
                    "text": "[T]",
                    "table": "[B]",
                    "equation": "[E]",
                    "image": "[I]",
                }
                icon = icons.get(t, "[?]")
                print(f"    {icon} {t:15s} {count:4d} 个")
        except (json.JSONDecodeError, IOError) as e:
            print(f"\n  [警告] 无法解析 content_list: {e}")

    print(f"\n{'=' * 60}")


# ============================================================
# 主流程
# ============================================================

def main():
    start_time = datetime.now()
    print("=" * 60)
    print("  MinerU 云端 API — MVP 测试 Pipeline")
    print(f"  启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 加载配置
    config = load_config()
    print(f"\n[配置] API 地址: {config['api_base_url']}")
    print(f"[配置] 语言: {config['language']}, OCR: {config['is_ocr']}, "
          f"公式: {config['enable_formula']}, 表格: {config['enable_table']}")

    # 2. 确定文件 URL
    file_url = resolve_file_url(config)

    # 3. 提交任务
    client = MinerUClient(config)
    parse_config = {
        "language": config["language"],
        "is_ocr": config["is_ocr"],
        "enable_formula": config["enable_formula"],
        "enable_table": config["enable_table"],
        "model_version": config["model_version"],
    }
    task_id = client.submit(file_url, parse_config)

    # 4. 轮询等待
    result_data = client.poll(task_id)
    zip_url = result_data.get("full_zip_url", "")
    if not zip_url:
        print("[错误] 响应中未包含 full_zip_url")
        sys.exit(1)

    # 5. 下载并解压
    output_dir = os.path.join(os.path.dirname(__file__),
                              config["output_dir"],
                              task_id[:8])
    download_and_extract(zip_url, output_dir)

    # 6. 结果摘要
    print_results_summary(output_dir)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n[完成] 总耗时: {elapsed:.1f}s")
    print(f"[完成] 输出目录: {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    main()
