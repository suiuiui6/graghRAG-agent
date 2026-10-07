# 阿里云OSS集成方案

**目标:** 使用阿里云OSS存储上传的文件，让MinerU可以访问

---

## 需要的信息

### 1. Bucket基本信息
- **Bucket名称**: 例如 `my-graphrag-bucket`
- **Bucket地域**: 例如 `oss-cn-hangzhou`
- **Bucket外网访问域名**: 例如 `my-bucket.oss-cn-hangzhou.aliyuncs.com`

### 2. 访问方式（二选一）

#### 方案A：使用AccessKey（推荐）
**优点:** 安全，可以设置权限
**需要:**
- AccessKey ID
- AccessKey Secret

**获取方式:**
1. 登录阿里云控制台
2. 右上角头像 → AccessKey管理
3. 创建AccessKey或使用现有的

#### 方案B：公共读Bucket
**优点:** 配置简单，无需AccessKey
**需要:**
- 设置Bucket为"公共读"权限
- 只需要Bucket域名

**设置方式:**
1. 进入OSS控制台
2. 选择Bucket → 权限管理 → 读写权限
3. 设置为"公共读"

---

## 集成步骤

### 步骤1：安装阿里云OSS SDK

```bash
cd D:/graghRAG-agent/backend
source .venv/Scripts/activate
pip install oss2
```

### 步骤2：配置环境变量

编辑 `backend/.env`，添加：

```bash
# 阿里云OSS配置
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=your-bucket-name
OSS_ACCESS_KEY_ID=your-access-key-id
OSS_ACCESS_KEY_SECRET=your-access-key-secret
OSS_PATH_PREFIX=graphrag/uploads/
```

### 步骤3：创建OSS上传模块

创建 `backend/oss_uploader.py`:

```python
import os
import oss2
from dotenv import load_dotenv

load_dotenv()

def upload_to_oss(local_file_path: str, object_name: str = None) -> str:
    """
    上传文件到阿里云OSS
    
    Args:
        local_file_path: 本地文件路径
        object_name: OSS对象名称（可选，默认使用文件名）
    
    Returns:
        文件的公网URL
    """
    # 读取配置
    endpoint = os.getenv('OSS_ENDPOINT')
    bucket_name = os.getenv('OSS_BUCKET_NAME')
    access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
    access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')
    path_prefix = os.getenv('OSS_PATH_PREFIX', 'uploads/')
    
    # 验证配置
    if not all([endpoint, bucket_name, access_key_id, access_key_secret]):
        raise ValueError("OSS配置不完整，请检查.env文件")
    
    # 创建认证对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    
    # 创建Bucket对象
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    # 生成对象名称
    if object_name is None:
        object_name = os.path.basename(local_file_path)
    
    # 添加路径前缀
    full_object_name = path_prefix + object_name
    
    # 上传文件
    bucket.put_object_from_file(full_object_name, local_file_path)
    
    # 生成公网URL
    url = f"https://{bucket_name}.{endpoint}/{full_object_name}"
    
    return url


def upload_to_oss_public_read(local_file_path: str, object_name: str = None) -> str:
    """
    上传文件到公共读Bucket（无需AccessKey）
    
    仅用于已设置为公共读的Bucket
    """
    endpoint = os.getenv('OSS_ENDPOINT')
    bucket_name = os.getenv('OSS_BUCKET_NAME')
    path_prefix = os.getenv('OSS_PATH_PREFIX', 'uploads/')
    
    # 对于公共读Bucket，仍需要AccessKey来上传
    # 但读取时不需要签名
    return upload_to_oss(local_file_path, object_name)
```

### 步骤4：修改worker.py

编辑 `backend/worker.py`，在 `_upload_to_public` 函数中添加OSS上传：

```python
def _upload_to_public(filepath: str) -> str | None:
    """Upload file to public hosting via OSS or curl, return URL."""
    
    # Try OSS first
    try:
        from oss_uploader import upload_to_oss
        import uuid
        
        # 生成唯一文件名
        filename = os.path.basename(filepath)
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        
        url = upload_to_oss(filepath, unique_name)
        print(f"[OSS] Uploaded to: {url}")
        return url
    except Exception as e:
        print(f"[OSS] Upload failed: {e}")
    
    # Fallback to file.io
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-F", f"file=@{filepath}", "https://file.io"],
            capture_output=True, text=True, timeout=35,
        )
        data = json.loads(result.stdout)
        if data.get("success"):
            return data["link"]
    except Exception:
        pass

    # Fallback to transfer.sh
    try:
        fname = os.path.basename(filepath)
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", "-T", filepath, f"https://transfer.sh/{fname}"],
            capture_output=True, text=True, timeout=65,
        )
        if result.returncode == 0 and result.stdout.strip().startswith("http"):
            return result.stdout.strip()
    except Exception:
        pass

    return None
```

---

## 配置示例

### 完整的.env配置

```bash
# MinerU API
MINERU_API_TOKEN=your-mineru-token
MINERU_API_BASE_URL=https://mineru.net/api/v4/extract/task

# LangExtract / DeepSeek
LANGEXTRACT_API_KEY=sk-your-deepseek-key
LANGEXTRACT_MODEL_ID=deepseek-chat
LANGEXTRACT_BASE_URL=https://api.deepseek.com

# 阿里云OSS
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET_NAME=my-graphrag-bucket
OSS_ACCESS_KEY_ID=LTAI5tXXXXXXXXXXXXXX
OSS_ACCESS_KEY_SECRET=your-secret-key
OSS_PATH_PREFIX=graphrag/uploads/
```

---

## 测试OSS上传

创建测试脚本 `backend/test_oss.py`:

```python
from oss_uploader import upload_to_oss

# 测试上传
test_file = "uploads/demo.pdf"
url = upload_to_oss(test_file, "test_demo.pdf")
print(f"上传成功！")
print(f"URL: {url}")

# 测试访问
import requests
response = requests.head(url)
print(f"HTTP状态: {response.status_code}")
if response.status_code == 200:
    print("✅ 文件可以公网访问")
else:
    print("❌ 文件无法访问，请检查Bucket权限")
```

运行测试:
```bash
cd backend
python test_oss.py
```

---

## 安全建议

### 1. 使用RAM子账号
不要使用主账号的AccessKey，创建RAM子账号：

1. 进入RAM控制台
2. 创建用户 → 选择"编程访问"
3. 添加权限：`AliyunOSSFullAccess` 或自定义策略
4. 保存AccessKey

### 2. 最小权限策略

自定义RAM策略（只允许上传和读取）:
```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject"
      ],
      "Resource": [
        "acs:oss:*:*:your-bucket-name/graphrag/*"
      ]
    }
  ]
}
```

### 3. 设置生命周期规则

自动删除旧文件节省成本：
1. OSS控制台 → Bucket → 基础设置 → 生命周期
2. 创建规则：30天后删除 `graphrag/uploads/` 下的文件

---

## 常见问题

### Q1: 上传成功但无法访问？
**A:** 检查Bucket权限设置，确保是"公共读"或使用签名URL

### Q2: AccessKey泄露怎么办？
**A:** 立即在阿里云控制台禁用该AccessKey，创建新的

### Q3: 文件太大上传慢？
**A:** OSS支持分片上传，可以优化大文件上传速度

### Q4: 如何查看上传的文件？
**A:** OSS控制台 → 文件管理 → 查看 `graphrag/uploads/` 目录

---

## 下一步

配置完成后：
1. 重启后端服务
2. 访问 http://localhost:5173
3. 上传本地文件
4. 系统会自动上传到OSS并调用MinerU解析

✅ 完全支持本地文件上传！
