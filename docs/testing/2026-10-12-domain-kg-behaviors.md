# 词典、图谱与桥接行为专项

质量整改协调者分配的有界本地测试任务。使用 test-driven-development 的红绿缺陷回归与 verification-before-completion 的实际命令核验；原所有权仅两份新测试及本报告，确认三处缺陷红测后由协调者扩大授权至三个生产函数的最小修改。未改此前 CLI 测试/报告或其他任务文件；不提交 Git。

## 行为与边界

- `test_domain_dictionary_behaviors.py`：真实临时 YAML 加载/默认值/类别、缺失/空/错误格式及解析错误，文件替换与新实例重新加载；内存增删改和旧别名清理，长英文缩写索引限制、精确/模糊展开、ASCII/中文相似度、提示条数/长度约束、大小写搜索及单例缓存。
- `test_kg_store_quality_behaviors.py`：实际 NetworkX 的属性/标签查询、类型交集、子串回退、限额/环/孤立节点/多跳邻居、社区缓存；真实 JSON 的legacy包装、版本新增/切换/重载、无文件/坏文件、全局fallback、多文档同名ID与tenant范围；桥接内容类型、真实UTF-8文件、位置回退、标题分段/短尾合并、文档最小长度和源字符偏移。
- 版本存储是真实临时文件；可选 event_bus 与 audit_logger getter 替代，分别覆盖成功通知与故障不阻塞，以防写入现有 output 或启动真实投递。其他词典/图查询/桥接算法未mock。
- 词典 CRUD 目前为内存操作，本模块没有自动持久化 API；本轮持久化证据指 YAML 文件替换、reload及新实例重载，不宣称新增自动落盘功能。
- 禁用 dotenv/HuggingFace联网，未读取.env、调用模型、修改现有output或研究冻结。API端点/真实数据库/供应商及跨项目验收不在该专项范围。

## 红测、根因及最小修复

首轮 `62 passed, 5 failed` 中两项是测试作者把 Unicode sorted 的词序写错；已修正为既有排序契约，不是生产缺陷。随后确认运行 `67 passed, 3 failed`、退出1，精确保留以下三项红测，未skip/xfail或删除断言：

| 红测 | 生产根因 | 获授权修复 |
|---|---|---|
| search_abbreviations_is_case_insensitive | `backend/domain_dict.py::DomainDict.search` 只lower查询，`JSA`候选仍大写，`search('jsa')`为空 | term/synonym/abbreviation/description参与搜索时一致lower，保留原返回数据 |
| prefixed_graph_does_not_create_phantom_nodes_for_missing_edge_endpoint | `backend/kg_store.py::KgVersionManager.load_graph` 原始空ID先加prefix后成为非空`doc:`，NetworkX新增虚构节点 | 原始src/tgt通过非空校验后才拼prefix，保留有效ID和边属性 |
| stripped_document_offsets_still_map_to_original_source_characters | `backend/bridge.py::build_documents` 文本strip后仍使用section原始起点，前导4字符导致grounding偏移 | offset加原始section文本lstrip去掉的字符数，尾空白不移动起点，全空section不建文档 |

三个函数修改后73项通过；新增ASCII四字段/空端点四形态及前导/尾部/Unicode空白断言后最终80项通过。未改评分、实验产物、历史冻结或其他生产契约。协调者负责独立复审、规范回流与全量回归。

## 实际命令

执行目录仓库根，backend/.venv Python3.12。各pytest命令均先设置：

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
```

准确三项红测复现（67 passed、3 failed、1 warning、3.14s、退出1）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_domain_dictionary_behaviors.py backend/tests/test_kg_store_quality_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/domain-kg-confirm-red-20261012
```

最小修改后绿测（73 passed、1 warning、1.23s、退出0）：

```powershell
backend/.venv/Scripts/python.exe -B -X utf8 -m pytest backend/tests/test_domain_dictionary_behaviors.py backend/tests/test_kg_store_quality_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/domain-kg-green-20261012
```

最终固定范围专项覆盖（coverage7.6.12；pytest输出80 passed、1 warning、2.55s）：

```powershell
$env:PYTHONPATH='.tmp/coverage-runtime-py312-20261012'
backend/.venv/Scripts/python.exe -B -X utf8 -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=backend/tests/_sandbox_tmp/domain-kg-final-20261012.coverage -m pytest backend/tests/test_domain_dictionary_behaviors.py backend/tests/test_kg_store_quality_behaviors.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/domain-kg-final-20261012
```

coverage进程最终退出0；之后使用同配置导出JSON，退出0。报告90个生产文件、excluded_lines=0。既有 `Unknown config option: timeout` 警告及导出时agentic_rag_mvp.py无效转义SyntaxWarning未在本任务改配置/生产文件。

```powershell
backend/.venv/Scripts/python.exe -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=backend/tests/_sandbox_tmp/domain-kg-final-20261012.coverage -o backend/tests/_sandbox_tmp/domain-kg-final-coverage-20261012.json
```

| 目标文件 | 覆盖行 / 全部行 | 覆盖分支 / 全部分支 |
|---|---|---|
| backend/domain_dict.py | 213 / 214 | 110 / 112 |
| backend/kg_store.py | 293 / 294 | 127 / 134 |
| backend/bridge.py | 120 / 121 | 50 / 52 |

全固定范围本专项合计行1279/13368、分支295/4504，包含未导入文件；只反映这80项场景，不是全量测试结果，不声称后端双指标达标。独立data_file与JSON位于上述sandbox路径，未覆盖主报告；原始命令输出保留在本次工具执行记录。

## 文件快照

| 文件 | SHA256 |
|---|---|
| backend/domain_dict.py | 07390519368BB5ABBE2280A611EB3EAC34DA03C34D4BB8314528E82B9E484E18 |
| backend/kg_store.py | FFC075D6649F3A9FB3CD8A2E128A1031D241644DB5E2EA08C86729883662EC7A |
| backend/bridge.py | 08A5AC7DCE4DAC38B33D6F83D38BCABE14C47C47EC2BE4B138375A2341314531 |
| backend/tests/test_domain_dictionary_behaviors.py | 874EE3B387A52D607800FB136B92C0C73D13ABE7ACC47A4FFA33304945A34144 |
| backend/tests/test_kg_store_quality_behaviors.py | E5AC7C0CCCFEF500C299B2234E71196E12A88565E927847008B72DA6729348A7 |

共享工作区仍有其他整改，最终全量快照与memory由协调者统一记录；专项不能证明后端或全项目双覆盖门槛通过。没有commit/push。
