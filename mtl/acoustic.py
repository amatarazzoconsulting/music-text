"""Expressive additive acoustic approximations and drawbar organ voices."""
import numpy as np
from scipy import signal


def acoustic_voice(inst, freq, t, rate, rng, velocity):
    audio = np.zeros(len(t))
    # Integrate vibrato analytically; delayed onset mimics settling breath/bow.
    vibrato = inst.vibrato_depth * (1 - np.exp(-t * 5))
    phase = 2 * np.pi * freq * t - freq * vibrato / inst.vibrato_rate * np.cos(2 * np.pi * inst.vibrato_rate * t)
    if inst.engine == 'organ':
        ratios = [0.5, 1.5, 1, 2, 3, 4, 5, 6, 8]
        weights = [(10 ** (v * 3 / 20) - 1) / (10 ** (24 / 20) - 1) for v in inst.drawbars]
        for ratio, weight in zip(ratios, weights):
            if freq * ratio < rate * .45:
                audio += weight * np.sin(phase * ratio)
        audio /= max(1, sum(weights) ** .5)
        if freq * 3 < rate * .45:
            audio += inst.percussion * np.sin(phase * 3) * np.exp(-t * 12)
        audio += .025 * rng.uniform(-1, 1, len(t)) * np.exp(-t * 220)
        audio *= 1 - .12 * np.sin(2 * np.pi * inst.rotary * t)
        return audio * .7
    if inst.engine == 'vibes':
        for ratio, gain, damping in [(1, 1, .7), (4, .2, 2.0), (9.2, .06, 5.0)]:
            if freq * ratio < rate * .45:
                audio += gain * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t * damping)
        audio *= .82 + .18 * np.sin(2 * np.pi * inst.vibrato_rate * t)
        return audio * .75
    harmonic_limit = min(48, int(rate * .45 / (freq * (1 + inst.vibrato_depth))))
    for n in range(1, harmonic_limit + 1):
        if inst.engine == 'trumpet':
            # Dynamic spectral tilt: tongued onset and harder notes open the spectrum.
            brightness = 3 + velocity * 12 * (1 - np.exp(-t * 35))
            weight = np.exp(-n / brightness) / n**.5
            formant = 1 + .8 * np.exp(-((n * freq - 1500) / 900)**2)
        else:
            weight = 1 / n**1.25
            formant = .65 + .6 * np.exp(-((n * freq - 500) / 280)**2) + .5 * np.exp(-((n * freq - 2600) / 1100)**2)
        audio += weight * formant * np.sin(phase * n)
    noise = rng.uniform(-1, 1, len(t))
    noise = signal.sosfilt(signal.butter(1, 1500, 'highpass', fs=rate, output='sos'), noise)
    audio += noise * (.025 if inst.engine == 'trumpet' else .045) * (1 - np.exp(-t * 30))
    return audio * (.38 if inst.engine == 'trumpet' else .5)
