#!/usr/bin/env python3
"""
LangExtract + DeepSeek (via OpenAI Provider) MVP 验证脚本

流程: 构造模拟文本 → DeepSeek-chat 结构化抽取 → 输出结果
规范: 遵循 docs/LangExtract-Pipeline-Specification.md
"""

import os
import sys
import textwrap

# 确保使用当前虚拟环境
sys.path.insert(0, os.path.dirname(__file__))

import langextract as lx
from langextract.factory import ModelConfig

# ============================================================
# 1. DeepSeek 配置 (遵循规范 §2.3 方式二: ModelConfig 显式配置)
# ============================================================

DEEPSEEK_CONFIG = ModelConfig(
    model_id="deepseek-v4-pro",
    provider="openai",                     # 走 OpenAI 兼容通道
    provider_kwargs={
        "api_key": os.getenv("LANGEXTRACT_API_KEY", ""),
        "base_url": os.getenv("LANGEXTRACT_BASE_URL", "https://api.deepseek.com"),
    },
)

# ============================================================
# 2. 构造模拟文本数据 (符合规范 §1.2 类型一: 纯文本字符串)
# ============================================================

INPUT_TEXT = textwrap.dedent("""\
    患者张三，男，45岁，于2024年3月15日入院。主诉：反复胸闷、气短3月余，加重1周。

    既往史：高血压病史5年，最高血压168/95mmHg，长期口服硝苯地平控释片30mg qd，
    血压控制尚可。2型糖尿病史3年，口服二甲双胍0.5g tid，空腹血糖控制在6-7mmol/L。
    否认冠心病、脑卒中史。吸烟史20年，每天1包，已戒烟2年。

    体格检查：T 36.5°C，P 88次/分，R 20次/分，BP 145/90mmHg。双肺呼吸音清，
    未闻及干湿啰音。心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
    腹软，无压痛，肝脾肋下未及。双下肢无水肿。

    辅助检查：心电图示窦性心律，ST-T改变。心脏超声示左室射血分数(LVEF)55%，
    左室舒张功能减退。冠脉CTA示左前降支(LAD)近段狭窄约70%。

    诊断：1. 冠状动脉粥样硬化性心脏病 2. 高血压病2级 3. 2型糖尿病

    治疗计划：给予阿司匹林肠溶片100mg qd抗血小板，阿托伐他汀钙片20mg qn调脂，
    美托洛尔缓释片47.5mg qd控制心率及血压。建议择期行冠状动脉造影检查，
    必要时行PCI治疗。低盐低脂糖尿病饮食，适度运动，定期门诊随访。
""")

# ============================================================
# 3. 构建 Few-shot 示例 (遵循规范 §1.5)
# ============================================================

PROMPT_DESCRIPTION = textwrap.dedent("""\
    Extract the following medical entities from the clinical note in order of appearance:
    - medication: drug name with attributes (dosage, frequency, purpose)
    - measurement: vital signs or lab values with attributes (value, unit, type)
    - condition: medical diagnosis or symptom with attributes (severity, duration)
    - procedure: medical test or treatment with attributes (method, target)
    - demographic: patient information with attributes (age, gender, habit)

    Use exact text from the source for extraction_text. Do not paraphrase.
    Provide meaningful attributes for each entity.
""")

EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "患者李四，女，60岁，因胸痛2小时入院。BP 160/95mmHg，心率92次/分。"
            "诊断急性心肌梗死。给予阿司匹林300mg嚼服。"
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="demographic",
                extraction_text="女",
                attributes={"gender": "female", "age": "60岁"},
            ),
            lx.data.Extraction(
                extraction_class="condition",
                extraction_text="胸痛",
                attributes={"duration": "2小时", "severity": "acute"},
            ),
            lx.data.Extraction(
                extraction_class="measurement",
                extraction_text="BP 160/95mmHg",
                attributes={"type": "blood_pressure", "systolic": "160", "diastolic": "95"},
            ),
            lx.data.Extraction(
                extraction_class="measurement",
                extraction_text="心率92次/分",
                attributes={"type": "heart_rate", "value": "92"},
            ),
            lx.data.Extraction(
                extraction_class="condition",
                extraction_text="急性心肌梗死",
                attributes={"severity": "acute"},
            ),
            lx.data.Extraction(
                extraction_class="medication",
                extraction_text="阿司匹林300mg",
                attributes={"dosage": "300mg", "route": "oral"},
            ),
        ],
    ),
]

# ============================================================
# 4. 执行抽取
# ============================================================

def main():
    print("=" * 60)
    print("  LangExtract + DeepSeek MVP 验证")
    print("  Provider: OpenAI Compat → api.deepseek.com")
    print("  Model: deepseek-chat")
    print("=" * 60)

    print(f"\n[1] 输入文本 ({len(INPUT_TEXT)} chars):")
    print("    " + INPUT_TEXT[:120].replace("\n", " ") + "...")

    print(f"\n[2] 提交抽取任务...")
    try:
        result = lx.extract(
            text_or_documents=INPUT_TEXT,
            prompt_description=PROMPT_DESCRIPTION,
            examples=EXAMPLES,
            config=DEEPSEEK_CONFIG,
            temperature=0.0,
            max_char_buffer=2000,
            batch_length=1,
            max_workers=1,
            show_progress=True,
            debug=False,
            use_schema_constraints=False,   # DeepSeek 不支持 response_format JSON mode
            fence_output=True,              # 使用 ```yaml  fence 模式
        )
    except Exception as e:
        print(f"\n[错误] 抽取失败: {e}")
        sys.exit(1)

    # ============================================================
    # 5. 输出结果
    # ============================================================

    extractions = result.extractions or []
    grounded = [e for e in extractions if e.char_interval is not None]
    ungrounded = [e for e in extractions if e.char_interval is None]

    print(f"\n[3] 抽取完成:")
    print(f"    总抽取数:   {len(extractions)}")
    print(f"    已接地:     {len(grounded)}")
    print(f"    未接地:     {len(ungrounded)}")

    # 按类别统计
    class_counts = {}
    for e in grounded:
        c = e.extraction_class
        class_counts[c] = class_counts.get(c, 0) + 1

    print(f"\n[4] 按类别统计:")
    for cls, count in sorted(class_counts.items()):
        print(f"    {cls:20s} {count:3d} 个")

    print(f"\n[5] 详细抽取结果 (已接地):")
    print("-" * 60)
    for i, e in enumerate(grounded[:30]):
        ci = e.char_interval
        pos = f"[{ci.start_pos}:{ci.end_pos}]" if ci else "[?]"
        attrs = ", ".join(f"{k}={v}" for k, v in (e.attributes or {}).items()) if e.attributes else "—"
        print(f"  {i+1:2d}. [{e.extraction_class}] {e.extraction_text}")
        print(f"      Pos: {pos} | Attrs: {attrs}")

    if len(grounded) > 30:
        print(f"  ... ({len(grounded) - 30} more)")

    if ungrounded:
        print(f"\n[6] 未接地抽取 (LLM 幻觉/Few-shot 迁移):")
        for i, e in enumerate(ungrounded[:5]):
            print(f"  - [{e.extraction_class}] {e.extraction_text[:60]}...")

    # ============================================================
    # 6. 保存结果
    # ============================================================
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    import json
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = os.path.join(output_dir, f"deepseek_mvp_{timestamp}.jsonl")

    lx.io.save_annotated_documents(
        [result],
        output_dir=output_dir,
        output_name=os.path.basename(jsonl_path),
        show_progress=False,
    )
    print(f"\n[7] 结果已保存: {jsonl_path}")

    # 同时生成结构化摘要 JSON
    summary_path = os.path.join(output_dir, f"deepseek_mvp_{timestamp}_summary.json")
    summary = {
        "model": "deepseek-chat (via OpenAI Provider)",
        "input_chars": len(INPUT_TEXT),
        "total_extractions": len(extractions),
        "grounded": len(grounded),
        "ungrounded": len(ungrounded),
        "class_counts": class_counts,
        "extractions": [
            {
                "class": e.extraction_class,
                "text": e.extraction_text,
                "attributes": e.attributes,
                "char_interval": (
                    [e.char_interval.start_pos, e.char_interval.end_pos]
                    if e.char_interval else None
                ),
            }
            for e in grounded
        ],
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[8] 摘要已保存: {summary_path}")

    print(f"\n{'=' * 60}")
    print(f"  MVP 验证完成")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
