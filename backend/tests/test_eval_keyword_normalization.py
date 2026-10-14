from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_metrics_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "iteration-2" / "eval-2-existing-components" / "rag_eval" / "metrics_a2_faithfulness.py"
    spec = spec_from_file_location("metrics_a2_faithfulness", module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_keyword_hits_normalizes_figure_spacing_and_number_units():
    metrics = _load_metrics_module()

    found, missing = metrics._keyword_hits(
        ["图 2", "图 5", "0.75MW", "36吨", "wind 4 solar 1"],
        "答案列出了图2、图5，并给出 0.75 MW 和 36 吨；对应 W4S1 场景。",
    )

    assert found == ["图 2", "图 5", "0.75MW", "36吨", "wind 4 solar 1"]
    assert missing == []
