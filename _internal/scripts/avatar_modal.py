"""Generate the app-owned voice portrait set on Modal; never runs torch on the client.

Run with the existing authenticated Modal CLI. Only catalog descriptions and original
fixtures go to this job. Character source excerpts must stay in private book projects.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import modal

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
REVISION = "462165984030d82259a11f4367a4eed129e94a7b"
PINS = ["torch==2.8.0", "diffusers==0.35.2", "transformers==4.57.1", "accelerate==1.11.0",
        "safetensors==0.6.2", "huggingface-hub==0.36.0", "Pillow==11.3.0", "numpy==2.2.6", "psutil==7.1.3"]
image = modal.Image.debian_slim(python_version="3.11").pip_install(*PINS)
cache = modal.Volume.from_name("abook-avatar-models", create_if_missing=True)
app = modal.App("abook-voice-avatars")


@app.function(image=image, gpu="L4", cpu=2, memory=16384, timeout=1800,
              max_containers=1, scaledown_window=30, volumes={"/models": cache})
def portraits(briefs: list[dict]):
    import io
    import os
    import psutil
    import torch
    from diffusers import StableDiffusionXLPipeline
    from PIL import Image
    if len(briefs) > 48:
        raise ValueError("At most 48 portraits per bounded job")
    started = time.perf_counter()
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, revision=REVISION, torch_dtype=torch.float16,
        variant="fp16", use_safetensors=True, cache_dir="/models", add_watermarker=False).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    torch.backends.cudnn.benchmark = False
    load_seconds = time.perf_counter() - started
    cache.commit()
    for brief in briefs:
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        result = pipe(prompt=brief["prompt"], negative_prompt="photo, photograph, realistic, text, letters, watermark, "
                      "signature, multiple people, collage, cropped head, disfigured",
                      width=768, height=768, num_inference_steps=24, guidance_scale=6.0,
                      generator=torch.Generator("cuda").manual_seed(brief["seed"])).images[0]
        out = io.BytesIO()
        result.resize((256, 256), Image.Resampling.LANCZOS).save(out, format="WEBP", quality=85, method=6)
        yield {**brief, "image": base64.b64encode(out.getvalue()).decode(),
               "seconds": time.perf_counter() - started, "loadSeconds": load_seconds,
               "peakVramBytes": torch.cuda.max_memory_allocated(),
               "rssBytes": psutil.Process(os.getpid()).memory_info().rss,
               "peakRssKiB": __import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss,
               "gpu": torch.cuda.get_device_name(), "model": MODEL, "revision": REVISION,
               "steps": 24, "guidance": 6.0, "resolution": 768, "pins": PINS}


@app.local_entrypoint()
def main(out: str, fixtures: bool = True, only: str = "", reroll: int = 0):
    """`only`: comma-separated portrait files to redo; `reroll` is added to their seed (recorded per result)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from abook.avatars import STYLE, hash32, voice_file
    from abook.voice_catalog import VIENEU_PRESETS, ENGINE_VOICES
    from abook.readaloud.edge import VOICES
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    briefs = []
    catalog = list(VIENEU_PRESETS) + list(ENGINE_VOICES) + [
        {"name": key, "label": label, "gender": gender, "description": "Adult, natural, clear"} for key, label, gender in VOICES]
    ages = {"Trẻ": "young adult", "Trung niên": "middle-aged adult", "Lớn tuổi": "elderly adult"}
    for voice in catalog:
        description = voice["description"]
        age = next((value for key, value in ages.items() if key in description), "adult")
        manner = "gentle warm expression" if "doc_truyen" == voice.get("style") else "calm clear expression"
        prompt = f"{STYLE} Vietnamese {age} {voice['gender']}, {manner}."
        briefs.append({"name": voice["name"], "description": description, "prompt": prompt,
                       "seed": hash32(voice["name"]), "file": voice_file(voice["name"])})
    if fixtures:
        for name, subject in [("fixture-minh", "Elderly Vietnamese man, short silver hair, round glasses, gentle smile"),
                              ("fixture-lan", "Young Vietnamese woman, long black hair, green eyes, blue scarf"),
                              ("fixture-tam", "Vietnamese teenage boy, short brown hair, freckles, red jacket")]:
            briefs.append({"name": name, "prompt": STYLE + " " + subject, "seed": hash32(name), "file": name + ".webp"})
    if only:
        wanted = set(only.split(","))
        briefs = [{**brief, "seed": (brief["seed"] + reroll) & 0xFFFFFFFF} for brief in briefs if brief["file"] in wanted]
    manifest = []
    started = time.perf_counter()
    for result in portraits.remote_gen(briefs):
        data = base64.b64decode(result.pop("image"))
        (target / result["file"]).write_bytes(data)
        result["sha256"] = __import__('hashlib').sha256(data).hexdigest()
        result["bytes"] = len(data)
        manifest.append(result)
        (target / "generation.json").write_text(json.dumps({"results": manifest, "wallSeconds": time.perf_counter() - started},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(manifest)}/{len(briefs)} {result['name']}: {result['seconds']:.2f}s, {len(data)} bytes", flush=True)
