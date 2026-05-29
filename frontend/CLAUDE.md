# Frontend — CLAUDE.md

## 项目概述

GraphRAG 多模态知识图谱问答系统前端。
React 18 + TypeScript + Vite + Tailwind CSS + Zustand。

## 项目结构

```
frontend/
├── src/
│   ├── pages/           ← 页面组件 (HomePage, GraphPage, QueryPage, DocumentsPage)
│   ├── components/      ← UI 组件
│   ├── lib/             ← API 客户端、常量、工具函数
│   └── main.tsx         ← 入口
├── prototype/
│   └── index.html       ← 产品原型 (5 页面)
├── visualizer.html      ← KG 图谱独立可视化
├── index.html           ← Vite 入口 HTML
├── vite.config.ts       ← Vite 配置
├── tailwind.config.js   ← Tailwind CSS 配置
├── package.json         ← 依赖与脚本
└── .env.example         ← 环境变量模板
```

## 开发与构建

```bash
# 安装依赖
cd D:/graghRAG-agent/frontend
npm install

# 启动开发服务器 (端口 5173)
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 环境变量

复制 `.env.example` 为 `.env` 并根据需要修改：

```
VITE_API_BASE_URL=http://localhost:8000
```

## 静态原型预览

```bash
cd D:/graghRAG-agent/frontend
python -m http.server 8766
# 原型: http://localhost:8766/prototype/index.html
# 图谱: http://localhost:8766/visualizer.html
```
