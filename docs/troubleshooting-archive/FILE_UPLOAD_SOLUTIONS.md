# 文件上传问题解决方案

**问题:** 本地文件上传失败，MinerU API需要公网URL

---

## 问题原因

1. **MinerU API要求公网URL**
   - MinerU云端服务需要能访问文件的公网URL
   - 本地文件无法直接被MinerU访问

2. **公共文件上传服务不可用**
   - file.io 服务失败
   - transfer.sh 服务失败
   - 120MB的大文件上传困难

---

## 解决方案

### 方案1：使用URL上传模式（推荐）

**适用场景:** 文件已经在公网上（如arXiv PDF、公司文档服务器等）

**操作步骤:**
1. 访问 http://localhost:5173
2. 进入"上传"页面
3. 找到"⚡ 快速模式：粘贴公网 PDF 链接"
4. 输入公网URL，例如：
   ```
   https://arxiv.org/pdf/1706.03762.pdf
   ```
5. 点击"🚀 解析此链接"

**示例URL:**
- arXiv论文: `https://arxiv.org/pdf/1706.03762.pdf`
- GitHub文档: `https://raw.githubusercontent.com/user/repo/main/doc.pdf`
- 公司服务器: `https://your-company.com/docs/file.pdf`

---

### 方案2：使用云存储服务

**适用场景:** 需要上传本地文件

**步骤:**

#### 2.1 上传到阿里云OSS
1. 登录阿里云OSS控制台
2. 上传文件到bucket
3. 获取公网URL
4. 在前端使用URL模式上传

#### 2.2 上传到腾讯云COS
1. 登录腾讯云COS控制台
2. 上传文件
3. 设置公共读权限
4. 获取访问URL

#### 2.3 使用临时文件分享服务
- **WeTransfer**: https://wetransfer.com/
- **百度网盘**: 生成分享链接（需要直链）
- **蓝奏云**: https://www.lanzou.com/

---

### 方案3：使用ngrok创建公网隧道（开发测试）

**适用场景:** 本地开发测试

**步骤:**

1. **安装ngrok**
   ```bash
   # 下载: https://ngrok.com/download
   # 或使用包管理器
   choco install ngrok  # Windows
   ```

2. **启动ngrok隧道**
   ```bash
   ngrok http 8000
   ```

3. **获取公网URL**
   ```
   Forwarding: https://xxxx-xx-xx-xx-xx.ngrok-free.app -> http://localhost:8000
   ```

4. **配置FILE_URL**
   编辑 `backend/.env`:
   ```
   FILE_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app/api/v1/files/
   ```

5. **重启后端**
   ```bash
   cd backend
   uvicorn server:app --reload
   ```

6. **上传文件**
   - 系统会自动使用ngrok URL
   - MinerU可以访问文件

---

### 方案4：本地MinerU CLI（高级）

**适用场景:** 需要完全离线处理

**步骤:**

1. **安装MinerU CLI**
   ```bash
   pip install magic-pdf
   ```

2. **手动解析文件**
   ```bash
   magic-pdf -p your-file.pdf -o output/mineru/manual_001
   ```

3. **放置输出**
   - 将解析结果放到 `backend/output/mineru/` 目录
   - 确保包含 `full.md` 和 `*_content_list.json`

4. **上传文件**
   - 系统会自动检测并使用本地MinerU输出

---

## 推荐方案对比

| 方案 | 难度 | 速度 | 适用场景 |
|------|------|------|---------|
| URL上传 | ⭐ | ⚡⚡⚡ | 文件已在公网 |
| 云存储 | ⭐⭐ | ⚡⚡ | 本地文件，长期使用 |
| ngrok | ⭐⭐⭐ | ⚡⚡ | 开发测试 |
| 本地CLI | ⭐⭐⭐⭐ | ⚡ | 完全离线 |

---

## 立即可用的测试URL

使用这些公开的PDF测试系统：

```
# Transformer论文（原始）
https://arxiv.org/pdf/1706.03762.pdf

# BERT论文
https://arxiv.org/pdf/1810.04805.pdf

# GPT-3论文
https://arxiv.org/pdf/2005.14165.pdf
```

---

## 下一步操作

**最简单的方式:**
1. 访问 http://localhost:5173
2. 进入"上传"页面
3. 在"快速模式"输入框粘贴：
   ```
   https://arxiv.org/pdf/1810.04805.pdf
   ```
4. 点击"🚀 解析此链接"
5. 等待解析完成
6. 在"知识问答"测试

这样可以立即验证系统功能！
