# 共同三臂：独立统计与聚合实现复核

最终结论：**接受本轮限定的描述性开发结论，专项阻断已关闭**。全部54答案实算、原判锁、两组仅定位派生修复、297条extra见证及关键失效病例复核通过。以下保留中间整改记录；最终验收绑定文末hash。本报告不冒充对所有事实重新语义评分或人工Gold认证，M2保持开放。

## 输入身份与锁

核查范围包括正式三臂契约、content/evidence操作口径、`common_evaluation_packets.py`、`common_evaluate_summary.py`、`common_scope_audit.py`及分析实现变更记录。未联网、读取真实key或联系内容/输入审计人员；未修改root实现及真实裁决。

两原内容裁决hash分别为`cc9fef6e0c73561eebbdca6772b0ef5ddeba63ff7690c5754471e92987de475e`、`cc5fc601798dca38c0fe16aec6c1a146269d1b629d7f217606b5c964ea2c9e82`；锁与实际文件匹配。仲裁后内容hash `f90162f34b0bc8cc0134253a759a4a7e59dd0dd1b546c94ff39b74e4f66189a4`与仲裁收据匹配。结构计数54答案、324 item rows、729 atoms，correct=true490、atom unknown0；106 extras含3 false/90 unknown；19完成性承诺。上述为已锁语义裁决的结构/计数复核，不是本专家重新语义评分。

`scope-audit.json`有18行（六题×三臂）、每轮145个Gold绑定区域，A/S的target-region access recall均1；P0访问P/R为null。不能把18行当54个独立范围观察；所有重复采用同一冻结选择/分块。S全文访问precision不是选择正确性，P0无完整span mapping，A读取NIST整个第3节允许含3.1，不能拿Gold最小目标区间误判越界。hardcoded A CORRECT是既有AI规则检查标签，本专家没有以计数验证为它增加人工或独立语义背书。

## 已发现并闭合的实现问题

初审版本`b5e4d2d08acb997349b12468579cf492c6bfbeba114a4906f32c49979cb4fdc2`存在三个可复现问题：

1. input_support_rate同时要求in_scope，混合了输入支持与范围两个维度。
2. extras只检查index集合，允许重复索引后写覆盖前判。
3. pending/未知完整性状态或遗漏原内容承诺可以错误strict通过。

根代理修复聚合实现，原内容文件保持锁定：input支持、in-scope支持、unknown支持率分开；extras索引数量/整数类型/唯一性/连续覆盖检查；完成性审计需显式完成且逐原承诺索引与text全覆盖，strict只允许已判SUPPORTED_COMPLETENESS。没有完成性承诺时仍可按其他必要条件strict成功，符合主契约；citation_entails=false不单独否定input_supported=true的strict。

独立合成测试使用8套54单元数据、13条关键断言。实际命令：`.tmp/backend-quality-venv-20261012/Scripts/python.exe -B .tmp/common-three-arm-final-20261015/independent-quality/boundary-audit-r3.py.txt`，exit0，绑定最终受测summary SHA256 `680e3f68e582cb5fcb24c46add01afe2a4f8aede05ae7ccfac82786d7d4f8421`。旧失败证据`boundary-audit.json`、中间修复`boundary-audit-r2.json`及最终`boundary-audit-r3.json`均保留；没有覆盖真实裁决或真实summary。

最终边界结果：缺失/重复extras索引拒绝；unknown支持strict=false且unknown率1；空claims各支持率null且strict=false；输入支持但越界时input率1/in-scope率0；pending承诺strict=false；遗漏blind承诺拒绝；已支持但引用不蕴含时input率1、citation率0，并可在其他条件齐全时strict=true。

## 统计与分母边界

required_content_complete只检查所有Gold身份/atoms/必要限定；content_complete再要求额外事实正确且在范围内。盲评extra=null不能在独立sourceaudit前默认为错或对，必须通过独立extra_index更新派生结果并保留原锁；原盲评理由与源审计定位分别保存。

54登记分母保持，失败/NOT_RUN strict=false而内容分项null；每题每臂三次重复逐项报告，不增加独立文档数。六题共享两来源，729 atom判断包含重复及条件属性，不能当729独立样本；不运行显著性、功效或泛化检验。item precision按当前内容操作口径的正确Gold身份数/去重预测对象数计算，无法可靠切分或空答案时为null，不将属性claim数当item数。

下一步：取得最终锁定evidence-final、真实quality-summary及报告后，独立重算全部54答案的字段、分母及严格判据并输出最终专家合同。

## 实际源审计分母分类补充

两输入审计采用不同拆分粒度：第一组27答案247条ordinary domain claims，部分来源覆盖断言放在indexed extras；第二组初稿625包含564 domain及61 source_metadata。根代理在首次真实聚合前将第二组metadata保留到独立数组，不删除原判，ordinary支持率仅使用domain claims；strict仍检查domain与metadata所有真实性/范围/输入支持，第一组metadata在indexed extras受独立正确性/范围审查。

独立合成回归新增metadata内容false、metadata输入支持false两场景，验证不能strict通过且不改变ordinary支持分母。实际运行`boundary-audit-r4.py.txt`，10场景22断言exit0，受测summary SHA256 `5a6a5501ccfa77ac876fe01b7ef38532d58db003d029bdd7aaf02dd6b6280e94`。前8场景13断言同时通过，旧版本结果均保留。

报告不得把第二组61 metadata当成全54答案已穷尽的metadata条目数；第一组同类事实保留在extras。预计ordinary总分母247+564=811仍待最终锁定文件实算。分类是分析实施补充，必须披露发生阶段和依据，不追溯改原盲评或生成登记。

下一步：取得最终证据锁与summary后，核定811 domain、61独立metadata及全部106 extra更新的实际覆盖与严格终点。

## 最终实算与定位整改记录

实际全54实算已完成：逐答案独立推导所有身份/属性分母、required/content complete、ordinary支持/范围支持/unknown/引用率、metadata及strict字段，与root summary一致。P0/A/S strict分别0/18、14/18、4/18；普通事实分母39/357/415，支持39/357/403，范围内支持10/309/321，引用38/357/403，支持unknown0/0/6。全部106 extra索引及19承诺索引/text覆盖；源宏平均精确为A=3/5、S=2/15，不能用合并14/18、4/18替代来源宏平均。所有原盲评锁和仲裁内容hash保持。

独立检查4283处canonical/实际消息/map输出/reduce/最终答案定位逐字一致。另对命题相关性抽查发现：B008-C011/C012和B022-C011/C012的H_VEL未知命题final定位误挂邻近搜索段，虽然子串合法但不包含命题。作者仅派生修正四个final locator，原裁决保留；新合并证据hash`d6e4736da9753cf60b79cc4cb8e77f6cffeb51773c9a8df3002817c6c4b5ee86`再次实算exit0，指标不变，四处定位修复通过。原失败审计保存在`finalaudit.pre-locator-correction.json`。

关键病例独立实读确认：6.2允许SEARCH=0且LATCH非零继续index pulse，6.8的联合例外不能变为零值必然跳过整个search/latch；B017把6.15的HAL mux两种模式/关节0和1扩成不存在的三关节第六例；B015的Transport等是3.1装配动作而非所问度量类别；B006把heading[15132,15154)当整章，真实6.14范围为[15132,15918)。本专家核了这些实际源句与上游输入，不仅引用审计者自报。

仍待闭合的证据定位问题：第二分区若干extra挂泛化Gold/标题/Note而非具体命题。已列具体B017 extra0/2/4及B015 extra0，见`independent-quality/extra-locator-gaps.json`。其individual claims已有较精确的支持/反证，作者应为64个extra补具体对应witness或linked claim，不修改判定、分母或选优。**算术与报告数字通过不自动消除此定位整改项；最终限定结论验收待该项关闭。**

下一步：作者交付第二分区仅定位修正的派生文件、root重新锁定并聚合后，独立复核绑定最终hash并出具完整验收合同。

## 最终验收：全部定位整改关闭

第二分区64 extras已改为297条顶层见证：280 linked atomic claims、9 canonical intervals、4实际最终KG上下文、3 linked qualifiers、1 direct实际链。另direct链内有1个嵌套canonical interval，不与顶层重复计。交接说279原子链接，独立实数为280；其中279个subproposition与目标claim标签逐字相等，B017 extra1→C022为明确的规则应用反证：`(-1,1,-1)`含负值且三关节绝对值相同，应全部同步，与“仅0/1同步”矛盾。已独立读其源规则，不能因标签不逐字相同误拒该有效反证。

已逐一解引用全部280 claim links并核关联collection/ID/命题及已存原文/实际map/reduce/final定位；另检查direct/qualifier/KG/canonical见证。前述B017 extra0/2/4现在挂相应同步、默认禁点动/龙门及homing-inhibit原子命题；B015 extra0挂具体动作与metadata命题，以及步骤3–6真实原句，不再以无关Gold列表代替。全文单元/主体不清的6个H_VEL支持unknown仍保留，没有为通过而升级。

第二分区派生前后去除且仅去除`source_locators`后JSON深层相等，普通564/metadata61/extra64/promise11及所有判定未改变；原31a151…文件保持。第一分区原181515…与v2仅四个final定位12叶变化，判定完全不变。生成配置、原始回执、content两原判及仲裁不变，root旧合并证据/summary另存历史版本。摘要包含派生extra定位，因此修后完整摘要hash变化是预期；不能宣称包含定位的JSON全深层相等，去且仅去source_locators后的54结果及分组等值才是相应不变证据。

最终命令：`.tmp/backend-quality-venv-20261012/Scripts/python.exe -X utf8 -B .tmp/common-three-arm-final-20261015/independent-quality/finalaudit.py.txt`，exit0。独立重算54结果所有核心字段、106 extra/19承诺索引与text、四判断/metadata/strict、来源宏平均、报告数字及4302个定位检查；所有被审文件核前后hash不变。最终无未关闭定位问题。

最终身份：

| 文件 | SHA256 |
|---|---|
| evidence-final.json | e785c892b536bf4231225d8c490795d3f4e1466d6f965f10adf707c8d1b7ebfc |
| quality-summary.json | d8c698be20e8e36bd8eaeb3177843866fa85349cbdd1b36d43ce3d2a77889c69 |
| source1 locator-corrected | 159771f9029e20ff63f8ba1f2c8c294a240f59fb954928cdac53949d11163fb9 |
| source2 locator-corrected | 980b06f64bf6bf3b34712cd6727b9caf0c29473ef7a803e9eece0bf1c9a8a021 |
| 独立finalaudit.py.txt | 93ecfce3cbfcb5764e0acbc0502b167f49e6383818462bcf2f74172b6f5d09df |
| 独立finalaudit.json | b832713d6118f9e6dfb53e64a603057308c54436933dcba6a8acf919665d26a6 |
| 被审评价报告 | 3784aea2f14733cde53c8c90dbbf9fc00ca4c49ae2051b642f27acf5681b5877 |

接受范围：两源六题三重复的描述性开发观察，P0/A/S严格成功0/18、14/18、4/18；来源宏平均0%、60%、13.33%，必要内容齐全0/18、18/18、16/18。A以76108 token保留全部必要内容，S为213324 token；不把更多读取等同更好输出约束。A剩余清单外扩展仍应先检验简单提示层解释，再登记新文档留出。未接受普遍方法优劣、金额结算、可靠总体区间、显著性/等效性、创新或进入新方法设计的结论；H1/H2仍空。

最终报告另已明确英文来源/中文QA、文字only范围；313550 tokens只计本轮生成，不含平台AI内容/证据评审，历史索引40次/119241 tokens单列。补充边界后独立实算再次exit0，表中报告及audit hash已更新绑定当前文件。

完整exact SCI expert contract保存在正式profile的`independent-quality/result.yaml`。下一步：编排者仅归档并封存已审产物，保持M2_OPEN与未来独立留出门槛。
