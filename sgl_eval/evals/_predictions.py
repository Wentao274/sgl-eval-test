"""Build prediction dicts that match upstream NeMo-Skills' wire shape.

Both ``MathEvaluator.eval_single`` (during sampling) and ``MathMetrics.update``
(during aggregation) consume dicts with the same field set. We mint that dict
once here and reuse it on both sides so the data we feed into vendored code
matches the contract upstream's own ``inference/generate.py`` would produce.
"""

from __future__ import annotations

from typing import Any, Dict

from sgl_eval.types import Example, Sample


def sample_to_pred(sample: Sample, example: Example) -> Dict[str, Any]:
    completion = sample.completion_tokens or 0
    reasoning = sample.reasoning_tokens or 0
    pred: Dict[str, Any] = {
        "expected_answer": str(example.target),
        "num_generated_tokens": completion,
        "num_reasoning_tokens": reasoning,
        "num_answer_tokens": max(completion - reasoning, 0),
        "problem": example.inputs.get("problem", ""),
    }
    # Upstream's ``BaseMetrics.update`` skips entries that omit the timestamp
    # keys, so include them only when valid (avoids min(...) collapsing to 0).
    if sample.generation_start_time is not None:
        pred["generation_start_time"] = sample.generation_start_time
    if sample.generation_end_time is not None:
        pred["generation_end_time"] = sample.generation_end_time
    return pred
