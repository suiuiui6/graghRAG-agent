"""阿里云OSS文件上传模块"""

import os
import uuid
import oss2
from dotenv import load_dotenv

# 加载环境变量（强制覆盖系统环境变量）
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path, override=True)


def upload_to_oss(local_file_path: str, object_name: str = None) -> str:
    """
    上传文件到阿里云OSS

    Args:
        local_file_path: 本地文件路径
        object_name: OSS对象名称（可选，默认使用随机文件名）

    Returns:
        文件的公网URL
    """
    # 读取配置
    endpoint = os.getenv('OSS_ENDPOINT', '').strip()
    bucket_name = os.getenv('OSS_BUCKET_NAME', '').strip()
    access_key_id = os.getenv('OSS_ACCESS_KEY_ID', '').strip()
    access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET', '').strip()
    path_prefix = os.getenv('OSS_PATH_PREFIX', 'graphrag/uploads/')

    # 验证配置
    if not all([endpoint, bucket_name, access_key_id, access_key_secret]):
        raise ValueError(f"OSS配置不完整: endpoint={bool(endpoint)}, bucket={bool(bucket_name)}, "
                        f"key_id={bool(access_key_id)}, secret={bool(access_key_secret)}")

    # 创建认证对象
    auth = oss2.Auth(access_key_id, access_key_secret)

    # 创建Bucket对象
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 生成对象名称（使用随机前缀避免冲突）
    if object_name is None:
        filename = os.path.basename(local_file_path)
        unique_prefix = uuid.uuid4().hex[:8]
        object_name = f"{unique_prefix}_{filename}"

    # 添加路径前缀
    full_object_name = path_prefix + object_name

    # 上传文件
    print(f"[OSS] 上传文件: {local_file_path} -> {full_object_name}")
    bucket.put_object_from_file(full_object_name, local_file_path)

    # 生成公网URL
    url = f"https://{bucket_name}.{endpoint}/{full_object_name}"
    print(f"[OSS] 上传成功: {url}")

    return url


def test_oss_connection():
    """测试OSS连接"""
    try:
        endpoint = os.getenv('OSS_ENDPOINT', '').strip()
        bucket_name = os.getenv('OSS_BUCKET_NAME', '').strip()
        access_key_id = os.getenv('OSS_ACCESS_KEY_ID', '').strip()
        access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET', '').strip()

        if not all([endpoint, bucket_name, access_key_id, access_key_secret]):
            return False, "OSS配置不完整"

        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)

        # 测试连接（列举bucket信息）
        bucket.get_bucket_info()
        return True, "OSS连接成功"
    except Exception as e:
        return False, f"OSS连接失败: {str(e)}"
