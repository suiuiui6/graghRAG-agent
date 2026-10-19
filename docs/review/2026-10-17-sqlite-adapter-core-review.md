# SQLite R8 适配器 core 独立审查



输入 `docs/testing/sqlite-vector-r8-20261017/manifest.json` SHA256 `ff9d60f7e90477debc95f93781aaf8e239452069ccd328c75e704d78c321506a`，37项逐hash一致，backend/tests复制到私有adapter目录。

审查总结：新增 **Medium 1**，Critical 0、High 0、Low 0。消费者R2两项仍关闭；适配器restore专项存在以下实际反例。

### 🟡 Medium：restore只检查表名，不验证schema

冻结 `backend/vector_store.py:348–354`。一个完整性检查通过且三表名正确的SQLite文件，`payload`定义为`CREATE TABLE payload(arbitrary TEXT)`，其余collections/records存在正常字段；提供该文件真实SHA256和size后，restore成功创建目标并返回VectorStore。后续payload写入/读取无法按正常schema工作。hash验证证明文件来源和字节完整性，不能代替应用schema与数据有效性验证。

独立失败：`test_restore_rejects_wrong_payload_schema`，实际 **DID NOT RAISE VectorInputError，1 failed in 0.53s，pytest exit1**，日志 `schema-review.log`。这是恢复成功却生成不兼容存储的具体反例，不宣称已证明可执行攻击。

建议在创建target之前验证列名/类型/主键、必要唯一与外键约束及无额外trigger/view；对记录的dimension/payload段完整性提供明确检查，并用错误schema有效hash的反例做回归。

Before:

```python
if table_names != {'collections', 'records', 'payload'}:
    fail(op='open')
```

After（结构建议，尚未实现）：

```python
validate_schema_and_constraints(c)  # Exact application schema, reject extra objects.
validate_snapshot_records(c)        # Dimensions and complete payload segments.
# Create target only after validation succeeds.
```

### 已执行独立证据及边界

原adapter16例 + 新增4例 **20 passed, 3 subtests passed in 10.22s，pytest exit0**。新增：非法scalar的float/array钩子未触发；注入目标事务payload写入OperationalError后records/payload/dimension全部回滚；错误hash在调用SQLite解析之前拒绝且target未建；备份恢复真实Unicode往返及`../escape`集合名不造成路径穿越。

首次运行默认pytest临时目录不可创建，16通过4个setup error（exit1），保留 `adapter-temp-error.log`；使用私有`--basetemp`重新执行上述全套通过。随后新增schema反例单独失败；不能把此前20通过称最终全套通过。实际命令均用同一integration-env Python、`-B -X utf8 -m pytest`、`-q -p no:cacheprovider --basetemp=<私有目录>`。

静态检查：参数化集合/ID输入、connect防御配置、完整batch私有SQLite暂存先验后目标事务、页面generator closing释放、snapshot校验复制均存在；search在同一只读事务评分及读取命中payload，vector窗口转换，text/JSON增量编码。read_payload仍物化逻辑单行，metadata扫描/最终输出计入内存，不承诺严格RSS。以上静态观察不替代真实故障/大规模与provider验收。

优先级：先补restore schema反例并复验；再由root重新冻结和组合验证。没有执行全backend、覆盖率或漏洞扫描，不能据本审查提交/生产切换。


## R2 修订独立闭环（最终结论）

新冻结 `docs/testing/sqlite-vector-r8-r2-20261017/manifest.json` SHA256 `9d4e97242ea1e536669502ab28d16a9b5beaa0dff6ce410d1726666293761cc7`，42项运行前后逐文件核验一致；复制至全新 `.tmp/sqlite-r8-r2-review-20261017/adapter-r2/`，未覆盖旧失败版本。

**最终审查总结：上述Medium已关闭，当前专项新增开放问题0（Critical 0、High 0、Medium 0、Low 0）。** 原18例 + 上述5例独立边界 + 新增6例 = **29 passed, 3 subtests passed in 11.19s，pytest exit0**。新增restore/reopen × trigger/view四例、缺records UNIQUE约束restore/reopen两例全部拒绝，并核拒绝时主数据库字节未更改和未创建restore目标。

R2源码 `backend/vector_store.py:274–295,366–367` 使用精确应用schema对象/SQL白名单，同时检查外键；已有数据库构造在journal PRAGMA和写入前验证，restore在可信hash及integrity验证后、创建target前验证。旧wrong payload schema反例真实转绿，正常backup/restore与多集合原测试不退化。

首次新增restore异常schema夹具的更改留在WAL，而测试仅复制主库字节，导致三例输入事实上仍为合法旧schema（26通过3失败，exit1）。核因后仅修私有夹具：关闭连接并checkpoint，把异常schema真正写入输入文件，再完整重跑得到上述29通过。保留 `r2-fixture-wal-error.log`，不将此夹具问题归于候选实现。

最终命令、时间、准确pytest退出码、冻结manifest及新增测试/日志SHA256见 `.tmp/sqlite-r8-r2-review-20261017/adapter-r2-receipt.json`。使用新integration-env Python，完整命令 `-B -X utf8 -m pytest .tmp/sqlite-r8-r2-review-20261017/adapter-r2/tests -q -p no:cacheprovider --basetemp=.tmp/sqlite-r8-r2-review-20261017/r2-final-pytest-temp`。

本闭环证明已复现schema缺口及新增schema对象/约束边界修复；没有验证任意恶意数据库或全部payload语义有效性，不扩大为全域安全证明。优先级：root最终组合和规范/记忆汇总；全量backend、双90覆盖及漏洞扫描仍未执行，无提交/推送/部署准入结论。
