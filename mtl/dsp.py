"""Offline synthesis primitives. Buffers are floating point until final export."""

import math
from fractions import Fraction

import numpy as np
from scipy import signal

from .model import Instrument
from .audio import read_audio
from .acoustic import acoustic_voice
from .piano import piano_voice


def frequency(pitch):
    accidental = pitch[1:2] in {'#', 'b'}
    octave = int(pitch[2:] if accidental else pitch[1:])
    semitone = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[pitch[0].lower()]
    semitone += (1 if pitch[1] == '#' else -1) if accidental else 0
    return 440.0 * 2 ** (((octave + 1) * 12 + semitone - 69) / 12)


def _blep(phase, step):
    """Polynomial correction of a waveform discontinuity over two samples."""
    result = np.zeros_like(phase)
    left = phase < step
    x = phase[left] / step
    result[left] = 2 * x - x * x - 1
    right = phase > 1 - step
    x = (phase[right] - 1) / step
    result[right] = x * x + 2 * x + 1
    return result


def oscillator(waveform, freq, count, rate, phase_offset=0.0):
    if freq >= rate / 2:
        return np.zeros(count)
    step = freq / rate
    phase = (np.arange(count) * step + phase_offset) % 1
    if waveform == "sine":
        return np.sin(2 * np.pi * phase)
    if waveform == "saw":
        return 2 * phase - 1 - _blep(phase, step)
    if waveform == "square":
        return np.where(phase < 0.5, 1.0, -1.0) + _blep(phase, step) - _blep((phase + 0.5) % 1, step)
    # A finite odd-harmonic triangle has no partial at or above Nyquist.
    result = np.zeros(count)
    for harmonic in range(1, min(64, math.ceil(rate / (2 * freq))), 2):
        result += (-1) ** ((harmonic - 1) // 2) * np.sin(2 * np.pi * phase * harmonic) / harmonic**2
    return result * (8 / np.pi**2)


def envelope(count, gate_samples, inst, rate):
    """Release begins at the current ADS level, including very short notes."""
    t = np.arange(count) / rate
    attack = max(inst.attack, 0.001)
    decay = max(inst.decay, 1 / rate)
    level = np.where(t < attack, t / attack,
                     inst.sustain + (1 - inst.sustain) * np.exp(-5 * np.maximum(t - attack, 0) / decay))
    gate = min(gate_samples, count - 1)
    release_count = count - gate
    if release_count > 0:
        level[gate:] = level[gate] * np.linspace(1, 0, release_count) ** 2
    return level


def _coefficients(cutoff, rate, inst):
    # RBJ low/high-pass biquad; Q is bounded by the parser.
    omega = 2 * np.pi * cutoff / rate
    cosine = np.cos(omega)
    alpha = np.sin(omega) / (2 * inst.resonance)
    if inst.filter_type == "lowpass":
        b = np.array([(1 - cosine) / 2, 1 - cosine, (1 - cosine) / 2])
    else:
        b = np.array([(1 + cosine) / 2, -(1 + cosine), (1 + cosine) / 2])
    a = np.array([1 + alpha, -2 * cosine, 1 - alpha])
    return b / a[0], a / a[0]


def _filter(audio, rate, inst, *, start_sample=0, cutoff_curve=None):
    limit = rate * 0.45
    if cutoff_curve is None and not inst.lfo_depth:
        b, a = _coefficients(min(inst.cutoff, rate * 0.45), rate, inst)
        return signal.sosfilt(np.r_[b, a][None, :], audio)

    # Update at 1 kHz. Reconstruct transposed filter state from input/output
    # history when coefficients change, so a sweep does not reset the filter.
    output = np.empty_like(audio)
    step = max(1, round(rate / 1000))
    x1 = x2 = y1 = y2 = 0.0
    for offset in range(0, len(audio), step):
        segment = audio[offset:offset + step]
        time = (start_sample + offset + len(segment) / 2) / rate
        cutoff = cutoff_curve(time) if cutoff_curve is not None else inst.cutoff
        cutoff += inst.lfo_depth * math.sin(2 * math.pi * inst.lfo_rate * time)
        b, a = _coefficients(np.clip(cutoff, 20, limit), rate, inst)
        state = [b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2,
                 b[2] * x1 - a[2] * y1]
        result, _ = signal.lfilter(b, a, segment, zi=state)
        output[offset:offset + len(segment)] = result
        if len(segment) > 1:
            x2, y2 = segment[-2], result[-2]
        else:
            x2, y2 = x1, y1
        x1, y1 = segment[-1], result[-1]
    return output


def _drum(inst, rate, rng):
    name = inst.name
    if name in {"hat", "closed_hat"}:
        name = "hihat"
    durations = {"kick": 0.75, "snare": 0.4, "clap": 0.3, "hihat": 0.12,
                 "open_hat": 0.6, "tom": 0.55, "cymbal": 1.5, "ride": 1.2, "perc": 0.25}
    duration = min(3.0, durations.get(name, 0.5) * max(0.5, inst.decay / 0.12))
    t = np.arange(round(duration * rate)) / rate
    noise = rng.uniform(-1, 1, len(t))
    if name in {"kick", "tom"}:
        low, high, tau = (48, 155, 0.028) if name == "kick" else (110, 230, 0.025)
        # Integrate f(t) analytically; f(t)*t gives the wrong instantaneous pitch.
        phase = 2 * np.pi * (low * t + (high - low) * tau * (1 - np.exp(-t / tau)))
        audio = np.sin(phase) * np.exp(-t * (8 if name == "kick" else 12))
        audio += 0.12 * noise * np.exp(-t * 450)
    elif name in {"snare", "clap"}:
        high = signal.sosfilt(signal.butter(2, 1200, 'highpass', fs=rate, output='sos'), noise)
        audio = 0.75 * high * np.exp(-t * 22)
        if name == "snare":
            audio += 0.35 * np.sin(2 * np.pi * 185 * t) * np.exp(-t * 35)
        else:
            audio *= 1 + 0.5 * np.sin(2 * np.pi * 95 * t) * np.exp(-t * 80)
    else:
        high = signal.sosfilt(signal.butter(3, min(6500, rate * 0.35), 'highpass', fs=rate, output='sos'), noise)
        audio = high * np.exp(-t * (55 if name == "hihat" else 7))
    return audio * np.minimum(t / 0.0008, 1)


def synthesize(inst: Instrument, pitch: str, gate_seconds: float, rate: int, quality: int, rng,
               *, start_sample=0, cutoff_curve=None, velocity=0.8):
    """Render one mono voice with release and bounded ambience tails."""
    factor = 1 if quality <= 2 else 2 if quality <= 4 else 4
    internal_rate = rate * factor
    if inst.engine == "drum":
        audio = _drum(inst, internal_rate, rng)
    else:
        release = max(inst.release, 0.005, inst.pedal * 2 if inst.engine in {'piano', 'multisampler'} else 0)
        count = max(2, round((gate_seconds + release) * internal_rate))
        gate = min(round(gate_seconds * internal_rate), count - 1)
        freq = frequency(pitch)
        t = np.arange(count) / internal_rate
        audio = np.zeros(count)
        if inst.engine == 'multisampler':
            from .multisample import multisample_voice
            audio = multisample_voice(inst, pitch, count, internal_rate, rng, velocity)
            audio *= envelope(count, gate, inst, internal_rate)[:, None]
            audio[-min(count, round(.005 * internal_rate)):] *= np.linspace(1, 0, min(count, round(.005 * internal_rate)))[:, None]
            audio = process_audio(audio, inst, internal_rate, 1, rng, start_sample=start_sample * factor, cutoff_curve=cutoff_curve)
            if factor > 1:
                audio = signal.resample_poly(audio, 1, factor, axis=0)
            return np.asarray(audio * .35, dtype=np.float32)
        if inst.engine == 'piano':
            audio = piano_voice(inst, freq, t, internal_rate, rng, velocity, gate_seconds=gate_seconds)
        elif inst.engine in {'trumpet', 'violin', 'vibes', 'organ'}:
            audio = acoustic_voice(inst, freq, t, internal_rate, rng, velocity)
        elif inst.engine == 'sampler':
            sample = read_audio(inst.sample_path, internal_rate).mean(axis=1)
            ratio = Fraction(frequency(inst.root_pitch) / freq).limit_denominator(4096)
            sample = sample[:math.ceil(count * ratio.denominator / ratio.numerator) + 64]
            sample = signal.resample_poly(sample, ratio.numerator, ratio.denominator)
            audio[:min(count, len(sample))] = sample[:count]
        elif inst.engine in {"pluck", "bell"}:
            ratios = range(1, 25) if inst.engine == "pluck" else [1, 2.756, 5.404, 8.933, 13.34, 18.64]
            for i, ratio in enumerate(ratios, 1):
                if freq * ratio >= internal_rate * 0.45:
                    continue
                damping = 1.5 + ratio * (0.45 if inst.engine == 'pluck' else 0.12)
                audio += np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t * damping) / i**1.4
            audio *= 0.65
        elif inst.engine == "fm":
            index = max(0, min(2.0, (internal_rate * 0.4 / freq - 1) / 2))
            audio = np.sin(2 * np.pi * freq * t + index * np.exp(-t * 3) * np.sin(4 * np.pi * freq * t))
        elif inst.waveform == "noise":
            audio = rng.uniform(-1, 1, count)
        else:
            offsets = np.linspace(-1, 1, inst.unison) if inst.unison > 1 else [0]
            for i, offset in enumerate(offsets):
                audio += oscillator(inst.waveform, freq * (1 + offset * inst.detune), count, internal_rate, i * 0.137)
            audio /= inst.unison
        audio *= envelope(count, gate, inst, internal_rate)
    audio = _filter(audio, internal_rate, inst, start_sample=start_sample * factor,
                    cutoff_curve=cutoff_curve)
    if inst.drive:
        audio = np.tanh(audio * (1 + inst.drive)) / np.tanh(1 + inst.drive)
    # Every voice ends at zero, including resonant filters and drum tails.
    fade = min(len(audio), max(2, round(0.005 * internal_rate)))
    audio[-fade:] *= np.linspace(1, 0, fade)
    if factor > 1:
        audio = signal.resample_poly(audio, 1, factor)
    audio = ambience(audio, inst, rate, rng)
    return np.asarray(audio * 0.35, dtype=np.float32)



def ambience(audio, inst, rate, rng):
    if inst.delay:
        step = max(1, round(inst.delay_time * rate))
        # Finite echo train, truncated below -60 dB or after 3 seconds.
        repeats = min(int(3 * rate / step), 64)
        dry = audio
        audio = np.pad(dry * (1 - inst.delay), (0, repeats * step))
        for i in range(1, repeats + 1):
            gain = inst.delay * inst.feedback ** (i - 1)
            if gain < 0.001:
                break
            audio[i * step:i * step + len(dry)] += dry * gain
    if inst.reverb:
        # Deterministic, diffuse FIR room response; no unstable feedback network.
        count = round(inst.reverb_seconds * rate)
        t = np.arange(count) / rate
        impulse = rng.normal(0, 1, count) * np.exp(-t * (8 / inst.reverb_seconds))
        impulse[:round(0.015 * rate)] = 0  # predelay
        impulse = signal.sosfilt(signal.butter(1, min(6000, rate * 0.4), fs=rate, output='sos'), impulse)
        impulse /= max(np.sqrt(np.sum(impulse**2)), 1e-12)
        wet = signal.fftconvolve(audio, impulse)
        audio = np.pad(audio * (1 - inst.reverb), (0, len(wet) - len(audio))) + wet * inst.reverb * 0.4
    return audio


def process_audio(audio, inst, rate, quality, rng, *, start_sample=0, cutoff_curve=None):
    """Apply a track insert chain to mono/stereo WAV audio, preserving channels."""
    channels = []
    factor = 1 if quality <= 2 else 2 if quality <= 4 else 4
    for channel in audio.T:
        if factor > 1:
            channel = signal.resample_poly(channel, factor, 1)
        channel = _filter(channel, rate * factor, inst, start_sample=start_sample * factor, cutoff_curve=cutoff_curve)
        if inst.drive:
            channel = np.tanh(channel * (1 + inst.drive)) / np.tanh(1 + inst.drive)
        if factor > 1:
            channel = signal.resample_poly(channel, 1, factor)
        channels.append(ambience(channel, inst, rate, rng))
    return np.column_stack(channels)
