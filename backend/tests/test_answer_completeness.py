from generator import _complete_answer_text, _repair_answer_text


def test_repair_answer_text_rewrites_empty_query_response_when_context_exists():
    repaired = _repair_answer_text(
        answer_text="您的问题内容为空，请提供具体问题以便我根据文档内容进行回答。",
        query="这篇论文的标题是什么？",
        context_chunks=[
            {
                "chunk_id": "c00001",
                "text": "论文标题为《风电光伏制氢氨协同优化运行研究》。",
                "source": "vector",
            }
        ],
    )

    assert "问题内容为空" not in repaired
    assert "风电光伏制氢氨协同优化运行研究" in repaired


def test_repair_answer_text_rewrites_premature_refusal_when_context_has_support():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的 W4S1 场景代表什么？",
        context_chunks=[
            {
                "chunk_id": "c00019",
                "text": "W4S1 表示风电4、光伏1的容量配比场景。",
                "source": "kg",
            }
        ],
    )

    assert "文档中未提及" not in repaired
    assert "W4S1" in repaired
    assert "[c00019]" in repaired


def test_repair_answer_text_keeps_refusal_when_context_is_actually_empty():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的 W4S1 场景代表什么？",
        context_chunks=[],
    )

    assert repaired == "文档中未提及此信息。"


def test_repair_answer_text_rewrites_generation_error_when_context_has_supported_fact():
    repaired = _repair_answer_text(
        answer_text="??????????????",
        query="What is the paper title?",
        context_chunks=[
            {
                "chunk_id": "c00001",
                "text": "Paper title: Wind-Solar Hydrogen-Ammonia Cooperative Optimization.",
                "source": "vector",
            }
        ],
    )

    assert repaired != "??????????????"
    assert "Wind-Solar Hydrogen-Ammonia Cooperative Optimization" in repaired
    assert "[c00001]" in repaired


def test_repair_answer_text_rewrites_generation_error_for_inventory_queries():
    repaired = _repair_answer_text(
        answer_text="???????????",
        query="List all figure items in the paper.",
        context_chunks=[
            {
                "chunk_id": "c00031",
                "text": "Figure 1. Problem 1 campus power curve.",
                "source": "vector",
            },
            {
                "chunk_id": "c00032",
                "text": "Figure 2. Problem 2 discrete ammonia scheduling.",
                "source": "vector",
            },
            {
                "chunk_id": "c00033",
                "text": "Figure 3. Problem 2 annual ammonia cost distribution.",
                "source": "vector",
            },
        ],
    )

    assert repaired != "???????????"
    assert "[c00031]" in repaired
    assert "[c00032]" in repaired
    assert "[c00033]" in repaired
    assert repaired.count("- ") >= 3


def test_repair_answer_text_does_not_echo_raw_kg_json_when_refusal_is_repaired():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的wind 4 solar 1场景代表什么含义?",
        context_chunks=[
            {
                "chunk_id": "d1_n0039",
                "text": '{"entity": {"node_id": "d1_n0039", "entity_type": "dataset", "label": "24种风光出力场景", "properties": {"name": "24 wind-solar power output scenarios"}}}',
                "source": "kg",
            },
            {
                "chunk_id": "d0_n0035",
                "text": "W4S1 表示最大弃电场景（maximum curtailment scenario）。",
                "source": "kg",
            },
        ],
    )

    assert '{"entity"' not in repaired
    assert "W4S1" in repaired


def test_repair_answer_text_prefers_top_ranked_support_over_later_lexical_noise():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的wind 4 solar 1场景代表什么含义?",
        context_chunks=[
            {
                "chunk_id": "d0_n0035",
                "text": "W4S1 表示最大弃电场景（maximum curtailment scenario）。",
                "source": "kg",
            },
            {
                "chunk_id": "c00030",
                "text": "核心代码文件solve.py（约1600行）包含以下主要模块：风电4、光伏1、场景枚举等。",
                "source": "vector",
            },
        ],
    )

    assert "W4S1" in repaired
    assert "[d0_n0035]" in repaired


def test_repair_answer_text_can_summarize_raw_kg_json_into_readable_text():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的wind 4 solar 1场景代表什么含义?",
        context_chunks=[
            {
                "chunk_id": "d0_n0035",
                "text": '{"entity":{"node_id":"d0_n0035","label":"W4S1","properties":{"name":"maximum curtailment scenario","description":"wind 4 solar 1 scenario"}}}',
                "source": "kg",
            },
        ],
    )

    assert '{"entity"' not in repaired
    assert "W4S1" in repaired
    assert "maximum curtailment scenario" in repaired


def test_repair_answer_text_prefers_summarizable_top_kg_json_over_later_noise():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中提到的wind 4 solar 1场景代表什么含义?",
        context_chunks=[
            {
                "chunk_id": "d0_n0035",
                "text": '{"entity":{"node_id":"d0_n0035","label":"W4S1","properties":{"name":"maximum curtailment scenario","description":"wind 4 solar 1 scenario"}}}',
                "source": "kg",
            },
            {
                "chunk_id": "c00030",
                "text": "核心代码文件solve.py（约1600行）包含以下主要模块：风电4、光伏1、场景枚举等。",
                "source": "vector",
            },
        ],
    )

    assert "W4S1" in repaired
    assert "maximum curtailment scenario" in repaired
    assert "[d0_n0035]" in repaired


def test_repair_answer_text_prefers_figure_chunk_for_figure_queries():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="图 5 展示了什么内容？",
        context_chunks=[
            {
                "chunk_id": "c00031",
                "text": "图 5— 问题四离网与储能分析（左：三种模式经济性对比；右：储能充放电调度）",
                "source": "vector",
            },
            {
                "chunk_id": "c00005",
                "text": "五个问题形成基准线建立、灵活性引入、调节方式升级、独立性检验、宏观扩展的递进逻辑链。",
                "source": "vector",
            },
        ],
    )

    assert "图 5" in repaired
    assert "储能充放电调度" in repaired
    assert "[c00031]" in repaired


def test_repair_answer_text_rewrites_vague_alias_guess_when_exact_kg_support_exists():
    repaired = _repair_answer_text(
        answer_text="文中未明确解释，可能代表第4种风电和第1种光伏组合。",
        query="论文中提到的wind 4 solar 1场景代表什么含义?",
        context_chunks=[
            {
                "chunk_id": "d0_n0035",
                "text": "W4S1 表示最大弃电场景（maximum curtailment scenario），对应弃电量 173.7 MWh。",
                "source": "kg",
            },
            {
                "chunk_id": "c00030",
                "text": "泛化背景说明。",
                "source": "vector",
            },
        ],
    )

    assert "未明确解释" not in repaired
    assert "最大弃电场景" in repaired
    assert "173.7" in repaired
    assert "[d0_n0035]" in repaired


def test_repair_answer_text_keeps_refusal_when_only_pseudo_support_mentions_generic_factor_terms():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="本论文的影响因子(impact factor)是多少？",
        context_chunks=[
            {
                "chunk_id": "c00019",
                "text": "风光出力水平是吨氨成本的核心决定因素，对综合经济性影响显著。",
                "source": "vector",
            }
        ],
    )

    assert repaired == "文档中未提及此信息。"


def test_repair_answer_text_keeps_refusal_for_scenario_metric_query_without_exact_scenario_support():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="W2S2 场景的绿电消纳率是多少？",
        context_chunks=[
            {
                "chunk_id": "c00002",
                "text": "三项绿电直连指标中，新能源自发自用率28.2%，上网电量比例35.9%，绿电指标全满足率39.2%。",
                "source": "bm25",
            },
            {
                "chunk_id": "c00022",
                "text": "针对最大弃电场景W4S1（弃电量173.7MWh/日），最优储能配置为210.4MWh/30MW，加储能后风光利用率达100%。",
                "source": "vector",
            },
        ],
    )

    assert repaired == "文档中未提及此信息。"


def test_repair_answer_text_inventory_query_lists_all_supported_items_instead_of_one_snippet():
    repaired = _repair_answer_text(
        answer_text="文档中未提及此信息。",
        query="论文中所有的图(figure)有哪些？",
        context_chunks=[
            {
                "chunk_id": "c00031",
                "text": "图 1 问题一园区功率曲线。",
                "source": "vector",
            },
            {
                "chunk_id": "c00032",
                "text": "图 2 问题二离散制氨最优调度。",
                "source": "vector",
            },
            {
                "chunk_id": "c00033",
                "text": "图 3 问题二全年吨氨成本分布。",
                "source": "vector",
            },
        ],
    )

    assert "图 1" in repaired
    assert "图 2" in repaired
    assert "图 3" in repaired
    assert repaired.count("- ") >= 3


def test_repair_answer_text_prefers_visualization_library_support_over_title_noise():
    repaired = _repair_answer_text(
        answer_text="??????????",
        query="???????????",
        context_chunks=[
            {
                "chunk_id": "c00002",
                "text": "?????A ????????????????",
                "source": "vector",
            },
            {
                "chunk_id": "c00152",
                "text": "???????? Python 3.10 ????? PuLP ????? CBC ????? MILP/LP ????? NumPy ? Pandas ????????? Matplotlib ??????",
                "source": "vector",
            },
        ],
    )

    assert "[c00152]" in repaired
    assert any(token in repaired for token in ("Matplotlib", "Python 3.10"))


def test_repair_answer_text_inventory_query_lists_all_method_families_when_context_is_split():
    repaired = _repair_answer_text(
        answer_text="??????????",
        query="???????????????????????",
        context_chunks=[
            {
                "chunk_id": "c00005",
                "text": "??????????????MILP??????????????????????????LP??",
                "source": "vector",
            },
            {
                "chunk_id": "c00148",
                "text": "????????????RO??????????SP??????????????????????",
                "source": "vector",
            },
        ],
    )

    assert "MILP" in repaired
    assert "RO" in repaired
    assert repaired.count("- ") >= 2


def test_repair_answer_text_inventory_query_lists_all_cost_indicators_from_abstract_support():
    repaired = _repair_answer_text(
        answer_text="??????????",
        query="???????????????????????",
        context_chunks=[
            {
                "chunk_id": "c00002",
                "text": "???????????????3554?/??5820?/??7111?/??3669?/??5652?/??",
                "source": "vector",
            },
            {
                "chunk_id": "c00143",
                "text": "????????????",
                "source": "vector",
            },
        ],
    )

    assert "3554" in repaired
    assert "[c00002]" in repaired
    assert repaired.count("- ") >= 1


def test_complete_answer_text_adds_data_processing_role_for_pandas_usage_query():
    completed = _complete_answer_text(
        answer_text="Pandas 是使用的库 [c00152]。",
        query="Pandas processing purpose",
        context_chunks=[{"chunk_id": "c00152", "text": "使用 Pandas 进行数据处理。", "source": "vector"}],
    )
    assert "Pandas" in completed and "数据处理" in completed
    assert "[c00152]" in completed and "???" not in completed


def test_complete_answer_text_adds_implementation_purpose_for_python_role_query():
    completed = _complete_answer_text(
        answer_text="使用 Python 3.10 [c00152]。",
        query="Python 3.10 implementation purpose",
        context_chunks=[{"chunk_id": "c00152", "text": "程序采用 Python 3.10 实现。", "source": "vector"}],
    )
    assert "Python 3.10" in completed and "程序实现" in completed
    assert "[c00152]" in completed and "???" not in completed


def test_complete_answer_text_adds_bilingual_alias_meaning_when_only_english_phrase_is_present():
    completed = _complete_answer_text(
        answer_text="W4S1 maximum curtailment scenario 173.7 MWh/day curtailment [d0_n0035]",
        query="wind 4 solar 1 是什么含义？",
        context_chunks=[{"chunk_id": "d0_n0035", "text": "W4S1 表示 maximum curtailment scenario，弃电量173.7 MWh/day。", "source": "kg"}],
    )
    assert "最大弃电场景" in completed and "maximum curtailment scenario" in completed
    assert "173.7 MWh/day" in completed and "[d0_n0035]" in completed
    assert "???" not in completed
