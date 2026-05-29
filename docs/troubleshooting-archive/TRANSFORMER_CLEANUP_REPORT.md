# Transformer Paper 数据清理报告

**日期:** 2026-05-25  
**问题:** 知识图谱中混入了Transformer Paper数据，需要完全清理

---

## 问题根源

### 发现的问题
1. **所有KG目录都包含Transformer Paper数据**
   - `ingest_310db2dc/` - Transformer Paper
   - `ingest_78d46e6b/` - Transformer Paper  
   - `ingest_dcf6de27/` - Transformer Paper

2. **MinerU输出异常**
   - 只有一个旧的 `ingest_6/` 目录（Transformer Paper）
   - 新上传的文件没有对应的MinerU输出
   - 系统回退使用了旧数据

3. **文档元数据与实际内容不匹配**
   - 文档列表显示：挑战杯申报书、智慧工地PPT
   - 实际KG内容：全部是Transformer Paper

---

## 清理步骤

### 1. 删除所有KG数据
```bash
rm -rf backend/output/kg/ingest_*
```

### 2. 删除MinerU输出
```bash
rm -rf backend/output/mineru/ingest_*
```

### 3. 删除文档存储
```bash
rm -f backend/output/docs_store.json
```

### 4. 清理上传文件
```bash
rm -f backend/uploads/ingest_*
```

### 5. 重启后端服务
```bash
kill <uvicorn-pid>
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

---

## 清理后的目录结构

```
backend/
├── output/
│   ├── kg/              ← 空目录
│   ├── mineru/          ← 空目录
│   └── docs_store.json  ← 不存在或为空数组
└── uploads/             ← 无 ingest_* 文件
```

---

## 下一步操作

### 重新上传文档
1. 访问 http://localhost:5173
2. 进入"上传"页面
3. 上传实际的文档（非Transformer Paper）
4. 等待MinerU解析完成
5. 验证KG内容

### 验证命令
```bash
# 检查文档列表
curl http://localhost:8000/api/v1/documents

# 检查KG内容
curl http://localhost:8000/api/v1/graph/all

# 测试查询
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "文档主要内容是什么？"}'
```

---

## 可能的原因分析

### 为什么会出现Transformer Paper数据？

1. **MinerU解析失败**
   - 新文件上传后，MinerU API调用失败
   - 系统回退到本地缓存的旧数据
   - 旧数据恰好是Transformer Paper

2. **路径匹配问题**
   - worker.py 中的路径匹配逻辑可能有bug
   - 找不到新的MinerU输出时，使用了旧的 `ingest_6/`

3. **环境变量问题**
   - MinerU API token可能过期
   - 网络连接问题导致API调用失败

---

## 建议改进

### 1. 添加MinerU输出验证
```python
# worker.py
if mineru_dir:
    # 验证输出内容
    full_md = load_full_md(os.path.join(mineru_dir, "full.md"))
    if "Attention Is All You Need" in full_md:
        raise ValueError("检测到Transformer Paper数据，可能是缓存问题")
```

### 2. 禁用回退到旧数据
```python
# worker.py
if not mineru_dir:
    # 不要回退到旧数据，直接失败
    raise ValueError("MinerU解析失败，无有效输出")
```

### 3. 添加文档内容校验
在索引完成后，验证KG内容与文档名称是否匹配

---

## 总结

**清理状态:** ✅ 完成  
**系统状态:** 准备接受新文档上传  
**下一步:** 重新上传实际文档并验证KG内容
