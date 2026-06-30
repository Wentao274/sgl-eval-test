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

import ast
import io
import re
import warnings
from typing import List, Optional

from sgl_eval._vendored.nemo_skills.dataset._utils import get_mcq_fields
from sgl_eval.types import Example, MediaItem

_DATASET = "MMMU/MMMU_Pro"
# MMMU-Pro ships 3 configs; "standard (10 options)" is the hard variant.
_CONFIG = "standard (10 options)"
# Questions reference images as <image n>; the dataset stores them in columns
# image_1..image_7 (there is no single "image" column).
_IMAGE_REF_RE = re.compile(r"<image\s+(\d+)>")


def load_mmmu_pro(split: str = "test", num_examples: Optional[int] = None) -> List[Example]:
    """Load MMMU-Pro ``split`` as Examples with the question image(s) attached.

    Per-row data errors (malformed options, a referenced ``<image n>`` whose
    column is missing) warn and skip the row instead of silently degrading to a
    text-only / unanswerable sample -- the failure mode behind the original 9%
    baseline. A single bad row does not abort the whole load.
    """
    from datasets import load_dataset  # lazy: heavy import, benchmark-specific

    ds = load_dataset(_DATASET, _CONFIG, split=split)
    examples: List[Example] = []
    for i, row in enumerate(ds):
        try:
            examples.append(_build_example(row, i))
        except ValueError as e:
            warnings.warn(f"skipping MMMU-Pro row {row.get('id') or i}: {e}")
            continue
        if num_examples is not None and len(examples) >= num_examples:
            break
    return examples


def _build_example(row, i: int) -> Example:
    question = row["question"]
    images = _images_for_question(row, question)
    # Replace <image n> with [image] so build_user_content splices it in place.
    question = _IMAGE_REF_RE.sub("[image]" if images else "", question)
    options = _parse_options(row)
    answer = _normalize_answer(row.get("answer"))
    problem = get_mcq_fields(question, options)["problem"]
    return Example(
        id=row.get("id") or f"mmmu_pro-{i}",
        inputs={"problem": problem},
        target=answer,
        meta={
            "subject": row.get("subject"),
            "difficulty": row.get("topic_difficulty"),
            "image_type": row.get("img_type"),
        },
        media=_image_media(images),
    )


def _parse_options(row) -> list:
    options = row.get("options")
    if isinstance(options, str):
        # HF stores MMMU_Pro options as a Python-literal string ("['a','b',...]"),
        # not a list; list(str) would split it into characters. literal_eval can
        # also return a non-list (e.g. a bare quoted string), so the result is
        # checked -- otherwise list() re-introduces the per-character split.
        try:
            options = ast.literal_eval(options)
        except (ValueError, SyntaxError) as e:
            raise ValueError(f"cannot parse options literal: {e}") from e
    if not isinstance(options, (list, tuple)):
        raise ValueError(f"options is {type(options).__name__}, expected a list")
    options = list(options)
    if not options:
        raise ValueError("empty options")
    return options


def _normalize_answer(answer) -> Optional[str]:
    """MMMU-Pro answers are letters; tolerate an int index just in case."""
    if answer is None:
        return None
    if isinstance(answer, int):
        return chr(ord("A") + answer)
    return str(answer).strip().upper()[:1] or None


def _images_for_question(row, question: str) -> List:
    """Pick image_1..image_7 columns referenced by <image n>.

    A referenced ``<image n>`` whose column is missing is a data error and
    raises -- silently dropping the marker and sending text-only was the
    original ~40% bug. Rows with no marker fall back to ``image_1`` (then a
    flat ``image`` column) so an unmarked image is still attached, not dropped.
    """
    ids = [int(m.group(1)) for m in _IMAGE_REF_RE.finditer(question)]
    if ids:
        images = []
        for n in ids:
            img = row.get(f"image_{n}")
            if img is None:
                raise ValueError(f"question references <image {n}> but image_{n} is missing")
            images.append(img)
        return images
    img = row.get("image_1")
    if img is None:
        img = row.get("image")  # back-compat if a flat image column ever appears
    return [img] if img is not None else []


def _image_media(images) -> List[MediaItem]:
    if not images:
        return []
    if not isinstance(images, (list, tuple)):
        images = [images]
    media: List[MediaItem] = []
    for image in images:
        if image is None:
            continue
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        media.append(MediaItem(kind="image", data=buf.getvalue(), mime="image/png"))
    return media
