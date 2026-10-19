# 匿名裁决包本地验证

2026-10-15。代码：backend/research/common_evaluation_packets.py，root负责；仅后处理，不进入生成runtime。

已执行锁定环境 `.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -` 的临时目录合成54单元打包检查，exit0：profile终止文件缺失时拒绝读Gold；54答案一一映射，Gold紧凑包36项/81scoring_atoms；匿名答案只含answer_id/question_id/answer/run_status，不含arm/repeat；同目录重打包拒绝。合成文本仅为测试，临时目录自动移除，不混入研究结果。

随后新增validate_judgments结构校验函数：要求每答案、Gold item和atom均覆盖，三值类型正确，true atom有实际答案子串定位；这仅验证结构与引文归属，不自动判断语义。该新增函数须随实际裁决包再次验证后才算已验证。

研究生成及语义裁决此时均未执行，不构成生产全量测试/覆盖率/人工Gold认证。
