# 本地文件上传完整解决方案

**目标:** 支持本地文件直接上传，无需公网URL

---

## 方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| ngrok隧道 | 简单、快速、免费 | 需要网络 | ⭐⭐⭐⭐⭐ |
| 本地MinerU | 完全离线 | 安装复杂 | ⭐⭐⭐ |
| 云存储 | 稳定、持久 | 需要账号 | ⭐⭐⭐⭐ |

---

## 方案A：ngrok隧道（推荐）

### 1. 安装ngrok

**Windows:**
```bash
# 方法1: 使用Chocolatey
choco install ngrok

# 方法2: 手动下载
# 访问 https://ngrok.com/download
# 下载Windows版本，解压到任意目录
```

**验证安装:**
```bash
ngrok version
```

### 2. 启动ngrok隧道

```bash
# 在新的终端窗口运行
ngrok http 8000
```

**输出示例:**
```
Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

### 3. 配置后端

复制ngrok提供的URL（如 `https://abc123.ngrok-free.app`），编辑 `backend/.env`:

```bash
# 添加或修改这一行
FILE_URL=https://abc123.ngrok-free.app/api/v1/files/
```

### 4. 重启后端

```bash
cd D:/graghRAG-agent/backend
# 停止当前后端
taskkill /F /IM python.exe

# 重新启动
source .venv/Scripts/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 上传本地文件

现在可以直接上传本地文件了！
1. 访问 http://localhost:5173
2. 拖拽本地文件到上传区域
3. 点击"开始解析文档"
4. 系统会自动通过ngrok隧道让MinerU访问文件

---

## 方案B：本地MinerU CLI

### 1. 安装MinerU

```bash
# 创建新的虚拟环境
cd D:/graghRAG-agent
python -m venv mineru-env
source mineru-env/Scripts/activate

# 安装MinerU
pip install magic-pdf[full]
```

### 2. 配置MinerU

创建配置文件 `~/.magic-pdf.json`:
```json
{
  "models-dir": "D:/models/magic-pdf",
  "device-mode": "cpu"
}
```

### 3. 手动解析文件

```bash
# 解析单个文件
magic-pdf -p "your-file.pdf" -o "D:/graghRAG-agent/backend/output/mineru/manual_001"
```

### 4. 修改worker.py支持本地输出

编辑 `backend/worker.py`，在本地文件处理部分添加：

```python
# 检查是否有手动解析的输出
manual_dirs = [d for d in os.listdir(output_mineru) if d.startswith('manual_')]
if manual_dirs:
    # 使用最新的手动输出
    mineru_dir = os.path.join(output_mineru, sorted(manual_dirs)[-1])
```

---

## 方案C：简化版 - 使用localtunnel

### 1. 安装localtunnel

```bash
npm install -g localtunnel
```

### 2. 启动隧道

```bash
lt --port 8000
```

### 3. 配置FILE_URL

```bash
# 使用localtunnel提供的URL
FILE_URL=https://your-subdomain.loca.lt/api/v1/files/
```

---

## 快速启动脚本

创建 `start-with-tunnel.sh`:

```bash
#!/bin/bash

echo "=== 启动GraphRAG系统（支持本地文件上传） ==="

# 1. 启动ngrok隧道
echo "1. 启动ngrok隧道..."
ngrok http 8000 > /dev/null 2>&1 &
NGROK_PID=$!
sleep 3

# 2. 获取ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*ngrok-free.app')
echo "   ngrok URL: $NGROK_URL"

# 3. 更新.env
echo "2. 更新配置..."
cd backend
sed -i "s|FILE_URL=.*|FILE_URL=${NGROK_URL}/api/v1/files/|" .env

# 4. 启动后端
echo "3. 启动后端..."
source .venv/Scripts/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 5. 启动前端
echo "4. 启动前端..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 系统启动完成！"
echo "   前端: http://localhost:5173"
echo "   后端: http://localhost:8000"
echo "   ngrok: $NGROK_URL"
echo ""
echo "现在可以上传本地文件了！"
```

---

## 常见问题

### Q1: ngrok提示需要注册？
**A:** 访问 https://ngrok.com/signup 免费注册，然后运行：
```bash
ngrok config add-authtoken YOUR_TOKEN
```

### Q2: ngrok隧道经常断开？
**A:** 免费版ngrok会话有时间限制，可以：
- 升级到付费版
- 使用localtunnel替代
- 使用云存储方案

### Q3: 文件太大上传失败？
**A:** 
- 检查后端配置的最大文件大小（默认200MB）
- 使用云存储方案
- 分批上传多个小文件

### Q4: 不想使用隧道服务？
**A:** 使用方案B（本地MinerU CLI），完全离线处理

---

## 推荐配置

**开发测试环境:**
- 使用ngrok隧道
- 快速、简单、免费

**生产环境:**
- 使用云存储（阿里云OSS/腾讯云COS）
- 稳定、可靠、持久

**离线环境:**
- 使用本地MinerU CLI
- 完全离线、无需网络

---

## 总结

**最简单的方案:**
1. 安装ngrok: `choco install ngrok`
2. 启动隧道: `ngrok http 8000`
3. 配置FILE_URL到.env
4. 重启后端
5. 上传本地文件 ✅

**URL上传的限制:**
- URL只能访问公网上的文件
- 不能直接上传本地文件
- 需要文件已经在某个公网服务器上

**使用ngrok后:**
- ✅ 可以上传本地文件
- ✅ MinerU通过隧道访问你的本地服务器
- ✅ 无需手动上传到云存储
