"""Convert Synth1 .sy1 text patches in nested zip banks to MTL instruments."""

import io
import re
import tempfile
import zipfile
from pathlib import Path

from .model import MTLError

_WAVES = {0: "sine", 1: "saw", 2: "square", 3: "triangle"}
_OSC2_WAVES = ("saw", "square", "triangle", "noise")
_MAX_PATCHES = 50000
_MAX_PATCH_BYTES = 65536
_MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
DEFAULT_SYNTH1_LIMIT = 2000


def _cutoff_parameter(value):
    return 20 * (20000 / 20) ** (value / 127)


def _patch_parameters(data, source_name):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    parameters = {}
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or "=" in line:
            continue
        if "," not in line:
            continue
        fields = line.split(",")
        if line_number == 1 and not parameters:
            try:
                tuple(int(field.strip()) for field in fields)
            except ValueError:
                continue
        if len(fields) != 2:
            raise MTLError(f"{source_name}:{line_number}: expected parameter,value")
        try:
            index, value = (int(field.strip()) for field in fields)
        except ValueError as exc:
            if line_number == 1 and not parameters:
                continue
            raise MTLError(f"{source_name}:{line_number}: invalid numeric parameter") from exc
        if not 0 <= index <= 255 or not -(2**31) <= value < 2**32:
            raise MTLError(f"{source_name}:{line_number}: parameter is outside its supported range")
        if index in parameters:
            if parameters[index] != value:
                raise MTLError(f"{source_name}:{line_number}: conflicting parameter {index}")
            continue
        parameters[index] = value
    if not parameters:
        raise MTLError(f"{source_name}: no Synth1 parameters found")
    return parameters


def _instrument_text(name, parameters):
    wave = _WAVES.get(parameters.get(0, 1), "saw")
    osc2_wave = _OSC2_WAVES[min(3, parameters.get(76, 0) * 4 // 128)]
    osc2_level = parameters.get(3, 0) / 127
    unison = min(8, max(1, round(1 + parameters.get(44, 0) * 7 / 127)))
    detune = parameters.get(45, 0) / 1270
    cutoff = _cutoff_parameter(parameters.get(16, 110))
    resonance = 0.1 + parameters.get(17, 8) * 9.9 / 127
    filter_type = "highpass" if parameters.get(13, 0) >= 64 else "lowpass"
    saturation = parameters.get(18, 0) * 8 / 127
    lines = [
        f"instrument {name}",
        f"    oscillator {wave} unison {unison} detune {detune:.5f}",
        f"    filter {filter_type} cutoff {cutoff:.1f}hz resonance {resonance:.3f}",
    ]
    if osc2_level > 0:
        lines.append(f"    oscillator2 {osc2_wave} level {osc2_level:.4f} detune {detune:.5f}")
    if saturation > 0:
        lines.append(f"    distortion {saturation:.3f}")
    if parameters.get(26, 0):
        delay_time = 0.01 + parameters.get(27, 24) * 1.49 / 127
        feedback = parameters.get(29, 0) * 0.85 / 127
        mix = parameters.get(30, 0) / 127
        if mix > 0:
            lines.append(f"    delay time {delay_time:.4f}s feedback {feedback:.4f} mix {mix:.4f}")
    if parameters.get(31, 0):
        rate = 0.1 + parameters.get(34, 32) * 4.9 / 127
        depth = 0.0002 + parameters.get(33, 24) * 0.0098 / 127
        mix = parameters.get(35, 40) / 127
        if mix > 0:
            lines.append(f"    chorus rate {rate:.3f}hz depth {depth:.5f} mix {mix:.4f}")
    return "\n".join(lines)


def _block_features(block):
    waveform = re.search(r"^\s+oscillator (sine|saw|square|triangle|noise)\b", block, re.M)
    oscillator2 = re.search(r"^\s+oscillator2 (sine|saw|square|triangle|noise)\b", block, re.M)
    cutoff = re.search(r"^\s+filter (lowpass|highpass) cutoff ([\d.]+)hz", block, re.M)
    unison = re.search(r"^\s+oscillator \w+ unison (\d+)", block, re.M)
    if not waveform or not cutoff:
        raise MTLError("Synth1 preset is missing its oscillator or filter definition")
    return {
        "waveform": waveform.group(1),
        "oscillator2": oscillator2.group(1) if oscillator2 else "",
        "filter_type": cutoff.group(1),
        "cutoff": float(cutoff.group(2)),
        "unison": int(unison.group(1)) if unison else 1,
        "distortion": bool(re.search(r"^\s+distortion ", block, re.M)),
        "delay": bool(re.search(r"^\s+delay ", block, re.M)),
        "chorus": bool(re.search(r"^\s+chorus ", block, re.M)),
    }


def _bucket(features):
    cutoff = features["cutoff"]
    cutoff_band = 0 if cutoff < 250 else 1 if cutoff < 1000 else 2 if cutoff < 4000 else 3
    unison = features["unison"]
    unison_band = 0 if unison == 1 else 1 if unison < 5 else 2
    return (
        features["waveform"], features["filter_type"], bool(features["oscillator2"]),
        cutoff_band, unison_band, features["distortion"], features["delay"],
        features["chorus"],
    )


def _creative_name(features, ordinal):
    textures = {
        "sine": "glass", "saw": "ember", "square": "amber",
        "triangle": "velvet", "noise": "grain",
    }
    cutoff = features["cutoff"]
    color = ("subsonic" if cutoff < 250 else "smoky" if cutoff < 1000
             else "warm" if cutoff < 4000 else "luminous")
    if features["filter_type"] == "highpass":
        color = "hollow"
    if features["distortion"]:
        color = "driven"
    elif features["delay"] and features["chorus"]:
        color = "shimmering"
    elif features["oscillator2"]:
        color = "braided"
    use = (
        "sub" if cutoff < 180 else
        "bass" if cutoff < 700 else
        "texture" if features["waveform"] == "noise" or features["filter_type"] == "highpass" else
        "pad" if features["chorus"] and cutoff < 5000 else
        "lead" if cutoff >= 4000 else "keys"
    )
    return f"{textures[features['waveform']]}_{color}_{use}_{ordinal:04d}"


def _extract_blocks(text):
    blocks, current = [], []
    for raw in text.splitlines():
        if raw.startswith("instrument "):
            if current:
                blocks.append("\n".join(current))
            current = [raw]
        elif raw.lstrip().startswith("//"):
            continue
        elif current:
            if raw.strip():
                current.append(raw)
        elif raw.strip():
            raise MTLError("Synth1 bank contains content outside instrument definitions")
    if current:
        blocks.append("\n".join(current))
    if not blocks:
        raise MTLError("no Synth1 instrument definitions found")
    if len(blocks) > _MAX_PATCHES:
        raise MTLError("Synth1 bank exceeds the 50,000 patch limit")
    return blocks


def _write_bank(blocks, destination, limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_PATCHES:
        raise MTLError(f"Synth1 preset limit must be from 1 to {_MAX_PATCHES}")
    buckets = {}
    for block in blocks:
        features = _block_features(block)
        buckets.setdefault(_bucket(features), []).append((block, features))
    selected = []
    keys = sorted(buckets)
    for offset in range(max(map(len, buckets.values()))):
        for key in keys:
            if offset < len(buckets[key]):
                selected.append(buckets[key][offset])
                if len(selected) == limit:
                    break
        if len(selected) == limit:
            break
    if not selected:
        raise MTLError("no Synth1 presets selected")
    rewritten = []
    for ordinal, (block, features) in enumerate(selected, 1):
        lines = block.splitlines()
        lines[0] = f"instrument {_creative_name(features, ordinal)}"
        rewritten.append("\n".join(lines))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=destination.parent,
                prefix=".synth1-", suffix=".mtl", delete=False) as output:
            temporary = Path(output.name)
            output.write("\n\n".join(rewritten))
            output.write("\n")
        temporary.replace(destination)
    except OSError as exc:
        raise MTLError(f"cannot write curated Synth1 bank {destination}: {exc}") from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return len(rewritten)


def curate_synth1_bank(source, destination, limit=DEFAULT_SYNTH1_LIMIT):
    """Keep a diverse, deterministically named subset of a converted MTL bank."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    try:
        blocks = _extract_blocks(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise MTLError(f"cannot read Synth1 bank {source}: {exc}") from exc
    return _write_bank(blocks, destination, limit)


def _walk_archive(archive, prefix, depth, budget):
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = f"{prefix}/{info.filename}" if prefix else info.filename
        if info.file_size < 0 or budget[0] + info.file_size > _MAX_UNCOMPRESSED_BYTES:
            raise MTLError("Synth1 archive exceeds the 128 MiB uncompressed size limit")
        budget[0] += info.file_size
        if info.filename.lower().endswith(".sy1"):
            if info.file_size > _MAX_PATCH_BYTES:
                raise MTLError(f"{name}: patch exceeds the 64 KiB size limit")
            yield name, archive.read(info)
        elif info.filename.lower().endswith(".zip") and depth < 4:
            if info.file_size > _MAX_UNCOMPRESSED_BYTES:
                raise MTLError(f"{name}: nested archive exceeds the size limit")
            payload = archive.read(info)
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                    yield from _walk_archive(nested, name, depth + 1, budget)
            except zipfile.BadZipFile as exc:
                raise MTLError(f"{name}: invalid nested zip archive") from exc


def convert_synth1_archive(source, destination, limit=DEFAULT_SYNTH1_LIMIT):
    """Write a diverse, creatively named subset of nested .sy1 patches as an MTL bank."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise MTLError("output must not overwrite the Synth1 archive")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_PATCHES:
        raise MTLError(f"Synth1 preset limit must be from 1 to {_MAX_PATCHES}")
    try:
        outer = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise MTLError(f"cannot read Synth1 zip archive {source}: {exc}") from exc
    try:
        patches = []
        budget = [0]
        with outer:
            for source_name, data in _walk_archive(outer, "", 0, budget):
                if len(patches) >= _MAX_PATCHES:
                    raise MTLError("Synth1 archive exceeds the 50,000 patch limit")
                parameters = _patch_parameters(data, source_name)
                patches.append(_instrument_text(f"source_patch_{len(patches) + 1}", parameters))
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise MTLError(f"cannot read Synth1 archive {source}: {exc}") from exc
    if not patches:
        raise MTLError(f"{source}: no .sy1 patches found")
    return _write_bank(patches, destination, limit)
