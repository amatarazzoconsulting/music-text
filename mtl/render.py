"""Compile rational beat positions, mix to disk, and atomically export PCM WAV."""

import math
import os
import tempfile
import wave
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

import numpy as np

from .dsp import frequency, synthesize, process_audio
from .audio import read_audio
from .model import MTLError, Instrument
from .parser import DRUMS, _preset


@dataclass(frozen=True)
class Event:
    sample: int
    gate_seconds: float
    track: str
    pitch: str
    velocity: float
    seed: int
    note_index: int = 0


def sample_at(beat, song):
    # Round the absolute rational position once; never add rounded beat lengths.
    return round(beat * 60 * song.sample_rate / Fraction(str(song.bpm)))


def _transpose_pitch(pitch, semitones):
    midi = round(69 + 12 * math.log2(frequency(pitch) / 440)) + semitones
    if not 0 <= midi <= 127:
        raise MTLError(f"arpeggiator transposition takes {pitch} outside MIDI pitch range")
    names = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")
    return f"{names[midi % 12]}{midi // 12 - 1}"


def _arpeggio_pitches(track, pitches, rng):
    arp = track.arpeggiator
    ordered = sorted(pitches, key=frequency)
    expanded = tuple(_transpose_pitch(pitch, 12 * octave)
                     for octave in range(arp.octaves) for pitch in ordered)
    if arp.pattern:
        if any(step > len(expanded) for step in arp.pattern):
            raise MTLError(f"track {track.name!r}: arpeggiator pattern selects a step outside its chord")
        return tuple(None if step == 0 else expanded[step - 1] for step in arp.pattern)
    if arp.mode == "random":
        order = rng.permutation(len(expanded)).tolist()
    elif arp.mode == "down":
        order = list(reversed(range(len(expanded))))
    elif arp.mode == "up_down":
        ascending = list(range(len(expanded)))
        order = ascending + list(range(len(expanded) - 2, 0, -1))
    else:
        order = list(range(len(expanded)))
    return tuple(expanded[index] for index in order)


def compile_timeline(song):
    """Restart patterns and release held notes at each section boundary."""
    regions = []
    position = Fraction(0)
    active = set() if song.sections and song.sections[0].actions else set(song.tracks)
    for section in song.sections:
        for action, name in section.actions:
            selected = set(song.tracks) if name == 'all' else {name}
            if action == 'only':
                active = selected
            elif action == 'add':
                active |= selected
            else:
                active -= selected
        end = min(position + section.length, song.length)
        if end > position:
            regions.append((position, end, sorted(active)))
        position = end
        if position >= song.length:
            break
    if position < song.length:
        regions.append((position, song.length, sorted(active)))
    rng = np.random.default_rng(song.seed)
    events = []
    for start, end, tracks in regions:
        for name in tracks:
            if song.tracks[name].clips:
                continue
            pattern = song.patterns[song.tracks[name].pattern]
            if math.ceil((end - start) / pattern.length) > 1000000:
                raise MTLError("section exceeds one million pattern repeats")
            repeat = start
            while repeat < end:
                for note_index, note in enumerate(pattern.notes):
                    beat = repeat + note.beat
                    # Swing delays the second eighth of each quarter-note pair.
                    if note.beat % 1 == Fraction(1, 2):
                        beat += Fraction(str(pattern.swing / 100 - 0.5))
                    if beat >= end:
                        continue
                    arp = song.tracks[name].arpeggiator
                    if arp and note.pitches[0] not in DRUMS:
                        step_count = math.ceil(note.duration / arp.step)
                        if step_count > 100000:
                            raise MTLError(f"track {name!r}: arpeggiator note exceeds 100000 steps")
                        step_order = _arpeggio_pitches(song.tracks[name], note.pitches, rng)
                        note_end_beat = beat + note.duration
                        for step_index in range(step_count):
                            pitch = step_order[step_index % len(step_order)]
                            if pitch is None:
                                continue
                            onset_beat = beat + arp.step * step_index
                            if onset_beat >= end or onset_beat >= note_end_beat:
                                continue
                            onset = sample_at(onset_beat, song)
                            if song.timing_ms:
                                onset += round(rng.uniform(-song.timing_ms, song.timing_ms) * song.sample_rate / 1000)
                            onset = max(sample_at(start, song), min(onset, sample_at(end, song) - 1))
                            gate = min(float(arp.step) * arp.gate * 60 / song.bpm,
                                       float(note_end_beat - onset_beat) * 60 / song.bpm,
                                       (sample_at(end, song) - onset) / song.sample_rate)
                            velocity = np.clip(note.velocity + rng.uniform(-song.velocity_variation, song.velocity_variation), 0, 1)
                            events.append(Event(onset, gate, name, pitch, float(velocity),
                                                int(rng.integers(2**32)), note_index))
                            if len(events) > 1000000:
                                raise MTLError("song exceeds one million scheduled notes; shorten the song or patterns")
                        continue
                    onset = sample_at(beat, song)
                    if song.timing_ms:
                        onset += round(rng.uniform(-song.timing_ms, song.timing_ms) * song.sample_rate / 1000)
                    onset = max(sample_at(start, song), min(onset, sample_at(end, song) - 1))
                    gate = min(float(note.duration * 60 / Fraction(str(song.bpm))),
                               (sample_at(end, song) - onset) / song.sample_rate)
                    velocity = np.clip(note.velocity + rng.uniform(-song.velocity_variation, song.velocity_variation), 0, 1)
                    for pitch in note.pitches:
                        events.append(Event(onset, gate, name, pitch, float(velocity), int(rng.integers(2**32)), note_index))
                        if len(events) > 1000000:
                            raise MTLError("song exceeds one million scheduled notes; shorten the song or patterns")
                repeat += pattern.length
    return sorted(events, key=lambda event: event.sample)


def _pcm(audio, bits, rng):
    scale = 2 ** (bits - 1)
    # TPDF dither at one LSB; keep digital silence silent.
    noise = rng.random(audio.shape) - rng.random(audio.shape)
    noise *= audio != 0
    values = np.clip(np.rint(audio * scale + noise), -scale, scale - 1).astype('<i4')
    if bits == 16:
        return values.astype('<i2').tobytes()
    unsigned = values.astype('<u4').reshape(-1)
    return np.column_stack([unsigned & 255, (unsigned >> 8) & 255, (unsigned >> 16) & 255]).astype('u1').tobytes()


def _automation_curves(song):
    """Compile section-relative ramps into absolute sample times."""
    sections = {}
    beat = Fraction(0)
    for section in song.sections:
        sections[section.name] = (beat, beat + section.length)
        beat += section.length
    curves = {}
    for automation in song.automation:
        start, end = sections[automation.section]
        values = (sample_at(start, song) / song.sample_rate,
                  sample_at(start + automation.duration, song) / song.sample_rate,
                  sample_at(end, song) / song.sample_rate,
                  automation.start, automation.end)
        if values[1] <= values[0]:
            raise MTLError(f"automation for {automation.track!r} is shorter than one sample")
        curves.setdefault((automation.track, automation.parameter), []).append(values)
    return curves


def _control_value(times, default, curves):
    """A ramp applies throughout its section, holding the final value after it."""
    values = np.full(np.shape(times), default, dtype=float)
    for start, finish, end, first, last in curves:
        ramp = first + (last - first) * np.clip((np.asarray(times) - start) / (finish - start), 0, 1)
        values = np.where((np.asarray(times) >= start) & (np.asarray(times) < end), ramp, values)
    return values


def _clip_events(song, notes=None):
    sections = {}
    beat = Fraction(0)
    for section in song.sections:
        sections[section.name] = beat
        beat += section.length
    events = []
    for track in song.tracks.values():
        for clip in track.clips:
            position = clip.offset + (sections[clip.section] if clip.section else 0)
            sample = sample_at(position, song)
            if clip.reference_track:
                anchor = next((e for e in (notes or []) if e.track == clip.reference_track and e.note_index == clip.reference_note), None)
                if anchor is None:
                    raise MTLError(f'audio on track {track.name!r}: referenced note is never scheduled')
                sample = anchor.sample + round(float(clip.reference_fraction) * anchor.gate_seconds * song.sample_rate) + sample_at(clip.reference_delay, song)
                if sample < 0:
                    raise MTLError(f'audio on track {track.name!r}: reference starts before the song')
            if sample >= sample_at(song.length, song):
                raise MTLError(f'audio clip on {track.name!r} starts beyond song length')
            events.append((sample, track, clip))
    return sorted(events, key=lambda item: item[0])


def _mix_voice(mix, voice, onset, track, velocity, song, curves):
    if voice.ndim == 1:
        voice = voice[:, None]
    if voice.shape[1] == 1:
        gains = np.array([math.cos((track.pan + 1) * math.pi / 4),
                          math.sin((track.pan + 1) * math.pi / 4)]) * velocity
    else:
        # Stereo balance preserves the original stereo image at center.
        gains = np.array([min(1, 1 - track.pan), min(1, 1 + track.pan)]) * velocity
    count = min(len(voice), len(mix) - onset)
    ramps = curves.get((track.name, 'volume'), ())
    for offset in range(0, count, 65536):
        size = min(65536, count - offset)
        if ramps:
            times = (onset + offset + np.arange(size)) / song.sample_rate
            volume = 10 ** (_control_value(times, track.volume, ramps) / 20)
        else:
            volume = np.full(size, 10 ** (track.volume / 20))
        mix[onset + offset:onset + offset + size] += voice[offset:offset + size] * volume[:, None] * gains


def _synthesize_layers(inst, song, pitch, gate_seconds, quality, seed, start_sample,
                       velocity, cutoff_curve, depth=0):
    if not inst.layers:
        return synthesize(inst, pitch, gate_seconds, song.sample_rate, quality,
                          np.random.default_rng(seed), start_sample=start_sample,
                          cutoff_curve=cutoff_curve, velocity=velocity)
    if depth >= 16:
        raise MTLError(f"instrument {inst.name!r}: layer nesting exceeds 16")
    voices = [_synthesize_layers(song.instruments[name], song, pitch, gate_seconds, quality,
                                seed + index + 1, start_sample, velocity, cutoff_curve, depth + 1)
              for index, name in enumerate(inst.layers)]
    length = max(map(len, voices))
    weights = inst.layer_balance or tuple(1.0 for _ in voices)
    norm = math.sqrt(sum(weight * weight for weight in weights))
    mixed = np.zeros(length, dtype=float)
    for voice, weight in zip(voices, weights):
        mixed[:len(voice)] += voice * (weight / norm)
    processed = process_audio(mixed[:, None], inst, song.sample_rate, quality,
                              np.random.default_rng(seed), start_sample=start_sample,
                              cutoff_curve=cutoff_curve)
    return processed[:, 0]


def render_song(song, output=None, *, quality=3):
    """Render to stereo 16/24-bit WAV; return output statistics.

    The mix is a disk-backed float32 array. Memory scales with the longest voice,
    rather than the song. The explicit song length includes releases/effect tails.
    """
    if quality not in {1, 2, 3, 4, 5}:
        raise MTLError("quality must be from 1 to 5")
    destination = Path(output or song.output)
    if destination.suffix.lower() != '.wav':
        raise MTLError("only .wav output is supported")
    frames = sample_at(song.length, song)
    if frames < 1:
        raise MTLError("song duration is less than one sample")
    if frames * 2 * (song.bit_depth // 8) > 2**32 - 128:
        raise MTLError("song exceeds the 4 GiB RIFF WAV limit")
    events = compile_timeline(song)
    curves = _automation_curves(song)
    clips = _clip_events(song, events)
    sources = ([clip.path for _, _, clip in clips]
               + [inst.sample_path for inst in song.instruments.values() if inst.sample_path]
               + [inst.sf2_path for inst in song.instruments.values() if inst.sf2_path])
    for inst in song.instruments.values():
        if inst.engine == 'multisampler':
            from .multisample import _map
            map_path = Path(inst.sample_map)
            try:
                stat = map_path.stat()
                zones = _map(str(map_path), stat.st_size, stat.st_mtime_ns)
            except OSError as exc:
                raise MTLError(f'cannot read sample map {map_path}: {exc}') from exc
            sources.append(str(map_path))
            sources.extend(str(map_path.parent / f) for zone in zones for f in zone['files'])
        if inst.engine == 'soundfont':
            from .soundfont import verify_soundfont
            info = verify_soundfont(inst.sf2_path)
            if inst.sf2_preset and inst.sf2_preset not in info['presets']:
                raise MTLError(f"SF2 preset {inst.sf2_preset!r} not found in {inst.sf2_path}")
    if any(destination.resolve() == Path(source).resolve() for source in sources):
        raise MTLError("output must not overwrite an input WAV")
    # Prevent unexpectedly large single-note allocations (including oversampling).
    for event in events:
        track = song.tracks[event.track]
        if (event.pitch not in DRUMS and track.instrument != "drums"
                and song.instruments[track.instrument].engine != "drum"
                and frequency(event.pitch) >= song.sample_rate / 2):
            raise MTLError(f"note {event.pitch} is at or above Nyquist; select a higher sample rate")
    if any(event.gate_seconds > 60 for event in events):
        raise MTLError("a note exceeds 60 seconds; use shorter tied/repeated notes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    block = 65536
    peak = 0.0
    with tempfile.TemporaryDirectory(prefix='mtl-') as scratch:
        mix = np.memmap(Path(scratch) / 'mix.f32', mode='w+', dtype='float32', shape=(frames, 2))
        try:
            for index, (onset, track, clip) in enumerate(clips):
                audio = read_audio(clip.path, song.sample_rate)
                fx = track.effects or Instrument('__audio', cutoff=96000)
                cutoff_ramps = curves.get((track.name, 'filter.cutoff'), ())
                cutoff_curve = (lambda t: float(_control_value(t, fx.cutoff, cutoff_ramps))) if cutoff_ramps else None
                if track.effects or cutoff_ramps:
                    audio = process_audio(audio, fx, song.sample_rate, quality,
                                          np.random.default_rng(song.seed + index),
                                          start_sample=onset, cutoff_curve=cutoff_curve)
                fade = min(len(audio) // 2, round(song.sample_rate * .003))
                if fade:
                    audio[:fade] *= np.linspace(0, 1, fade)[:, None]
                    audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
                _mix_voice(mix, audio, onset, track, 1, song, curves)
            for event in events:
                track = song.tracks[event.track]
                inst = (song.instruments[event.pitch] if event.pitch in song.instruments else _preset(event.pitch)) if track.instrument == 'drums' else song.instruments[track.instrument]
                # A named drum instrument triggered by notes uses a standard kick model.
                if inst.engine == 'drum' and inst.name not in DRUMS:
                    inst = replace(inst, name='kick')
                cutoff_ramps = curves.get((event.track, 'filter.cutoff'), ())
                cutoff_curve = (lambda t: float(_control_value(t, inst.cutoff, cutoff_ramps))) if cutoff_ramps else None
                if inst.layers:
                    voice = _synthesize_layers(inst, song, event.pitch, event.gate_seconds,
                                               quality, event.seed, event.sample, event.velocity,
                                               cutoff_curve)
                else:
                    voice = synthesize(inst, event.pitch, event.gate_seconds, song.sample_rate, quality,
                                       np.random.default_rng(event.seed), start_sample=event.sample,
                                       cutoff_curve=cutoff_curve, velocity=event.velocity)
                if inst.engine == 'piano':
                    from .piano import piano_image
                    voice = piano_image(voice, frequency(event.pitch), song.sample_rate, inst.stereo_width)
                if track.effects:
                    voice = process_audio(voice[:, None] if voice.ndim == 1 else voice, track.effects, song.sample_rate, quality,
                                          np.random.default_rng(event.seed), start_sample=event.sample)
                _mix_voice(mix, voice, event.sample, track, event.velocity, song, curves)
            # Boundary fades avoid an abrupt song cut while preserving exact length.
            fade = min(round(song.sample_rate * 0.005), frames // 2)
            if fade:
                mix[:fade] *= np.linspace(0, 1, fade)[:, None]
                mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
            for offset in range(0, frames, block):
                part = mix[offset:offset + block]
                if not np.isfinite(part).all():
                    raise MTLError("non-finite audio encountered during mixing")
                peak = max(peak, float(np.max(np.abs(part))))
            gain = min(1.0, 10 ** (song.peak_db / 20) / peak) if peak else 1.0
            # Replace the destination only after a complete valid WAV has been written.
            handle, temporary = tempfile.mkstemp(prefix='.mtl-', suffix='.wav', dir=destination.parent)
            os.close(handle)
            try:
                with wave.open(temporary, 'wb') as wav:
                    wav.setnchannels(2)
                    wav.setsampwidth(song.bit_depth // 8)
                    wav.setframerate(song.sample_rate)
                    rng = np.random.default_rng(song.seed)
                    for offset in range(0, frames, block):
                        wav.writeframesraw(_pcm(mix[offset:offset + block].astype('float64') * gain, song.bit_depth, rng))
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        finally:
            mix.flush()
            del mix
    return {"path": str(destination), "frames": frames, "sample_rate": song.sample_rate,
            "seconds": frames / song.sample_rate, "events": len(events), "clips": len(clips), "peak": peak * gain}
