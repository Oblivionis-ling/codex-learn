#!/usr/bin/env python3
"""Batch-transcribe media with one reusable faster-whisper model instance."""

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
    select_asr_backend,
    write_json_atomic,
)


def serialize_word(word: Any) -> dict[str, Any]:
    return {
        "start": round(float(word.start), 3),
        "end": round(float(word.end), 3),
        "word": word.word,
        "probability": round(float(word.probability), 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="audio or video files; one model load is reused for all")
    parser.add_argument("--output", required=True, help="combined UTF-8 transcript JSON")
    parser.add_argument("--language", help="ISO language code; omit for automatic detection")
    parser.add_argument("--initial-prompt")
    parser.add_argument("--word-timestamps", action="store_true")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--beam-size", type=int, default=5)
    args = parser.parse_args()

    paths = [absolute_path(value) for value in args.inputs]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        emit({"ok": False, "error": "input files not found", "missing": missing})
        return 1

    config, _, model_root = configured_paths()
    configure_process_environment(config, model_root)
    backend = select_asr_backend(config)
    if args.batch_size:
        backend["batch_size"] = args.batch_size

    from faster_whisper import BatchedInferencePipeline, WhisperModel

    model_name = str(config.get("asr_model", "large-v3"))
    started = time.perf_counter()
    model = WhisperModel(
        model_name,
        device=backend["device"],
        compute_type=backend["compute_type"],
        cpu_threads=backend["cpu_threads"],
        num_workers=1,
        download_root=str(model_root / "faster-whisper"),
        local_files_only=True,
    )
    pipeline = BatchedInferencePipeline(model=model)
    model_load_seconds = time.perf_counter() - started

    files: list[dict[str, Any]] = []
    for path in paths:
        file_started = time.perf_counter()
        segments_iter, info = pipeline.transcribe(
            str(path),
            language=args.language,
            beam_size=args.beam_size,
            best_of=args.beam_size,
            initial_prompt=args.initial_prompt,
            word_timestamps=args.word_timestamps,
            without_timestamps=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            batch_size=backend["batch_size"],
        )
        segments: list[dict[str, Any]] = []
        for index, segment in enumerate(segments_iter, 1):
            item: dict[str, Any] = {
                "id": f"transcript-{index:04d}",
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": segment.text.strip(),
                "avg_logprob": round(float(segment.avg_logprob), 5),
                "no_speech_prob": round(float(segment.no_speech_prob), 5),
            }
            if args.word_timestamps and segment.words:
                item["words"] = [serialize_word(word) for word in segment.words]
            segments.append(item)
        files.append(
            {
                "path": str(path),
                "language": info.language,
                "language_probability": round(float(info.language_probability), 5),
                "duration_seconds": round(float(info.duration), 3),
                "elapsed_seconds": round(time.perf_counter() - file_started, 3),
                "segments": segments,
            }
        )

    payload = {
        "schema_version": 1,
        "model": model_name,
        "backend": backend,
        "model_load_seconds": round(model_load_seconds, 3),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "files": files,
    }
    output = absolute_path(args.output)
    write_json_atomic(output, payload)
    emit(
        {
            "ok": True,
            "output": str(output),
            "files": len(files),
            "segments": sum(len(item["segments"]) for item in files),
            "elapsed_seconds": payload["elapsed_seconds"],
            "backend": backend,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
