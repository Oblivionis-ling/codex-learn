#!/usr/bin/env python3
"""Extract many timestamped frames from one video in a single process."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from learn_config import absolute_path
from tool_runtime import emit, write_json_atomic


def contact_sheet(frame_paths: list[Path], timestamps: list[float], output: Path) -> None:
    from PIL import Image, ImageDraw

    thumbs: list[Image.Image] = []
    for path, seconds in zip(frame_paths, timestamps):
        image = Image.open(path).convert("RGB")
        image.thumbnail((480, 270))
        canvas = Image.new("RGB", (480, 305), "white")
        canvas.paste(image, ((480 - image.width) // 2, 0))
        ImageDraw.Draw(canvas).text((12, 280), f"{seconds:.3f}s", fill="black")
        thumbs.append(canvas)
    columns = 2
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 480, rows * 305), "white")
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % columns) * 480, (index // columns) * 305))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--timestamps", nargs="+", type=float, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--contact-sheet")
    args = parser.parse_args()

    video = absolute_path(args.video)
    if not video.is_file():
        emit({"ok": False, "error": f"video not found: {video}"})
        return 1
    timestamps = sorted(set(max(0.0, value) for value in args.timestamps))
    output_dir = absolute_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import cv2

    cv2.setNumThreads(max(1, min(4, (os.cpu_count() or 4) // 2)))
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        emit({"ok": False, "error": f"cannot open video: {video}"})
        return 1
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 else None
    started = time.perf_counter()
    frames: list[dict[str, Any]] = []
    frame_paths: list[Path] = []
    try:
        for seconds in timestamps:
            capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
            ok, frame = capture.read()
            if not ok:
                frames.append({"requested_seconds": seconds, "error": "frame read failed"})
                continue
            filename = f"frame-{int(round(seconds * 1000)):010d}ms.png"
            path = output_dir / filename
            encoded_ok, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not encoded_ok:
                frames.append({"requested_seconds": seconds, "error": "frame encode failed"})
                continue
            try:
                # Python file I/O preserves Unicode paths on Windows.
                path.write_bytes(encoded.tobytes())
            except OSError as error:
                frames.append({"requested_seconds": seconds, "error": f"frame write failed: {error}"})
                continue
            actual_seconds = float(capture.get(cv2.CAP_PROP_POS_MSEC) or seconds * 1000.0) / 1000.0
            frames.append(
                {
                    "requested_seconds": seconds,
                    "actual_seconds": round(actual_seconds, 3),
                    "path": str(path),
                }
            )
            frame_paths.append(path)
    finally:
        capture.release()

    successful_times = [item["requested_seconds"] for item in frames if item.get("path")]
    sheet_path = absolute_path(args.contact_sheet) if args.contact_sheet else None
    if sheet_path and frame_paths:
        contact_sheet(frame_paths, successful_times, sheet_path)
    payload = {
        "schema_version": 1,
        "video": str(video),
        "fps": round(fps, 5),
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "frames": frames,
        "contact_sheet": str(sheet_path) if sheet_path and sheet_path.is_file() else None,
    }
    manifest = absolute_path(args.manifest) if args.manifest else output_dir / "frames.json"
    write_json_atomic(manifest, payload)
    emit(
        {
            "ok": all("error" not in item for item in frames),
            "manifest": str(manifest),
            "frames": len(frame_paths),
            "elapsed_seconds": payload["elapsed_seconds"],
        }
    )
    return 0 if len(frame_paths) == len(timestamps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
