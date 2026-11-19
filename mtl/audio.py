"""Validated PCM/float WAV decoding and polyphase sample-rate conversion."""
from functools import lru_cache
from math import gcd
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from .model import MTLError


@lru_cache(maxsize=4)
def _decode(path, size, modified):
    try:
        rate, data = wavfile.read(path)
    except (OSError, ValueError) as exc:
        raise MTLError(f'cannot read WAV {path}: {exc}') from exc
    if not 8000 <= rate <= 192000 or data.ndim not in {1, 2}:
        raise MTLError(f'unsupported WAV rate or dimensions: {path}')
    if data.ndim == 2 and data.shape[1] not in {1, 2}:
        raise MTLError(f'WAV must be mono or stereo: {path}')
    if not len(data) or len(data) > rate * 120:
        raise MTLError(f'WAV must contain audio and be at most 120 seconds: {path}')
    if data.dtype == np.uint8:
        audio = (data.astype(np.float64) - 128) / 128
    elif np.issubdtype(data.dtype, np.signedinteger):
        audio = data.astype(np.float64) / (2 ** (data.dtype.itemsize * 8 - 1))
    elif np.issubdtype(data.dtype, np.floating):
        audio = data.astype(np.float64)
    else:
        raise MTLError(f'unsupported WAV encoding: {path}')
    if not np.isfinite(audio).all():
        raise MTLError(f'non-finite samples in WAV: {path}')
    return rate, audio.reshape(len(audio), -1)


def read_audio(path, output_rate):
    path = Path(path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise MTLError(f'cannot read WAV {path}: {exc}') from exc
    if stat.st_size > 64 * 1024**2:
        raise MTLError(f'WAV exceeds 64 MiB input limit: {path}')
    rate, audio = _decode(str(path), stat.st_size, stat.st_mtime_ns)
    if rate != output_rate:
        divisor = gcd(rate, output_rate)
        audio = signal.resample_poly(audio, output_rate // divisor, rate // divisor, axis=0)
    return audio.copy()
