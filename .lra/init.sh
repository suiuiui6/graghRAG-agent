#!/bin/bash
# Long-Running Agent - Environment Initialization Script
# GraphRAG Agent 知识图谱问答系统
# 用途：让每个新 session 的 agent 快速进入可用状态

set -euo pipefail

echo "🚀 Starting GraphRAG Agent LRA Environment..."

# 后端：独立 uv venv（铁律 3）
if [ -d "backend/.venv" ]; then
    echo "  ✓ backend/.venv 已存在"
else
    echo "  ⚠  backend/.venv 不存在，请按 backend/CLAUDE.md 指引创建："
    echo "     cd backend && uv venv .venv --python 3.12"
fi

# 前端：pnpm + .nvmrc（铁律 3）
if [ -d "frontend/node_modules" ]; then
    echo "  ✓ frontend/node_modules 已存在"
else
    echo "  ⚠  frontend 依赖未安装：cd frontend && pnpm install"
fi

# 健康检查：后端是否能导入关键依赖
echo ""
echo "  → 检查后端依赖导入（oss2 / langextract）…"
(cd backend && .venv/Scripts/python.exe -c "import oss2; print('    oss2 ✓', oss2.__version__)" 2>/dev/null) \
  || echo "    ⚠ oss2 未安装（F001 待修：requirements.txt 缺失）"
(cd backend && .venv/Scripts/python.exe -c "import langextract; print('    langextract ✓')" 2>/dev/null) \
  || echo "    ⚠ langextract 未安装（F001 待修）"

echo ""
echo "✅ Environment ready!"
echo ""
echo "下一步：/developer-kit:devkit.lra.start-session 读取进度并选择 feature"
