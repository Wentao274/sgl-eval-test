"""Smoke tests for the vendored math chain. We verify the surface we
actually call from benchmark code: ``extract_answer``, ``math_equal``,
``MathMetrics``. We do **not** vendor upstream's full test suite by design
(per ROADMAP "Dependency policy" — drift detection comes from upstream
dep mirroring, not from a parallel test set).
"""

from __future__ import annotations

import pytest

from sgl_eval._vendored.nemo_skills.math_grader import extract_answer, math_equal
from sgl_eval._vendored.nemo_skills.math_metrics import MathMetrics


@pytest.mark.parametrize(
    "gt,pred,expected",
    [
        ("70", "70", True),
        ("70", "070", True),
        ("1/2", 0.5, True),
        ("\\frac{1}{2}", 0.5, True),
        ("70", "69", False),
        (0, None, False),
    ],
)
def test_math_equal_basics(gt, pred, expected):
    assert math_equal(gt, pred) is expected


def test_math_equal_take_modulo_param():
    """``take_modulo`` is supported by the vendored grader. sgl-eval does
    not currently pass it (upstream's aime configs don't either), but the
    parameter exists and we exercise it as a unit test."""
    assert math_equal("42", "1042", take_modulo=1000)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Answer is \\boxed{42}", "42"),
        ("\\boxed{x^2}", "x^2"),
        ("nothing here", None),
    ],
)
def test_extract_answer_boxed(text, expected):
    assert extract_answer(text) == expected


def test_extract_answer_relaxed_falls_back():
    """relaxed=True tries the regex first then boxed."""
    assert extract_answer("The final answer is 7", relaxed=True) == "7"


def test_math_metrics_smoke():
    m = MathMetrics()
    preds = [
        {
            "predicted_answer": "42",
            "expected_answer": "42",
            "symbolic_correct": True,
            "num_generated_tokens": 10,
            "problem": "q",
        },
        {
            "predicted_answer": "42",
            "expected_answer": "42",
            "symbolic_correct": True,
            "num_generated_tokens": 12,
            "problem": "q",
        },
    ]
    m.update(preds)
    out = m.get_metrics()
    assert "majority@2" in out
    assert "pass@2" in out
    assert "pass@1[avg-of-2]" in out
    assert out["pass@2"]["symbolic_correct"] == 100.0
