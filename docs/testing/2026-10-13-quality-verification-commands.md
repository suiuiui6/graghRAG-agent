# 2026-10-13 最终质量验证命令

工作目录为仓库根；Python是独立 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，不是原backend/.venv。命令时间、git基线和158输入hash见r2输入快照；完整退出码单独保存。coverage7.6.12从独立运行目录注入，不修改产品锁来安装测量工具。运行时版本见[candidate-runtime.txt](2026-10-13-candidate-runtime.txt)。

```powershell
$env:PYTHON_DOTENV_DISABLED='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONUTF8='1'
$env:PYTHONPATH='D:/graghRAG-agent/.tmp/coverage-runtime-py312-20261012'
& .tmp/backend-quality-venv-20261012/Scripts/python.exe docs/testing/capture_quality_snapshot.py docs/testing/2026-10-13-quality-verified-r2-inputs-before.json
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -X utf8 -m coverage run --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/2026-10-13-quality-verified-r2-backend.coverage -m pytest backend/tests backend/research/test_deepseek_scope_pilot.py -q --tb=short -p no:cacheprovider --basetemp backend/tests/_sandbox_tmp/quality-verified-r2-20261013
# pytest退出码先保存为quality-verified-r2-backend-exit.txt，未用后续成功覆盖它。
& .tmp/backend-quality-venv-20261012/Scripts/python.exe -X utf8 -m coverage json --rcfile=docs/testing/coverage-backend-2026-10-12.ini --data-file=docs/testing/2026-10-13-quality-verified-r2-backend.coverage -o docs/testing/2026-10-13-quality-verified-r2-backend-coverage.json
# export退出码单独保存为quality-verified-r2-coverage-export-exit.txt。
& .tmp/backend-quality-venv-20261012/Scripts/python.exe docs/testing/capture_quality_snapshot.py docs/testing/2026-10-13-quality-verified-r2-inputs-after.json
& .tmp/backend-quality-venv-20261012/Scripts/python.exe docs/testing/check_candidate_dependencies.py
& .tmp/audit-tools-20261012/Scripts/python.exe -m pip_audit -r docs/testing/2026-10-13-candidate-registry-pins.txt --no-deps --disable-pip --strict --desc on -f json -o docs/testing/2026-10-13-candidate-pip-audit.json
$qualityInputs=Get-Content docs/testing/2026-10-13-quality-final-inputs-before.json -Raw | ConvertFrom-Json
& .tmp/audit-tools-20261012/Scripts/python.exe -m bandit @($qualityInputs.production_files) -f json -o docs/testing/2026-10-13-quality-final-bandit.json
& .tmp/audit-tools-20261012/Scripts/python.exe docs/testing/summarize_quality_verification.py 2026-10-13-quality-verified-r2
```

实际执行通过PowerShell重定向到同名前缀log，每次保存`$LASTEXITCODE`到对应exit.txt，并以pytest原始状态退出。扫描非零退出均保留；不使用coverage ignore、修改报告、弱化断言或缩减业务范围。全量测试需要本机asyncio/socketpair/loopback，已申请沙箱外执行，模型/云服务保持离线。审计联网仅发送公开包名与版本。

Bandit显式使用90生产文件清单。首次扫描递归包括了research/test_deepseek_scope_pilot.py；当前排除该真实pytest文件并纳入正式isolated_guard.py，与经独立审查的生产/测试分类一致。因此180→141发现数不能解释成39个生产缺陷已修复；当前4个中危仍为table_index.py的B608。Bandit未忽略规则（nosec=0、skipped_tests=0），扫描errors=[]。

所有失败历史保留：2026-10-12整改后coverage导出失败；2026-10-13首轮新环境测试适配失败；verified首轮旧工具替身污染失败。只有r2对应最终快照，仍需分别判断测试/双指标/安全门槛，不能以JSON成功导出替代pytest成功。
