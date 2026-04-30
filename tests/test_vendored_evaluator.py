"""Smoke tests for the vendored evaluator slice: ``MathEvaluator``,
prompt yaml render, dataset metadata, bundled aime test.txt loading.
"""

from __future__ import annotations

import asyncio


def test_math_evaluator_eval_single():
    from sgl_eval._vendored.nemo_skills.evaluator.math import MathEvaluator

    ev = MathEvaluator(config={})
    dp = {"generation": "Reasoning... \\boxed{42}", "expected_answer": "42"}
    out = asyncio.run(ev.eval_single(dp))
    assert out["predicted_answer"] == "42"
    assert out["symbolic_correct"] is True


def test_math_evaluator_wrong_answer():
    from sgl_eval._vendored.nemo_skills.evaluator.math import MathEvaluator

    ev = MathEvaluator(config={})
    dp = {"generation": "Reasoning... \\boxed{41}", "expected_answer": "42"}
    out = asyncio.run(ev.eval_single(dp))
    assert out["symbolic_correct"] is False


def test_dataset_metadata_aime25():
    from sgl_eval._vendored.nemo_skills.dataset import aime25

    assert aime25.METRICS_TYPE == "math"
    assert "prompt_config=generic/math" in aime25.GENERATION_ARGS


def test_aime25_bundled_data_loads():
    from sgl_eval.evals._loader import load_bundled

    loader = load_bundled("aime25")
    exs = loader(None)
    assert len(exs) == 30
    assert all(e.target.isdigit() or e.target.lstrip("-").isdigit() for e in exs)


def test_aime24_bundled_data_loads():
    from sgl_eval.evals._loader import load_bundled

    loader = load_bundled("aime24")
    exs = loader(None)
    assert len(exs) == 30


def test_prompt_render_no_few_shot():
    from sgl_eval.evals._math import render_math_prompt

    rendered = render_math_prompt("What is 2+2?")
    assert "Solve the following math problem" in rendered
    assert "\\boxed{}" in rendered
    assert "What is 2+2?" in rendered
    assert "{examples}" not in rendered


def test_prompt_render_with_few_shot():
    from sgl_eval.evals._math import render_math_prompt

    rendered = render_math_prompt(
        "Find x.",
        few_shot_examples=[{"problem": "1+1=?", "solution": "\\boxed{2}"}],
    )
    assert "Here are some examples" in rendered
    assert "1+1=?" in rendered
    assert "Find x." in rendered
