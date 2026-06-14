"""Tests for the MMMU-Pro loader (SE-own; HF dataset mocked, no network)."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL.Image")  # pillow ships with datasets

from sgl_eval.evals._mmmu_pro import _image_media, _normalize_answer, load_mmmu_pro  # noqa: E402


def _fake_row(idx="r1", answer="B", n_options=10, with_image=True):
    from PIL import Image

    return {
        "id": idx,
        "question": f"Question {idx}?",
        "options": [f"opt{i}" for i in range(n_options)],
        "answer": answer,
        "image": Image.new("RGB", (8, 8)) if with_image else None,
        "subject": "Art",
        "difficulty": "Easy",
        "image_type": ["Paintings"],
    }


def test_normalize_answer_letter():
    assert _normalize_answer("b") == "B"
    assert _normalize_answer("J") == "J"


def test_normalize_answer_int_index():
    assert _normalize_answer(3) == "D"


def test_normalize_answer_none():
    assert _normalize_answer(None) is None


def test_image_media_png():
    from PIL import Image

    media = _image_media(Image.new("RGB", (4, 4)))
    assert len(media) == 1
    assert media[0].kind == "image"
    assert media[0].mime == "image/png"
    assert media[0].data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature


def test_image_media_none():
    assert _image_media(None) == []


def test_load_mmmu_pro_end_to_end(monkeypatch):
    import datasets

    fake_ds = [_fake_row("r1", "B", 10), _fake_row("r2", "J", 5, with_image=False)]
    monkeypatch.setattr(datasets, "load_dataset", lambda *a, **k: fake_ds)

    examples = load_mmmu_pro(num_examples=None)
    assert len(examples) == 2

    ex0 = examples[0]
    assert ex0.id == "r1"
    assert ex0.target == "B"
    assert "Question r1?" in ex0.inputs["problem"]
    assert "A) opt0" in ex0.inputs["problem"]
    assert "J) opt9" in ex0.inputs["problem"]  # 10 options -> A..J
    assert len(ex0.media) == 1
    assert ex0.media[0].mime == "image/png"
    assert ex0.meta["subject"] == "Art"

    ex1 = examples[1]
    assert ex1.target == "J"
    assert ex1.media == []  # no image -> empty media
    assert "E) opt4" in ex1.inputs["problem"]  # 5 options -> A..E
    assert "F)" not in ex1.inputs["problem"]


def test_load_mmmu_pro_num_examples(monkeypatch):
    import datasets

    monkeypatch.setattr(
        datasets, "load_dataset", lambda *a, **k: [_fake_row(f"r{i}") for i in range(20)]
    )
    examples = load_mmmu_pro(num_examples=3)
    assert len(examples) == 3


def test_mmmu_pro_registered():
    """MMMU-Pro registers as a multichoice benchmark."""
    from sgl_eval.registry import get

    spec = get("mmmu_pro")
    assert spec.category == "multichoice"
    assert spec.default_n_repeats == 1
    assert "MMMU-Pro" in spec.description
