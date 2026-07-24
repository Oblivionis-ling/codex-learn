#!/usr/bin/env python3
"""OCR multiple images while loading RapidOCR only once."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from learn_config import absolute_path
from tool_runtime import (
    configure_process_environment,
    configured_paths,
    emit,
    write_json_atomic,
)


def box_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="image files processed by one OCR engine instance")
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-threshold", type=float, default=0.85)
    parser.add_argument("--no-orientation", action="store_true", help="skip text orientation classification")
    args = parser.parse_args()

    paths = [absolute_path(value) for value in args.inputs]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        emit({"ok": False, "error": "input files not found", "missing": missing})
        return 1

    config, _, model_root = configured_paths()
    configure_process_environment(config, model_root)
    from rapidocr import RapidOCR

    started = time.perf_counter()
    engine = RapidOCR()
    model_load_seconds = time.perf_counter() - started
    images: list[dict[str, Any]] = []
    for path in paths:
        image_started = time.perf_counter()
        result = engine(path, use_cls=not args.no_orientation)
        texts = list(result.txts or [])
        scores = [round(float(score), 5) for score in (result.scores or [])]
        boxes = box_list(result.boxes)
        lines = [
            {"text": text, "score": scores[index], "box": boxes[index] if index < len(boxes) else []}
            for index, text in enumerate(texts)
        ]
        images.append(
            {
                "path": str(path),
                "elapsed_seconds": round(time.perf_counter() - image_started, 3),
                "lines": lines,
                "needs_visual_review": not lines or any(
                    item["score"] < args.review_threshold for item in lines
                ),
            }
        )

    payload = {
        "schema_version": 1,
        "engine": "RapidOCR",
        "model_profile": "PP-OCRv6-small",
        "model_load_seconds": round(model_load_seconds, 3),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "review_threshold": args.review_threshold,
        "images": images,
    }
    output = absolute_path(args.output)
    write_json_atomic(output, payload)
    emit(
        {
            "ok": True,
            "output": str(output),
            "images": len(images),
            "lines": sum(len(item["lines"]) for item in images),
            "visual_review": sum(bool(item["needs_visual_review"]) for item in images),
            "elapsed_seconds": payload["elapsed_seconds"],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
