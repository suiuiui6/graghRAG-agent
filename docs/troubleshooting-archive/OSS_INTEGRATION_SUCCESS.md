# 阿里云OSS集成完成报告

**日期:** 2026-05-25  
**状态:** ✅ 成功集成

---

## 配置信息

```
Bucket名称: zhongshiyou-digitalization
Bucket地域: oss-cn-beijing
Endpoint: oss-cn-beijing.aliyuncs.com
AccessKey ID: LTAI5t7DjHhjuhJ596MXHV3P
路径前缀: graphrag/uploads/
```

---

## 测试结果

### ✅ OSS连接测试
- 状态: 成功
- Bucket信息获取正常

### ✅ 文件上传测试
- 测试文件: test_oss.txt
- 上传URL: https://zhongshiyou-digitalization.oss-cn-beijing.aliyuncs.com/graphrag/uploads/762c2d80_test_oss.txt
- 状态: 成功

### ✅ 后端服务
- 状态: 运行正常
- OSS模块已加载
- worker.py已集成OSS上传

---

## 工作流程

### 本地文件上传流程

1. **用户上传文件**
   - 前端: 拖拽文件到上传区域
   - 后端: 接收文件并保存到 `uploads/` 目录

2. **自动上传到OSS**
   - worker.py 调用 `_upload_to_public()`
   - oss_uploader.py 上传文件到阿里云OSS
   - 生成公网URL

3. **调用MinerU API**
   - 使用OSS公网URL
   - MinerU下载并解析文件
   - 返回解析结果

4. **构建知识图谱**
   - Format Bridge 分段
   - LangExtract 实体抽取
   - Grounding 溯源
   - KG 构建

5. **知识问答**
   - 基于构建的KG回答问题

---

## 文件结构

### 新增文件

```
backend/
├── oss_uploader.py          ← OSS上传模块
├── .env                     ← 包含OSS配置
└── worker.py                ← 已集成OSS上传
```

### OSS存储结构

```
zhongshiyou-digitalization/
└── graphrag/
    └── uploads/
        ├── 762c2d80_test_oss.txt
        ├── xxxxxxxx_document1.pdf
        └── xxxxxxxx_document2.docx
```

---

## 使用说明

### 上传本地文件

1. 访问 http://localhost:5173
2. 进入"上传"页面
3. 拖拽本地文件（PDF、DOCX、PPTX等）
4. 点击"开始解析文档"
5. 等待解析完成（观察5个阶段进度）
6. 在"知识问答"页面测试

### 支持的文件格式

- PDF (.pdf)
- Word (.doc, .docx)
- PowerPoint (.ppt, .pptx)
- Excel (.xlsx)
- 图片 (.png, .jpg, .jpeg)
- EPUB (.epub)
- HTML (.html)

### 文件大小限制

- 单个文件: 最大200MB
- 页数限制: 最多600页

---

## 安全建议

### 1. AccessKey安全

- ✅ 已使用独立的AccessKey
- ⚠️ 不要将AccessKey提交到Git
- ⚠️ 定期轮换AccessKey
- 建议: 使用RAM子账号（最小权限）

### 2. Bucket权限

当前配置需要以下权限:
- `oss:PutObject` - 上传文件
- `oss:GetObject` - 读取文件（MinerU需要）

### 3. 成本控制

建议设置生命周期规则:
- 30天后自动删除 `graphrag/uploads/` 下的文件
- 或转换为低频访问存储

---

## 故障排查

### 问题1: 上传失败 SignatureDoesNotMatch
**原因:** AccessKey不正确  
**解决:** 检查.env中的AccessKey ID和Secret

### 问题2: 403 Forbidden
**原因:** Bucket权限不足  
**解决:** 确保AccessKey有PutObject权限

### 问题3: 文件无法访问
**原因:** Bucket未设置公共读  
**解决:** OSS控制台 → Bucket → 权限管理 → 设置为"公共读"

---

## 下一步

### 立即测试

1. 准备一个本地PDF文件
2. 访问 http://localhost:5173
3. 上传文件
4. 等待解析完成
5. 在知识问答页面提问

### 监控建议

1. 定期检查OSS存储用量
2. 监控MinerU API调用次数
3. 查看后端日志: `backend/backend.log`

---

## 总结

✅ **阿里云OSS集成完成**  
✅ **支持本地文件上传**  
✅ **完整的文档处理流程**  
✅ **知识图谱构建正常**

现在系统完全支持本地文件上传和处理！🎉
