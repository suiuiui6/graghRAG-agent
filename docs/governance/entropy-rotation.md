# Entropy 月度巡检机制（Layer 6g）

> 来自 Martin Fowler "Humans on the Loop" 与 OpenHarness feedback 子系统，防止规范文档与代码实现漂移。

## 责任人

**chatbot-reviewer**（建议 `run_in_background: true`）

## 巡检周期

每月最后一个工作日，下次巡检：**2026-06-26**

## 巡检范围（4 个优先区域）

### 1. 规范文档与代码一致性

**检查项**：
- `integration/backend-api-architecture-v1.0.md` 中的端点定义与 `backend/app/api/` 实际路由是否一致
- `integration/frontend-system-design-v1.0.md` 中的组件结构与 `frontend/src/` 实际文件是否一致
- `langextract/docs/bridge-pipeline-specification-v1.0.md` 中的 6 阶段与 `langextract/pipeline.py` 实际流程是否一致

**命令模板**：
```bash
# 检查后端端点
grep -r "@app\\.\\(get\\|post\\|put\\|delete\\)" backend/app/api/ | awk -F: '{print $2}' | sort > /tmp/actual_endpoints.txt
grep "^### " integration/backend-api-architecture-v1.0.md | grep -E "(GET|POST|PUT|DELETE)" | sort > /tmp/spec_endpoints.txt
diff /tmp/spec_endpoints.txt /tmp/actual_endpoints.txt

# 检查前端组件
find frontend/src/components -name "*.tsx" -o -name "*.ts" | sort > /tmp/actual_components.txt
grep "^- \`" integration/frontend-system-design-v1.0.md | sed 's/^- `//;s/`.*$//' | sort > /tmp/spec_components.txt
diff /tmp/spec_components.txt /tmp/actual_components.txt
```

**阈值**：差异 > 3 项 → 触发修复

---

### 2. 环境变量同步

**检查项**：
- `backend/.env.example` 与 `backend/app/config.py` 中的 `Settings` 类字段是否一致
- `langextract/.env.example` 与 `langextract/docs/bridge-pipeline-specification-v1.0.md` 环境变量表是否一致

**命令模板**：
```bash
# 检查 backend
grep "^[A-Z_]*=" backend/.env.example | cut -d= -f1 | sort > /tmp/backend_env_example.txt
grep "^    [a-z_]*:" backend/app/config.py | sed 's/^    //;s/:.*$//' | tr '[:lower:]' '[:upper:]' | sort > /tmp/backend_config_fields.txt
diff /tmp/backend_env_example.txt /tmp/backend_config_fields.txt

# 检查 langextract
grep "^[A-Z_]*=" langextract/.env.example | cut -d= -f1 | sort > /tmp/langextract_env_example.txt
grep "| \`[A-Z_]*\`" langextract/docs/bridge-pipeline-specification-v1.0.md | sed 's/.*| `//;s/`.*//' | sort > /tmp/langextract_spec_env.txt
diff /tmp/langextract_env_example.txt /tmp/langextract_spec_env.txt
```

**阈值**：差异 > 1 项 → 触发修复

---

### 3. 测试覆盖率漂移

**检查项**：
- `backend/tests/` 中是否每个 API 端点都有对应的集成测试
- 新增端点是否遗漏测试

**命令模板**：
```bash
# 列出所有端点
grep -r "@app\\.\\(get\\|post\\)" backend/app/api/ | grep -oE '"/[^"]*"' | sort -u > /tmp/all_endpoints.txt

# 列出已测试端点
grep -r "def test_" backend/tests/ | grep -oE '"/[^"]*"' | sort -u > /tmp/tested_endpoints.txt

# 找出未测试端点
comm -23 /tmp/all_endpoints.txt /tmp/tested_endpoints.txt
```

**阈值**：未测试端点 > 0 → 触发修复

---

### 4. 归档文件回流检查

**检查项**：
- `docs/troubleshooting-archive/` 中的文件是否都已回流到对应规范文档
- 是否有新的散落修复报告未归档

**命令模板**：
```bash
# 检查根目录是否有新的散落报告
find . -maxdepth 1 -type f \( -name "*REPORT*.md" -o -name "*TROUBLESHOOTING*.md" -o -name "*FIX*.md" -o -name "*SOLUTION*.md" \) 2>/dev/null

# 检查归档索引是否完整
ls docs/troubleshooting-archive/*.md | wc -l
grep "^- \[" docs/troubleshooting-archive/README.md | wc -l
```

**阈值**：根目录有散落报告 OR 归档索引不完整 → 触发修复

---

## 修复循环

1. **发现漂移** → chatbot-reviewer 生成巡检报告（`docs/governance/entropy-inspection-YYYY-MM-DD.md`）
2. **判断严重性**：
   - 轻微（差异 ≤ 阈值）→ 记录到报告，下月复查
   - 中等（差异 > 阈值但 < 2×阈值）→ 创建 GitHub Issue，标记 `entropy-debt`
   - 严重（差异 ≥ 2×阈值）→ 立即修复，调用 chatbot-coder
3. **修复后验证** → 重新运行巡检命令，确认差异清零
4. **更新巡检报告** → 记录修复内容与 commit hash

## 升级触发条件

当出现以下情况时，升级为"重新进入对应 Layer"：

| 漂移类型 | 升级条件 | 重新进入 Layer |
|---------|---------|---------------|
| 规范文档与代码不一致 | 差异 ≥ 10 项 OR 核心架构变更 | Layer 2（集成拓扑）或 Layer 4（蓝图） |
| 环境变量不同步 | 新增 ≥ 5 个必需变量 | Layer 1（组件规范） |
| 测试覆盖率 < 50% | 未测试端点 ≥ 5 个 | Layer 5（测试策略） |
| 归档文件回流缺失 | 散落报告 ≥ 5 份 | Layer 0（能力边界摸底） |

## 巡检报告模板

```markdown
# Entropy 巡检报告 — YYYY-MM-DD

## 执行人
chatbot-reviewer (run_in_background: true)

## 巡检结果

### 1. 规范文档与代码一致性
- 状态：✅ 达标 / ⚠️ 轻微漂移 / ❌ 严重漂移
- 差异数：X 项
- 详情：[列出具体差异]

### 2. 环境变量同步
- 状态：✅ 达标 / ⚠️ 轻微漂移 / ❌ 严重漂移
- 差异数：X 项
- 详情：[列出具体差异]

### 3. 测试覆盖率漂移
- 状态：✅ 达标 / ⚠️ 轻微漂移 / ❌ 严重漂移
- 未测试端点：X 个
- 详情：[列出具体端点]

### 4. 归档文件回流检查
- 状态：✅ 达标 / ⚠️ 轻微漂移 / ❌ 严重漂移
- 散落报告：X 份
- 详情：[列出具体文件]

## 修复行动
- [ ] Issue #XXX：修复规范文档漂移
- [ ] Issue #XXX：补齐测试覆盖
- [ ] 立即修复：[描述]

## 下次巡检
YYYY-MM-DD（下月最后一个工作日）
```

## 自动化建议（未来）

当前为手动触发，未来可考虑：
- GitHub Actions 定时任务（每月 28 号触发）
- Pre-commit hook 拦截规范文档与代码不一致的提交
- CI 流水线集成 entropy 检查，PR 合并前强制通过

## 参考资料

- Martin Fowler "Humans on the Loop"：https://martinfowler.com/articles/humans-on-loop.html
- OpenHarness feedback 子系统：https://github.com/walkinglabs/awesome-harness-engineering
- 五子系统自检：`docs/governance/five-subsystem-audit-2026-05-28.md`
