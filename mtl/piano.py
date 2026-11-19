"""Original modal piano approximation: stiff strings and a nonlinear hammer spectrum.

This is a procedural voice, without recorded samples or commercial instrument assets.
"""
import numpy as np
from scipy import signal


def piano_voice(inst, freq, t, rate, rng, velocity, *, gate_seconds=None):
    # Normalize the stiff-string dispersion so the first partial stays in tune.
    stiffness = .00008 + .00035 * (freq / 440) ** 1.4
    brightness = 3.5 + 24 * velocity**1.5 * (.5 + inst.hammer)
    detuning = 2 ** (inst.string_detune / 1200) - 1
    strings = 1 if freq < 130 else 2 if freq < 260 else 3
    audio = np.zeros(len(t))
    for n in range(1, 97):
        partial = freq * n * np.sqrt((1 + stiffness * n * n) / (1 + stiffness))
        if partial * (1 + detuning) >= .45 * rate:
            break
        # Hammer strike position produces spectral notches. Harder strikes excite
        # upper modes, which lose energy faster than the low string modes.
        weight = (.4 + .6 * abs(np.sin(np.pi * n * .137))) * np.exp(-n / brightness) / n**1.15
        damping = .3 + .23 * (freq / 220)**.65 + .018 * n**1.45 * (freq / 220)**.3
        decay = .72 * np.exp(-t * damping) + .28 * np.exp(-t * (damping * 3 + 2))
        phase = 2 * np.pi * partial * t
        # Small strike-to-strike differences in string coupling avoid identical attacks.
        coupling = rng.uniform(.94, 1.06)
        if strings == 1:
            mode = np.sin(phase)
        elif strings == 2:
            mode = np.sin(phase) * np.cos(phase * detuning * coupling * .5)
        else:
            mode = np.sin(phase) * (1 + 2 * np.cos(phase * detuning * coupling)) / 3
        audio += mode * weight * decay
    # A brief, velocity-dependent felt/hammer noise excites damped body modes.
    noise = rng.normal(0, 1, len(t))
    noise = signal.sosfilt(signal.butter(1, [min(600, rate * .05), min(6500, rate * .4)],
                                          'bandpass', fs=rate, output='sos'), noise)
    audio += noise * (.005 + .055 * velocity**2) * np.exp(-t * (160 - 60 * inst.hammer))
    for resonance, gain in [(98, .6), (185, 1), (310, .7), (520, .4)]:
        if resonance < .45 * rate:
            audio += inst.soundboard * .045 * gain * np.sin(2 * np.pi * resonance * t) * np.exp(-t * (12 + resonance / 50))
    if gate_seconds is not None:
        released = np.maximum(t - gate_seconds, 0)
        audio += noise * .012 * (1 - inst.pedal) * np.exp(-released * 95) * (t >= gate_seconds)
    return audio * .95


def piano_image(audio, freq, rate, width):
    """Keyboard-position stereo plus weak early soundboard reflections."""
    pan = np.clip(np.log2(freq / 440) / 4, -1, 1) * width * .65
    stereo = np.column_stack([audio * np.sqrt((1 - pan) / 2), audio * np.sqrt((1 + pan) / 2)])
    for channel, milliseconds in [(0, 3.7), (1, 6.1)]:
        delay = round(rate * milliseconds / 1000)
        if 0 < delay < len(audio):
            stereo[delay:, channel] += audio[:-delay] * .09 * width
    return stereo
