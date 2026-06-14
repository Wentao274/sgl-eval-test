"""Vision-aware message construction shared by multimodal benchmarks.

``build_user_content`` turns a prompt + ``Example.media`` list into an
OpenAI-style ``content``: a plain string when there is no media (so text
benchmarks stay byte-for-byte compatible), or a list of text / image_url /
video_url blocks otherwise. The sampler passes it through unchanged.
"""

from __future__ import annotations

import base64
from typing import List, Union

from sgl_eval.types import MediaItem

ContentType = Union[str, list]


def build_user_content(prompt: str, media: List[MediaItem]) -> ContentType:
    """Render a user message ``content`` for the given prompt + media.

    No media -> plain string (text-benchmark path, unchanged). Images inline
    as ``data:`` base64; video uses a URL (too large to inline). The video
    block name is provider-specific (OpenAI ``input_video`` / sglang
    ``video_url``) and is settled when a video benchmark is wired up.
    """
    if not media:
        return prompt
    content: list = [{"type": "text", "text": prompt}]
    for m in media:
        if m.kind == "image":
            url = m.url or _data_url(m.data, m.mime or "image/png")
            content.append({"type": "image_url", "image_url": {"url": url}})
        elif m.kind == "video":
            if not m.url:
                raise ValueError("video MediaItem requires a url (too large to base64-inline)")
            content.append({"type": "video_url", "video_url": {"url": m.url}})
        else:
            raise ValueError(f"unsupported media kind: {m.kind!r}")
    return content


def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
