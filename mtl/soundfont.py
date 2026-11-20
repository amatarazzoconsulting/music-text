"""SoundFont 2 metadata inspection and FluidSynth-backed voice rendering."""

import ctypes
import ctypes.util
import struct
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

from .model import MTLError


def _chunks(data, start=12):
    view = memoryview(data)
    pos = start
    while pos + 8 <= len(view):
        tag = bytes(view[pos:pos + 4])
        size = struct.unpack_from("<I", view, pos + 4)[0]
        payload_start = pos + 8
        end = payload_start + size
        if end > len(view):
            raise MTLError("malformed SF2: chunk exceeds file size")
        yield tag, view[payload_start:end]
        pos = end + (size & 1)


def _metadata(data, path):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"sfbk":
        raise MTLError(f"invalid SF2: {path} is not a RIFF/sfbk SoundFont")
    presets = []
    sample_frames = 0
    for tag, payload in _chunks(data):
        if tag != b"LIST" or len(payload) < 4:
            continue
        list_type = bytes(payload[:4])
        for child_tag, child in _chunks(payload, 4):
            if list_type == b"sdta" and child_tag == b"smpl":
                sample_frames = len(child) // 2
            elif list_type == b"pdta" and child_tag == b"phdr":
                if len(child) % 38:
                    raise MTLError(f"malformed SF2: invalid preset table in {path}")
                for offset in range(0, len(child), 38):
                    record = child[offset:offset + 38]
                    name = bytes(record[:20]).split(b"\0", 1)[0].decode("latin-1", "replace").strip()
                    if name and name != "EOP":
                        preset, bank = struct.unpack_from("<HH", record, 20)
                        presets.append((name, bank, preset))
    if not presets:
        raise MTLError(f"invalid SF2: {path} has no preset data")
    return presets, sample_frames


def verify_soundfont(path):
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MTLError(f"cannot read SoundFont {path}: {exc}") from exc
    presets, sample_frames = _metadata(data, path)
    names = [name for name, _, _ in presets]
    return {"path": str(path.resolve()), "presets": names, "preset_count": len(names),
            "sample_frames": sample_frames, "bytes": len(data)}


@lru_cache(maxsize=8)
def _preset_table(path, modified_ns, size):
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise MTLError(f"cannot read SoundFont {path}: {exc}") from exc
    presets, _ = _metadata(data, path)
    return tuple(presets)


def _presets(path):
    path = Path(path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise MTLError(f"cannot read SoundFont {path}: {exc}") from exc
    return _preset_table(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _fluid_library():
    name = ctypes.util.find_library("fluidsynth")
    if not name:
        raise MTLError("SoundFont playback requires FluidSynth (install libfluidsynth)")
    try:
        library = ctypes.CDLL(name)
    except OSError as exc:
        raise MTLError(f"cannot load FluidSynth library {name}: {exc}") from exc

    def bind(symbol, result, *arguments):
        function = getattr(library, symbol)
        function.restype = result
        function.argtypes = arguments
        return function

    pointer = ctypes.c_void_p
    try:
        bind("new_fluid_settings", pointer)
        bind("delete_fluid_settings", None, pointer)
        bind("fluid_settings_setnum", ctypes.c_int, pointer, ctypes.c_char_p, ctypes.c_double)
        bind("fluid_settings_setint", ctypes.c_int, pointer, ctypes.c_char_p, ctypes.c_int)
        bind("new_fluid_synth", pointer, pointer)
        bind("delete_fluid_synth", None, pointer)
        bind("fluid_synth_sfload", ctypes.c_int, pointer, ctypes.c_char_p, ctypes.c_int)
        bind("fluid_synth_program_select", ctypes.c_int, pointer, ctypes.c_int, ctypes.c_int,
             ctypes.c_int, ctypes.c_int)
        bind("fluid_synth_all_sounds_off", ctypes.c_int, pointer, ctypes.c_int)
        bind("fluid_synth_noteon", ctypes.c_int, pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        bind("fluid_synth_noteoff", ctypes.c_int, pointer, ctypes.c_int, ctypes.c_int)
        bind("fluid_synth_write_float", ctypes.c_int, pointer, ctypes.c_int, pointer, ctypes.c_int,
             ctypes.c_int, pointer, ctypes.c_int, ctypes.c_int)
    except AttributeError as exc:
        raise MTLError(f"FluidSynth library {name} is missing a required API: {exc}") from exc
    return library


_DRUM_NOTES = {
    "kick": 36,
    "snare": 38,
    "clap": 39,
    "hihat": 42,
    "closed_hat": 42,
    "hat": 42,
    "tom": 45,
    "open_hat": 46,
    "cymbal": 49,
    "ride": 51,
    "perc": 54,
}


def _midi_note(pitch):
    if pitch in _DRUM_NOTES:
        return _DRUM_NOTES[pitch]
    accidental = pitch[1:2] in {"#", "b"}
    octave = int(pitch[2:] if accidental else pitch[1:])
    semitone = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[pitch[0].lower()]
    semitone += (1 if pitch[1] == "#" else -1) if accidental else 0
    return (octave + 1) * 12 + semitone


def _preset_coordinates(path, inst, drum_note):
    presets = _presets(path)
    if inst.sf2_preset:
        match = next((entry for entry in presets if entry[0].casefold() == inst.sf2_preset.casefold()), None)
        if match is None:
            raise MTLError(f"SF2 preset {inst.sf2_preset!r} not found in {path}")
        _, bank, program = match
        if drum_note and bank < 120:
            raise MTLError(f"SF2 preset {inst.sf2_preset!r} is melodic; select a percussion kit")
        return bank, program
    if drum_note:
        match = next((entry for entry in presets if entry[0].casefold() == "standard 1"), None)
        if match is None:
            match = next((entry for entry in presets if entry[1] >= 120), None)
        if match is None:
            raise MTLError(f"SoundFont {path} has no percussion preset")
        return match[1], match[2]
    return 0, inst.program or 0


class _FluidSynth:
    def __init__(self, path, rate):
        self.library = _fluid_library()
        self.settings = self.library.new_fluid_settings()
        if not self.settings:
            raise MTLError("FluidSynth could not create settings")
        self.synth = None
        self.lock = threading.RLock()
        settings = self.settings
        for key, value in ((b"synth.sample-rate", float(rate)), (b"synth.gain", 0.8)):
            if self.library.fluid_settings_setnum(settings, key, value) != 0:
                self.library.delete_fluid_settings(settings)
                self.settings = None
                raise MTLError(f"FluidSynth rejected setting {key.decode()}")
        for key, value in ((b"synth.reverb.active", 0), (b"synth.chorus.active", 0),
                           (b"synth.polyphony", 256)):
            if self.library.fluid_settings_setint(settings, key, value) != 0:
                self.library.delete_fluid_settings(settings)
                self.settings = None
                raise MTLError(f"FluidSynth rejected setting {key.decode()}")
        self.synth = self.library.new_fluid_synth(settings)
        if not self.synth:
            self.library.delete_fluid_settings(settings)
            self.settings = None
            raise MTLError("FluidSynth could not create a synthesizer")
        self.soundfont_id = self.library.fluid_synth_sfload(
            self.synth, str(path).encode("utf-8"), 1)
        if self.soundfont_id < 0:
            self.close()
            raise MTLError(f"FluidSynth could not load SoundFont {path}")

    def close(self):
        if self.synth:
            self.library.delete_fluid_synth(self.synth)
            self.synth = None
        if self.settings:
            self.library.delete_fluid_settings(self.settings)
            self.settings = None

    def _render(self, frames):
        left = np.zeros(frames, dtype=np.float32)
        right = np.zeros(frames, dtype=np.float32)
        if frames:
            result = self.library.fluid_synth_write_float(
                self.synth, frames,
                left.ctypes.data_as(ctypes.c_void_p), 0, 1,
                right.ctypes.data_as(ctypes.c_void_p), 0, 1)
            if result != 0:
                raise MTLError("FluidSynth failed while rendering audio")
        return np.column_stack((left, right))

    def voice(self, path, inst, pitch, gate_seconds, rate, velocity):
        is_drum_note = pitch in _DRUM_NOTES
        bank, program = _preset_coordinates(path, inst, is_drum_note)
        channel = 9 if is_drum_note or bank >= 120 else 0
        note = _midi_note(pitch)
        gate_frames = max(1, round(gate_seconds * rate))
        release_seconds = max(inst.release, 0.005)
        if channel == 9:
            release_seconds = max(release_seconds, 2.0 if note in {49, 51} else 0.8)
        tail_frames = max(1, round(release_seconds * rate))
        with self.lock:
            self.library.fluid_synth_all_sounds_off(self.synth, channel)
            if self.library.fluid_synth_program_select(
                    self.synth, channel, self.soundfont_id, bank, program) != 0:
                raise MTLError(f"FluidSynth could not select preset {inst.sf2_preset!r}")
            if velocity <= 0:
                return np.zeros((gate_frames + tail_frames, 2), dtype=np.float32)
            if self.library.fluid_synth_noteon(
                    self.synth, channel, note, min(127, max(1, round(velocity * 127)))) != 0:
                raise MTLError(f"FluidSynth could not start note {pitch}")
            audio = self._render(gate_frames)
            if self.library.fluid_synth_noteoff(self.synth, channel, note) != 0 and channel != 9:
                raise MTLError(f"FluidSynth could not release note {pitch}")
            return np.concatenate((audio, self._render(tail_frames)))


@lru_cache(maxsize=8)
def _synth(path, modified_ns, size, rate):
    return _FluidSynth(path, rate)


def soundfont_voice(inst, pitch, gate_seconds, rate, velocity):
    path = Path(inst.sf2_path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise MTLError(f"cannot read SoundFont {path}: {exc}") from exc
    synth = _synth(str(path.resolve()), stat.st_mtime_ns, stat.st_size, rate)
    return synth.voice(path, inst, pitch, gate_seconds, rate, velocity)
