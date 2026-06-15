"""MMMU-Pro loader (sgl-eval-own; NeMo-Skills upstream has no MMMU-Pro).

Fetches ``MMMU/MMMU_Pro`` from HuggingFace and attaches each question's image
as a ``MediaItem`` so the multichoice runner builds an OpenAI vision message.
Options are variable-length (most questions have 10; some fewer) and
``get_mcq_fields`` (vendored) handles any count. ``answer`` is a letter A-J.

The vendoring contract is preserved: nothing here decides a score -- the
multichoice grader (``eval_mcq``) and aggregator (``MathMetrics``) stay
vendored. This module is transport (dataset fetch + NS-shape row build).
"""

from __future__ import annotations

import io
from typing import List, Optional

from sgl_eval._vendored.nemo_skills.dataset._utils import get_mcq_fields
from sgl_eval.types import Example, MediaItem

_DATASET = "MMMU/MMMU_Pro"
_CONFIG = "standard (10 options)"


def load_mmmu_pro(split: str = "test", num_examples: Optional[int] = None) -> List[Example]:
    """Load MMMU-Pro ``split`` as Examples with the question image attached."""
    from datasets import load_dataset  # lazy: heavy import, benchmark-specific

    ds = load_dataset(_DATASET, _CONFIG, split=split)
    examples: List[Example] = []
    for i, row in enumerate(ds):
        question = row["question"]
        options = row.get("options")
        if isinstance(options, str):
            # HF stores MMMU_Pro options as a Python-literal string ("['a','b',...]"),
            # not a list; list(str) would split it into characters.
            import ast

            options = ast.literal_eval(options)
        options = list(options or [])
        answer = _normalize_answer(row.get("answer"))
        problem = get_mcq_fields(question, options)["problem"]
        examples.append(
            Example(
                id=row.get("id") or f"mmmu_pro-{i}",
                inputs={"problem": problem},
                target=answer,
                meta={
                    "subject": row.get("subject"),
                    "difficulty": row.get("difficulty"),
                    "image_type": row.get("image_type"),
                },
                media=_image_media(row.get("image")),
            )
        )
        if num_examples is not None and len(examples) >= num_examples:
            break
    return examples


def _normalize_answer(answer) -> Optional[str]:
    """MMMU-Pro answers are letters; tolerate an int index just in case."""
    if answer is None:
        return None
    if isinstance(answer, int):
        return chr(ord("A") + answer)
    return str(answer).strip().upper()[:1] or None


def _image_media(image) -> List[MediaItem]:
    if image is None:
        return []
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return [MediaItem(kind="image", data=buf.getvalue(), mime="image/png")]
