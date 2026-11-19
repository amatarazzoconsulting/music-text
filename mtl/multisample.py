"""Stereo multi-velocity WAV playback with seeded round robin and sustain loops."""
import json
import math
from pathlib import Path
from fractions import Fraction
from functools import lru_cache

import numpy as np
from scipy import signal

from .audio import read_audio
from .model import MTLError


@lru_cache(maxsize=8)
def _map(path, size, modified):
    from .parser import _pitch_valid, NOTE
    from .dsp import frequency
    try:
        if size > 2 * 1024 * 1024:
            raise ValueError('sample map exceeds 2 MiB')
        entries = json.loads(Path(path).read_text(encoding='utf-8'))['zones']
        if not isinstance(entries, list) or not 1 <= len(entries) <= 2048:
            raise ValueError('zones must be a list of 1..2048 zones')
        seen = set()
        for zone in entries:
            for name in ('root', 'low', 'high'):
                _pitch_valid(zone[name])
                if not NOTE.fullmatch(zone[name]):
                    raise ValueError('sample zone pitches must be melodic notes')
            if frequency(zone['low']) > frequency(zone['high']):
                raise ValueError('sample zone low exceeds high')
            velocity = float(zone['velocity'])
            if not math.isfinite(velocity) or not 0 <= velocity <= 1:
                raise ValueError('zone velocity must be 0..1')
            if not isinstance(zone['files'], list) or not 1 <= len(zone['files']) <= 32 or not all(isinstance(p, str) and p for p in zone['files']):
                raise ValueError('zone files must contain 1..32 WAV paths')
            loop = zone.get('loop')
            if loop is not None and (len(loop) != 2 or not all(math.isfinite(float(x)) for x in loop) or not 0 <= loop[0] < loop[1]):
                raise ValueError('loop must be [start_seconds, end_seconds]')
            identity = (zone['root'], zone['low'], zone['high'], velocity)
            if identity in seen:
                raise ValueError('duplicate velocity layer for root/range')
            seen.add(identity)
        return entries
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise MTLError(f'invalid sample map {path}: {exc}') from exc


def multisample_voice(inst, pitch, count, rate, rng, velocity):
    from .dsp import frequency
    path = Path(inst.sample_map)
    try:
        stat = path.stat()
    except OSError as exc:
        raise MTLError(f'cannot read sample map {path}: {exc}') from exc
    if stat.st_size > 2 * 1024 * 1024:
        raise MTLError('sample map exceeds 2 MiB')
    entries = _map(str(path), stat.st_size, stat.st_mtime_ns)
    freq = frequency(pitch)
    eligible = [z for z in entries if frequency(z['low']) <= freq <= frequency(z['high'])]
    if not eligible:
        raise MTLError(f'no sample zone covers {pitch}')
    root = min(eligible, key=lambda z: abs(math.log2(frequency(z['root']) / freq)))['root']
    layers = sorted((z for z in eligible if z['root'] == root), key=lambda z: float(z['velocity']))
    velocities = [float(z['velocity']) for z in layers]
    upper = min(len(layers) - 1, int(np.searchsorted(velocities, velocity)))
    lower = max(0, upper - 1) if velocity < velocities[upper] else upper
    mix = (velocity - velocities[lower]) / (velocities[upper] - velocities[lower]) if upper != lower else 0
    result = np.zeros((count, 2))
    for layer, gain in [(layers[lower], 1 - mix), (layers[upper], mix)]:
        if not gain:
            continue
        filename = layer['files'][int(rng.integers(len(layer['files'])))]
        audio = read_audio(path.parent / filename, rate)
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        ratio = Fraction(frequency(layer['root']) / freq).limit_denominator(4096)
        # Resample only enough source for this voice; preserve stereo.
        needed = math.ceil(count * ratio.denominator / ratio.numerator) + 64
        if layer.get('loop'):
            if round(float(layer['loop'][1]) * rate) > len(audio):
                raise MTLError(f'sustain loop exceeds source in {filename}')
            needed = max(needed, round(float(layer['loop'][1]) * rate) + 64)
        audio = signal.resample_poly(audio[:needed], ratio.numerator, ratio.denominator, axis=0)
        loop = layer.get('loop')
        if loop:
            start, end = [round(float(x) * rate * ratio.numerator / ratio.denominator) for x in loop]
            if not 0 <= start < end <= len(audio) or end - start < 4:
                raise MTLError(f'invalid or too short sustain loop in {filename}')
            fade = min(round(.01 * rate), (end - start) // 4)
            # Overlap-add loop boundaries; the first pass and every repeat blend.
            segment = audio[start:end]
            output = np.zeros((max(count, end), 2))
            output[:end] = audio[:end]
            cursor = end - fade
            while cursor < count:
                size = min(len(segment), count - cursor)
                overlap = min(fade, size)
                blend = np.linspace(0, 1, overlap)[:, None]
                output[cursor:cursor + overlap] = output[cursor:cursor + overlap] * (1 - blend) + segment[:overlap] * blend
                output[cursor + overlap:cursor + size] = segment[overlap:size]
                cursor += len(segment) - fade
            audio = output[:count]
        result[:min(count, len(audio))] += audio[:count] * gain
    return result
