"""Convert Standard MIDI Files to MTL source."""

import shlex
from bisect import bisect_right
from collections import defaultdict, deque
from fractions import Fraction

from .model import MTLError


_PITCHES = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")
_DRUMS = {
    35: "kick", 36: "kick", 37: "clap", 38: "snare", 39: "clap", 40: "snare",
    41: "tom", 42: "closed_hat", 43: "tom", 44: "closed_hat", 45: "tom",
    46: "open_hat", 47: "tom", 48: "tom", 49: "cymbal", 50: "tom",
    51: "ride", 52: "cymbal", 53: "ride", 54: "perc", 55: "cymbal",
    56: "perc", 57: "cymbal", 58: "perc", 59: "ride", 60: "perc",
    61: "perc", 62: "perc", 63: "perc", 64: "perc", 65: "perc",
    66: "perc", 67: "perc", 68: "perc", 69: "perc", 70: "perc",
    71: "perc", 72: "perc", 73: "perc", 74: "perc", 75: "perc",
    76: "perc", 77: "perc", 78: "perc", 79: "perc", 80: "perc",
    81: "perc",
}


def _read_vlq(data, offset, end):
    value = 0
    for _ in range(4):
        if offset >= end:
            raise MTLError("truncated MIDI variable-length quantity")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7f)
        if byte < 0x80:
            return value, offset
    raise MTLError("invalid MIDI variable-length quantity")


def _parse_track(data, offset, end):
    tick = 0
    running_status = None
    sequence = 0
    events = []
    while offset < end:
        delta, offset = _read_vlq(data, offset, end)
        tick += delta
        if offset >= end:
            raise MTLError("truncated MIDI event")
        status = data[offset]
        if status & 0x80:
            offset += 1
            if status < 0xf0:
                running_status = status
        elif running_status is not None:
            status = running_status
        else:
            raise MTLError("MIDI event has no running status")

        if status == 0xff:
            if offset + 2 > end:
                raise MTLError("truncated MIDI meta event")
            meta_type = data[offset]
            length, offset = _read_vlq(data, offset + 1, end)
            if offset + length > end:
                raise MTLError("truncated MIDI meta event data")
            payload = data[offset:offset + length]
            offset += length
            if meta_type == 0x51:
                if length != 3:
                    raise MTLError("invalid MIDI tempo event")
                tempo = int.from_bytes(payload, "big")
                if tempo == 0:
                    raise MTLError("MIDI tempo must be positive")
                events.append((tick, sequence, "tempo", tempo))
                sequence += 1
            elif meta_type == 0x58:
                if length < 2 or payload[1] > 4:
                    raise MTLError("unsupported MIDI time signature")
                events.append((tick, sequence, "meter", payload[0], 1 << payload[1]))
                sequence += 1
            continue

        if status in {0xf0, 0xf7}:
            length, offset = _read_vlq(data, offset, end)
            if offset + length > end:
                raise MTLError("truncated MIDI system-exclusive event")
            offset += length
            running_status = None
            continue
        if status >= 0xf0:
            raise MTLError(f"unsupported MIDI system status 0x{status:02x}")

        kind = status >> 4
        channel = status & 0x0f
        size = 1 if kind in {0xc, 0xd} else 2
        if offset + size > end or any(byte & 0x80 for byte in data[offset:offset + size]):
            raise MTLError("truncated or invalid MIDI channel event")
        values = data[offset:offset + size]
        offset += size
        if kind == 0xc:
            events.append((tick, sequence, "program", channel, values[0]))
        elif kind == 0x9 and values[1] > 0:
            events.append((tick, sequence, "on", channel, values[0], values[1]))
        elif kind == 0x8 or kind == 0x9:
            events.append((tick, sequence, "off", channel, values[0]))
        sequence += 1
    return events, tick


def _parse_file(data):
    if len(data) < 14 or data[:4] != b"MThd":
        raise MTLError("not a valid Standard MIDI File")
    header_length = int.from_bytes(data[4:8], "big")
    if header_length < 6 or 8 + header_length > len(data):
        raise MTLError("invalid MIDI header")
    file_format = int.from_bytes(data[8:10], "big")
    track_count = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if file_format not in {0, 1} or track_count == 0:
        raise MTLError("only MIDI format 0 and 1 files with at least one track are supported")
    if division & 0x8000 or division == 0:
        raise MTLError("SMPTE-timed MIDI files are not supported")

    offset = 8 + header_length
    tracks = []
    for _ in range(track_count):
        if offset + 8 > len(data) or data[offset:offset + 4] != b"MTrk":
            raise MTLError("missing or truncated MIDI track")
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        start = offset + 8
        end = start + length
        if end > len(data):
            raise MTLError("truncated MIDI track data")
        events, end_tick = _parse_track(data, start, end)
        tracks.append((events, end_tick))
        offset = end
    return division, tracks


def _tempo_clock(division, tracks):
    tempos = [(0, -1, -1, 500000)]
    meters = []
    for track_index, (events, _) in enumerate(tracks):
        for event in events:
            if event[2] == "tempo":
                tempos.append((event[0], track_index, event[1], event[3]))
            elif event[2] == "meter":
                meters.append((event[0], track_index, event[1], event[3], event[4]))
    tempos.sort()
    changes = {}
    for tick, _, _, tempo in tempos:
        changes[tick] = tempo

    ticks, seconds, active_tempos = [0], [Fraction(0)], []
    previous_tick, elapsed, tempo = 0, Fraction(0), changes[0]
    active_tempos.append(tempo)
    for tick in sorted(t for t in changes if t > 0):
        elapsed += Fraction((tick - previous_tick) * tempo, division * 1_000_000)
        ticks.append(tick)
        seconds.append(elapsed)
        tempo = changes[tick]
        active_tempos.append(tempo)
        previous_tick = tick

    def at(tick):
        index = bisect_right(ticks, tick) - 1
        return seconds[index] + Fraction((tick - ticks[index]) * active_tempos[index], division * 1_000_000)

    meters.sort()
    meter = (4, 4) if not meters else (meters[0][3], meters[0][4])
    return at, meter


def _fraction(value):
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _velocity(value):
    return f"{value / 127:.6f}".rstrip("0").rstrip(".")


def midi_to_mtl(data, title="MIDI import"):
    """Return MTL source for a Standard MIDI File, preserving its event timing."""
    division, tracks = _parse_file(data)
    clock, meter = _tempo_clock(division, tracks)
    from .parser import _gm_names, parse_song

    programs = _gm_names()
    note_groups = defaultdict(list)
    last_tick = max(end_tick for _, end_tick in tracks)
    for track_index, (events, end_tick) in enumerate(tracks):
        active_programs = defaultdict(int)
        active_notes = defaultdict(deque)
        for event in events:
            tick, _, kind, *values = event
            if kind == "program":
                channel, program = values
                active_programs[channel] = program
            elif kind == "on":
                channel, pitch, velocity = values
                key = (channel, pitch)
                active_notes[key].append((tick, velocity, active_programs[channel]))
            elif kind == "off":
                channel, pitch = values
                key = (channel, pitch)
                if active_notes[key]:
                    start, velocity, program = active_notes[key].popleft()
                    if start < tick:
                        note_groups[(track_index, channel, program)].append((start, tick, pitch, velocity))
        for (channel, pitch), pending in active_notes.items():
            while pending:
                start, velocity, program = pending.popleft()
                if start >= end_tick:
                    raise MTLError("MIDI note has no matching note-off")
                note_groups[(track_index, channel, program)].append((start, end_tick, pitch, velocity))

    length_beats = max(Fraction(1), clock(last_tick) * 2)
    lines = [
        f"song {shlex.quote(title)}",
        "bpm 120",
        f"time_signature {meter[0]}/{meter[1]}",
        f"length {_fraction(length_beats)} beats",
        "",
    ]
    for (track_index, channel, program), notes in sorted(note_groups.items()):
        track_name = f"midi_t{track_index + 1}_ch{channel + 1}_p{program}"
        pattern_name = f"{track_name}_notes"
        lines.extend((f"pattern {pattern_name}", f"    length {_fraction(length_beats)} beats"))
        for start, end, pitch, velocity in sorted(notes):
            beat = clock(start) * 2
            duration = (clock(end) - clock(start)) * 2
            if duration > 60:
                raise MTLError("MIDI note duration exceeds MTL's 60-second note limit")
            if channel == 9:
                note_name = _DRUMS.get(pitch, "perc")
            else:
                note_name = f"{_PITCHES[pitch % 12]}{pitch // 12 - 1}"
            lines.append(
                f"    {note_name} on {_fraction(beat + 1)} hold {_fraction(duration)} beats "
                f"vel {_velocity(velocity)}"
            )
        instrument = "drums" if channel == 9 else programs[program]
        lines.extend((f"track {track_name} instrument {instrument} pattern {pattern_name}", ""))
    result = "\n".join(lines).rstrip() + "\n"
    parse_song(result)
    return result
