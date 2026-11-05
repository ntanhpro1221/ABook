"""CPU scoring helper for the optional Studio runtime (no downloads, no Ollama)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def main(source: Path, target: Path) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    import soundfile

    from . import voice_pick

    request = json.loads(source.read_text(encoding="utf-8"))
    takes = {}
    for engine, clips in request.items():
        takes[engine] = []
        for clip in clips:
            wave, rate = soundfile.read(clip["file"], dtype="float32")
            takes[engine].append((clip["text"], wave, rate))
    results: dict[str, dict] = {engine: {} for engine in takes}
    similarity = voice_pick.default_similarity()
    asr = voice_pick._score(voice_pick.default_asr() if similarity else None, takes, results, "cer",
                            lambda judge, clips: voice_pick.engine_pick.score_clarity(clips, judge, similarity))
    natural = voice_pick._score(voice_pick.utmos_judge(), takes, results, "natural",
                                lambda judge, clips: voice_pick.engine_pick.score_naturalness(clips, judge))
    target.write_text(json.dumps({"engines": results, "asr": asr, "natural": natural}), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
