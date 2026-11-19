#!/usr/bin/env python3
"""CodeRabbit generated HQ gallery renderer and measured loudness mastering.

Run from the installed repository: python audio_tests/render_hq.py
Requires FFmpeg with loudnorm; originals and first gallery are never overwritten.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave

import numpy as np

from mtl import parse_song, render_song

RATE = 48000
QUALITY = 5
TARGET_I = -14.0
TARGET_TP = -1.5
BASE = "highpass=f=28,lowpass=f=19000,acompressor=threshold=0.2:ratio=1.4:attack=20:release=180:makeup=1"
NORM = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11"
ROOT = Path(__file__).resolve().parent


def run_ffmpeg(source: Path, filters: str, output: Path | None = None) -> dict:
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-threads", "1",
               "-i", str(source), "-af", filters]
    if output is None:
        command += ["-f", "null", "-"]
    else:
        command += ["-ar", str(RATE), "-ac", "2", "-c:a", "pcm_s24le",
                    "-map_metadata", "-1", "-metadata", "comment=coderabbit-ai-generated:v1",
                    str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    blocks = re.findall(r'\{\s*"input_i".*?\}', result.stderr, flags=re.S)
    if not blocks:
        raise RuntimeError("FFmpeg did not return loudness measurements")
    return json.loads(blocks[-1])


def inspect(path: Path) -> dict:
    with wave.open(str(path), "rb") as stream:
        assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (RATE, 2, 3)
        frames = stream.getnframes()
        pcm = stream.readframes(frames)
    raw = np.frombuffer(pcm, np.uint8).reshape(-1, 3).astype(np.int32)
    signed = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
    signed = (signed ^ 0x800000) - 0x800000
    audio = signed.astype(np.float64).reshape(-1, 2) / 8388608
    assert frames > RATE * 10 and np.isfinite(audio).all()
    assert np.max(np.abs(audio)) < 1 and np.sqrt(np.mean(audio**2)) > .001
    # Verify the ending reaches silence rather than finishing on a sustained voice.
    assert np.max(np.abs(audio[-480:])) < .001
    assert not np.any(np.all(audio == 0, axis=0))
    loudness = run_ffmpeg(path, NORM + ":print_format=json")
    integrated = float(loudness["input_i"])
    true_peak = float(loudness["input_tp"])
    assert math.isfinite(integrated) and abs(integrated - TARGET_I) <= 1.0, loudness
    assert true_peak <= -1.0, loudness
    return {"frames": frames, "seconds": frames / RATE, "sample_rate": RATE,
            "channels": 2, "bit_depth": 24, "integrated_lufs": integrated,
            "true_peak_dbtp": true_peak, "loudness_range_lu": float(loudness["input_lra"]),
            "sample_peak_dbfs": float(20 * np.log10(np.max(np.abs(audio)))),
            "pcm_sha256": hashlib.sha256(pcm).hexdigest()}


def render_one(source_string: str) -> dict:
    source = Path(source_string)
    song = parse_song(source.read_text(), base_path=source.parent)
    song.sample_rate, song.bit_depth = RATE, 24
    output = source.with_suffix(".wav")
    print(f"Rendering {source.stem} at quality {QUALITY}", flush=True)
    with tempfile.TemporaryDirectory(prefix="mtl-hq-") as temporary:
        raw = Path(temporary) / "raw.wav"
        mastered = Path(temporary) / "master.wav"
        stats = render_song(song, raw, quality=QUALITY)
        first = run_ffmpeg(raw, BASE + "," + NORM + ":print_format=json")
        measured = (f":measured_I={first['input_i']}:measured_TP={first['input_tp']}"
                    f":measured_LRA={first['input_lra']}:measured_thresh={first['input_thresh']}"
                    f":offset={first['target_offset']}:linear=false:print_format=json")
        run_ffmpeg(raw, BASE + "," + NORM + measured, mastered)
        report = inspect(mastered)
        assert report["frames"] == stats["frames"], "Mastering changed the song duration"
        shutil.copyfile(mastered, output)
    report.update(file=output.name, source=source.name, title=song.title, bpm=song.bpm,
                  quality=QUALITY, events=stats["events"],
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    print(f"Complete {source.stem}: {report['integrated_lufs']} LUFS / {report['true_peak_dbtp']} dBTP", flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--only", choices=[p.stem for p in sorted(ROOT.glob("hq_[0-9]*.mtl"))])
    args = parser.parse_args()
    if shutil.which("ffmpeg") is None:
        parser.error("FFmpeg is required for measured loudness mastering")
    sources = sorted(ROOT.glob((args.only or "hq_[0-9]*") + ".mtl"))
    if not sources:
        parser.error("No HQ song sources found")
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        reports = list(pool.map(render_one, map(str, sources)))
    manifest_path = ROOT / "hq_manifest.json"
    # A single rerender updates its own entry and preserves other recorded results.
    previous = json.loads(manifest_path.read_text()).get("tracks", []) if manifest_path.exists() else []
    entries = {row["file"]: row for row in previous}
    entries.update({row["file"]: row for row in reports})
    manifest = {"provenance": "coderabbit-ai-generated:v1", "target_lufs": TARGET_I,
                "target_true_peak_dbtp": TARGET_TP, "quality": QUALITY,
                "mastering": BASE + "," + NORM + ":linear=false (two-pass measured)",
                "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
                "instrument_bank_sha256": hashlib.sha256((ROOT / "hq_instruments.mtl").read_bytes()).hexdigest(),
                "render_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "tracks": sorted(entries.values(), key=lambda row: row["file"])}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
