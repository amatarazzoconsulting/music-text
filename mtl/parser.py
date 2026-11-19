"""Line-oriented MTL parser with conservative, deterministic entry conveniences."""

import math
import re
import shlex
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import lru_cache
from difflib import SequenceMatcher
from pathlib import Path

from .friendly import normalize, normalize_note, numeric_tokens, default_octave, PROPERTIES
from .model import AudioClip, Automation, Instrument, MTLError, Note, Pattern, Section, Song, Track

DRUMS = {"kick", "snare", "hihat", "closed_hat", "open_hat", "hat", "clap", "tom", "ride", "cymbal", "perc"}
NOTE = re.compile(r"[a-gA-G][#b]?-?\d\Z")


@dataclass
class Line:
    number: int
    tokens: list[str]
    indent: int
    children: list['Line'] = field(default_factory=list)
    base_path: Path = Path('.')
    filename: str = ''

    def error(self, message):
        prefix = f"{self.filename}:" if self.filename else ""
        return MTLError(f"{prefix}line {self.number}: {message}")


def _lines(source):
    root = Line(0, [], -1)
    stack = [root]
    for number, raw in enumerate(source.splitlines(), 1):
        # Strip // comments only outside strings. '#' belongs to note names.
        quoted = escaped = False
        end = len(raw)
        for i, char in enumerate(raw):
            if char == '"' and not escaped:
                quoted = not quoted
            if raw[i:i + 2] == "//" and not quoted:
                end = i
                break
            escaped = char == "\\" and not escaped
        raw = raw[:end].expandtabs(4).rstrip()
        if not raw.strip():
            continue
        try:
            tokens = shlex.split(raw, comments=False)
        except ValueError as exc:
            raise MTLError(f"line {number}: {exc}") from exc
        line = Line(number, tokens, len(raw) - len(raw.lstrip()))
        while line.indent <= stack[-1].indent:
            stack.pop()
        stack[-1].children.append(line)
        stack.append(line)
    return root.children


def _load_lines(source, base_path, filename='', stack=(), loaded=None):
    """Expand definition-only imports once; retain each declaration's origin."""
    loaded = set() if loaded is None else loaded
    if len(stack) > 32:
        raise MTLError('instrument import nesting exceeds 32 files')
    result = []
    def annotate(line):
        line.base_path, line.filename = base_path, filename
        for child in line.children:
            annotate(child)
    for line in _lines(source):
        annotate(line)
        t = line.tokens
        if t[0] == 'import':
            if line.children or not (len(t) == 2 or len(t) == 3 and t[1] == 'bank'):
                raise line.error('expected import "file.mtl" or import bank "file.mtl"')
            path = (base_path / t[-1]).resolve()
            if len(t) == 3 and t[1] == 'bank' and t[-1] in {'general_midi', 'acoustic', 'organs', 'electronic'}:
                path = Path(__file__).parent / 'presets' / (t[-1] + '.mtl')
                path = path.resolve()
            if path in stack:
                raise line.error(f'cyclic import: {path}')
            if path in loaded:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError) as exc:
                raise line.error(f'cannot import {path}: {exc}') from exc
            imported = _load_lines(text, path.parent, str(path), (*stack, path), loaded)
            if any(x.tokens[0] != 'instrument' for x in imported):
                raise line.error('imported banks may contain only instruments and imports')
            loaded.add(path)
            result.extend(imported)
        else:
            result.append(line)
    return result


def number(value, minimum, maximum):
    result = float(Fraction(value))
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"expected a number from {minimum} to {maximum}, got {value!r}")
    return result


def quantity(value, unit, minimum, maximum):
    if not value.lower().endswith(unit):
        raise ValueError(f"expected {unit} units, got {value!r}")
    return number(value[:-len(unit)], minimum, maximum)


def seconds(value):
    if value.endswith("ms"):
        return quantity(value, "ms", 0, 30000) / 1000
    return quantity(value, "s", 0, 30)


def duration(tokens, song, default="beats"):
    tokens = numeric_tokens(tokens, decimal_comma=True)
    if len(tokens) == 1 and re.fullmatch(r'\d+:\d{2}(?:\.\d+)?', tokens[0]):
        minutes, secs = tokens[0].split(':')
        if Fraction(secs) >= 60:
            raise ValueError('clock seconds must be less than 60')
        tokens = [str(60 * Fraction(minutes) + Fraction(secs)), 'seconds']
    if len(tokens) == 1:
        match = re.fullmatch(r'([\d./]+)(bars?|beats?|seconds?|minutes?|ms|s)', tokens[0])
        if match:
            tokens = list(match.groups())
    if not 1 <= len(tokens) <= 2:
        raise ValueError("expected a duration such as '4 bars' or 'two and a half beats'")
    amount = Fraction(tokens[0])
    if amount <= 0:
        raise ValueError("duration must be positive")
    unit = (tokens[1].lower() if tokens[1].lower() in {'s', 'ms'} else tokens[1].lower().rstrip('s')) if len(tokens) == 2 else default
    scales = {"bar": song.beats_per_bar, "beat": 1, "beats": 1,
              "second": Fraction(str(song.bpm)) / 60,
              "minute": Fraction(str(song.bpm)), "s": Fraction(str(song.bpm)) / 60,
              "m": Fraction(str(song.bpm)), "ms": Fraction(str(song.bpm)) / 60000}
    if unit not in scales:
        raise ValueError(f"unknown duration unit {unit!r}")
    return amount * scales[unit]


def _preset(name, *, gm=True):
    inst = Instrument(name)
    if name in DRUMS:
        inst.engine = "drum"
        inst.release = 0.0
    elif name == "bass":
        inst.waveform, inst.cutoff = "saw", 700
    elif name == "lead":
        inst.waveform, inst.cutoff = "saw", 5000
    elif name == "pad":
        inst.waveform, inst.attack, inst.release = "triangle", 0.4, 1.0
    elif name == "piano":
        inst.engine, inst.attack, inst.decay, inst.sustain, inst.release = "piano", .001, .04, 1, .35
        inst.reverb, inst.cutoff = .06, 14000
        inst.program = 0
    elif name in {"guitar", "pluck"}:
        inst.engine, inst.sustain, inst.release = "pluck", 0.2, 0.3
    elif name == "bell":
        inst.engine, inst.release = "bell", 1.5
    elif name not in {"sine", "synth"}:
        matched = _gm_name(name) if gm else None
        if matched:
            return replace(_gm_bank()[matched], name=name)
        raise ValueError(f"unknown instrument {name!r}; define it with 'instrument {name}'")
    return inst


_DESCRIPTORS = set("deep punchy sharp click tight bright metal shell short closed open warm smooth dark soft gentle aggressive gritty distorted clean pristine long rounded electronic bass synth lead pad airy and with a slightly very kick snare hihat".split())


def _describe(inst, tokens):
    words = {token.strip(",.") for token in tokens}
    if not words or words - _DESCRIPTORS:
        raise ValueError("unsupported sound description; use warm, bright, dark, deep, punchy, soft, short, long, or distorted")
    if words & {"warm", "dark", "deep"}:
        inst.cutoff = 900 if "warm" in words else 500
    if words & {"bright", "airy", "sharp"}:
        inst.cutoff = 10000
    if words & {"soft", "gentle", "smooth"}:
        inst.attack = 0.03
    if "short" in words:
        inst.decay, inst.release = 0.06, 0.05
    if "long" in words:
        inst.decay, inst.release = 0.5, 0.6
    if "punchy" in words:
        inst.attack, inst.decay = 0.001, 0.25
    if words & {"distorted", "gritty", "aggressive"}:
        inst.drive = 2.0


def _instrument_property(inst, tokens, song):
    key, *args = tokens
    if key == "type" and len(args) == 1:
        aliases = {"wavetable": "synth", "virtual_analog": "synth"}
        engine = aliases.get(args[0], args[0])
        if engine not in {"synth", "piano", "pluck", "bell", "fm", "drum", "trumpet", "violin", "vibes", "organ", "sampler", "multisampler"}:
            raise ValueError("supported types: piano, synth, wavetable, virtual_analog, pluck, bell, fm, drum, trumpet, violin, vibes, organ, sampler, multisampler")
        inst.engine = engine
    elif key in {'hammer', 'soundboard', 'string_detune', 'pedal', 'stereo_width'} and len(args) == 1:
        setattr(inst, key, number(args[0], 0, 10 if key == 'string_detune' else 1))
    elif key == 'program' and len(args) == 1:
        inst.program = int(args[0])
        if not 0 <= inst.program <= 127:
            raise ValueError('GM program must be 0..127')
    elif key == 'drawbars' and len(args) == 9:
        inst.drawbars = tuple(number(v, 0, 8) for v in args)
    elif key in {'rotary', 'percussion'} and len(args) == 1:
        setattr(inst, key, number(args[0], 0, 10 if key == 'rotary' else 1))
    elif key == 'vibrato' and len(args) == 4 and args[::2] == ['rate', 'depth']:
        inst.vibrato_rate = quantity(args[1], 'hz', 0.1, 12)
        inst.vibrato_depth = number(args[3], 0, 0.02)
    elif key == 'root' and len(args) == 1:
        _pitch_valid(args[0])
        if args[0] in DRUMS:
            raise ValueError('sample root must be a pitched note')
        inst.root_pitch = args[0]
    elif key == "oscillator" and args:
        if args[0] not in {"sine", "saw", "square", "triangle", "noise"}:
            raise ValueError("unknown oscillator waveform")
        inst.waveform = args.pop(0)
        while args:
            parameter = args.pop(0)
            value = args.pop(0)
            if parameter == "unison":
                inst.unison = int(number(value, 1, 8))
                if str(inst.unison) != value:
                    raise ValueError("unison must be an integer")
            elif parameter == "detune":
                inst.detune = number(value, 0, 0.1)
            else:
                raise ValueError(f"unknown oscillator parameter {parameter!r}")
    elif key == "envelope" and args and len(args) % 2 == 0:
        for parameter, value in zip(args[::2], args[1::2]):
            if parameter in {"attack", "decay", "release"}:
                setattr(inst, parameter, seconds(value))
            elif parameter == "sustain":
                inst.sustain = number(value, 0, 1)
            else:
                raise ValueError(f"unknown envelope parameter {parameter!r}")
    elif key == "filter" and len(args) in {3, 5}:
        if args[0] not in {"lowpass", "highpass"} or args[1] != "cutoff":
            raise ValueError("expected 'filter lowpass|highpass cutoff 1000hz [resonance 0.7]'")
        inst.filter_type = args[0]
        inst.cutoff = quantity(args[2], "hz", 20, 96000)
        if len(args) == 5:
            if args[3] != "resonance":
                raise ValueError("expected resonance")
            inst.resonance = number(args[4], 0.1, 10)
    elif key == "lfo" and len(args) == 6 and args[::2] == ["rate", "target", "depth"]:
        if args[3] != "filter.cutoff":
            raise ValueError("supported LFO target: filter.cutoff")
        rate = args[1]
        if rate.endswith("hz"):
            inst.lfo_rate = quantity(rate, "hz", 0.01, 30)
        else:
            value = Fraction(rate.removesuffix('t'))
            beats = 4 * value * (Fraction(2, 3) if rate.endswith('t') else 1)
            if beats <= 0:
                raise ValueError("LFO note value must be positive")
            inst.lfo_rate = float(Fraction(str(song.bpm)) / 60 / beats)
            if not 0.01 <= inst.lfo_rate <= 30:
                raise ValueError("LFO rate must be from 0.01 to 30 Hz")
        inst.lfo_depth = quantity(args[5], "hz", 0, 96000)
    elif key == "distortion" and len(args) == 1:
        levels = {"none": 0, "light": 1, "medium": 2, "heavy": 4}
        inst.drive = levels[args[0]] if args[0] in levels else number(args[0], 0, 8)
    elif key == "reverb" and len(args) == 3 and args[0] in {"room", "hall", "cathedral"} and args[1] == "mix":
        inst.reverb = number(args[2], 0, 1)
        inst.reverb_seconds = {"room": 0.6, "hall": 1.5, "cathedral": 3.0}[args[0]]
    elif key == "delay" and len(args) == 6 and args[::2] == ["time", "feedback", "mix"]:
        inst.delay_time = seconds(args[1])
        if not 0 < inst.delay_time <= 3:
            raise ValueError("delay time must be greater than 0 and at most 3s")
        inst.feedback = number(args[3], 0, 0.9)
        inst.delay = number(args[5], 0, 1)
    else:
        _describe(inst, tokens)


def _pitch_valid(pitch):
    if pitch not in DRUMS and not NOTE.fullmatch(pitch):
        raise ValueError(f"invalid note {pitch!r}; use a pitch such as C4, F#3, Bb2, or a drum name")
    if NOTE.fullmatch(pitch):
        midi = (int(pitch[2:] if pitch[1:2] in {'#', 'b'} else pitch[1:]) + 1) * 12
        midi += {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[pitch[0].lower()]
        midi += 1 if pitch[1:2] == '#' else -1 if pitch[1:2] == 'b' else 0
        if not 0 <= midi <= 127:
            raise ValueError("pitch must be in MIDI range 0..127")


def _chord(root, kind):
    # Natural chord roots default to octave 3; spell extensions as explicit notes.
    match = re.fullmatch(r"([a-gA-G])([#b]?)(-?\d)?", root)
    if not match or kind not in {"major", "minor"}:
        raise ValueError("expected 'play c major|minor for 4 beats'")
    letter, accidental, octave = match.groups()
    base = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[letter.lower()]
    base += {"": 0, "#": 1, "b": -1}[accidental]
    midi = (int(octave or 3) + 1) * 12 + base
    names = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]
    return tuple(f"{names[n % 12]}{n // 12 - 1}" for n in [midi, midi + (3 if kind == 'minor' else 4), midi + 7])


def _pattern(line, song, name):
    pattern = Pattern(name, song.beats_per_bar)
    event_lines = []
    for child in line.children:
        if child.children:
            raise child.error("pattern instructions cannot contain nested blocks")
        try:
            if child.tokens[0] == "length":
                pattern.length = duration(child.tokens[1:], song, "bar")
                pattern.explicit_length = True
            elif child.tokens[0] == "swing" and len(child.tokens) == 2:
                pattern.swing = number(child.tokens[1], 50, 75)
            else:
                event_lines.append(child)
        except (ValueError, IndexError, ZeroDivisionError) as exc:
            raise child.error(str(exc)) from exc
    cursor = Fraction(0)
    pending = []
    for child in event_lines:
        try:
            tokens = normalize_note(child.tokens)
            velocities, hold = [0.8], Fraction(1, 2)
            if "vel" in tokens:
                idx = tokens.index("vel")
                velocities = [number(v, 0, 1) for v in ' '.join(tokens[idx + 1:]).replace('and', ',').split(',')]
                tokens = tokens[:idx]
            if "hold" in tokens:
                idx = tokens.index("hold")
                hold = duration(tokens[idx + 1:], song)
                tokens = tokens[:idx]
            reference, interval, positions = None, None, []
            chord = tokens[0] == 'chord'
            if tokens[0] in {'notes', 'chord'}:
                tokens = tokens[1:]
            if len(tokens) >= 2 and tokens[1] in {'major', 'minor'}:
                tokens.insert(0, 'play')
            if tokens[0] == 'play' and len(tokens) >= 3 and tokens[2] in {'major', 'minor'}:
                if len(tokens) not in {6, 5} or tokens[3] != 'for':
                    raise ValueError("expected 'play c minor for 4 beats'")
                hold = duration(tokens[4:], song)
                pitches = _chord(tokens[1], tokens[2])
                positions = [cursor]
                cursor += hold
            elif 'at' in tokens or 'after' in tokens:
                idx = tokens.index('at') if 'at' in tokens else tokens.index('after')
                # Absolute 'at beat 2' is a friendly alias of 'on 2'.
                if tokens[idx + 1:idx + 2] in [['beat'], ['beats']]:
                    positions = [Fraction(numeric_tokens(tokens[idx + 2:])[0]) - 1]
                else:
                    reference = tuple(tokens[idx:])
                pitches = tuple(default_octave(p) for p in tokens[:idx])
            elif 'on' in tokens or 'every' in tokens:
                mode = 'on' if 'on' in tokens else 'every'
                idx = tokens.index(mode)
                pitches = tuple(default_octave(p) for p in tokens[:idx])
                if mode == 'on':
                    positions = [Fraction(v.strip()) - 1 for v in ' '.join(tokens[idx + 1:]).replace(' and ', ',').split(',')]
                else:
                    value = tokens[idx + 1:]
                    if len(value) != 1:
                        raise ValueError("expected a note value such as 'every 1/8' or 'every 1/8t'")
                    interval = 4 * Fraction(value[0].removesuffix('t')) * (Fraction(2, 3) if value[0].endswith('t') else 1)
                    if interval <= 0:
                        raise ValueError('repeat interval must be positive')
            elif len(tokens) == 2 and tokens[0] in DRUMS and re.fullmatch(r'[xX.\-]+', tokens[1]):
                pitches = (tokens[0],)
                grid = tokens[1]
                positions = [Fraction(i, len(grid)) * pattern.length for i, hit in enumerate(grid) if hit in 'xX']
            else:
                # Bare pitches form a melody; 'chord' makes simultaneous pitches.
                if tokens[0] == 'play':
                    tokens = tokens[1:]
                if 'for' in tokens:
                    idx = tokens.index('for')
                    hold = duration(tokens[idx + 1:], song)
                    tokens = tokens[:idx]
                elif 'hold' not in child.tokens:
                    hold = Fraction(1)
                pitches = tuple(default_octave(p) for p in tokens)
                for pitch in pitches:
                    _pitch_valid(pitch)
                if not chord and len(pitches) > 1:
                    for pitch in pitches:
                        pending.append((child, (pitch,), [cursor], None, hold, velocities, None))
                        cursor += hold
                    if not pattern.explicit_length:
                        pattern.length = max(pattern.length, math.ceil(cursor / song.beats_per_bar) * song.beats_per_bar)
                    continue
                positions = [cursor]
                cursor += hold
            if not pitches:
                raise ValueError('a note or drum name is required')
            if any(p in DRUMS for p in pitches) and (len(pitches) != 1 or pitches[0] not in DRUMS):
                raise ValueError('drum hits must have exactly one drum name')
            for pitch in pitches:
                _pitch_valid(pitch)
            if positions:
                if min(positions) < 0:
                    raise ValueError('beat positions start at 1')
                cursor = max(cursor, max(positions) + hold)
                if not pattern.explicit_length:
                    end = max(positions) + (Fraction(1, 4) if pitches[0] in DRUMS else hold)
                    pattern.length = max(pattern.length, math.ceil(end / song.beats_per_bar) * song.beats_per_bar)
            pending.append((child, pitches, positions, interval, hold, velocities, reference))
        except (ValueError, IndexError, ZeroDivisionError) as exc:
            raise child.error(str(exc)) from exc
    for child, pitches, positions, interval, hold, velocities, reference in pending:
        if reference:
            if len(velocities) != 1:
                raise child.error('relative notes require one velocity')
            pattern.notes.append(PendingNote(pitches, hold, velocities[0], reference, child))
            continue
        if interval:
            count = math.ceil(pattern.length / interval)
            if count > 100000:
                raise child.error('pattern has more than 100000 events')
            positions = [i * interval for i in range(count)]
        if len(velocities) not in {1, len(positions)}:
            raise child.error('provide one velocity or one per beat position')
        for i, beat in enumerate(positions):
            if beat >= pattern.length:
                raise child.error('note starts outside the declared pattern length')
            pattern.notes.append(Note(beat, hold, pitches, velocities[i % len(velocities)]))
    return pattern

def _track(line, song):
    if len(line.tokens) < 2:
        raise ValueError("track requires a name")
    name = line.tokens[1]
    track = song.tracks.setdefault(name, Track(name))
    properties = ([Line(line.number, line.tokens[2:], line.indent, base_path=line.base_path, filename=line.filename)] if line.tokens[2:] else []) + line.children
    for child in properties:
        try:
            if child.children:
                raise ValueError("track properties cannot contain nested blocks")
            args = child.tokens.copy()
            if args[0] == 'audio':
                if len(args) < 4 or args[2] != 'at':
                    raise ValueError('expected audio "file.wav" at 4 bars or at section chorus')
                if any(word in args[3:] for word in ('note', 'through', 'of')):
                    clip = AudioClip(str((child.base_path / args[1]).resolve()), reference=tuple(args[2:]))
                elif len(args) == 5 and args[3] == 'section':
                    clip = AudioClip(str((child.base_path / args[1]).resolve()), section=args[4])
                else:
                    offset = Fraction(0) if args[3:] in [['0'], ['0', 'beats'], ['0', 'bars'], ['0', 'seconds']] else duration(args[3:], song)
                    clip = AudioClip(str((child.base_path / args[1]).resolve()), offset)
                track.clips.append(clip)
                continue
            if args[0] in {'filter', 'reverb', 'delay', 'distortion'}:
                if track.effects is None:
                    track.effects = Instrument('__effects', cutoff=96000)
                _instrument_property(track.effects, args, song)
                continue
            while args:
                key = args.pop(0)
                value = args.pop(0)
                if key in {"instrument", "pattern"}:
                    parts = [value]
                    while args and args[0] not in {'instrument', 'pattern', 'volume', 'pan'}:
                        parts.append(args.pop(0))
                    setattr(track, key, ' '.join(parts))
                elif key == "volume":
                    if args and args[0].lower() in {'db', 'decibels'}:
                        args.pop(0)
                    value = value.lower()
                    track.volume = number(value.removesuffix('db'), -96, 12)
                elif key == "pan":
                    track.pan = 0 if value == "center" else number(value, -100, 100) / 100
                else:
                    raise ValueError(f"unknown track property {key!r}")
        except (ValueError, IndexError) as exc:
            raise child.error(str(exc)) from exc


def parse_song(source: str, *, base_path=None, _bank=False) -> Song:
    """Parse text to a song, rejecting unsupported commands with source lines."""
    song = Song()
    lines = _load_lines(source, Path(base_path or Path.cwd()).resolve())
    entry_summary = []
    if not _bank:
        from .arrange import compact_source
        try:
            compact = compact_source(lines)
        except MTLError:
            raise
        except (ValueError, IndexError, ZeroDivisionError, OverflowError) as exc:
            raise MTLError(f'compact input: {exc}') from exc
        if compact is not None:
            source, entry_summary = compact
            lines = _load_lines(source, Path(base_path or Path.cwd()).resolve())
        lines = _friendly_lines(lines)
    pending_automation = []
    # Resolve global meter and tempo before durations, regardless of declaration order.
    global_keys = {"song", "bpm", "time_signature", "length", "output", "render", "sample_rate", "bit_depth", "seed", "key", "genre"}
    for line in lines:
        try:
            tokens = line.tokens
            key, args = tokens[0], tokens[1:]
            if key in global_keys and line.children:
                raise ValueError(f"{key} does not accept a block")
            if key == "bpm" and len(args) == 1:
                song.bpm = number(args[0], 20, 300)
            elif key == "time_signature" and len(args) == 1:
                numerator, denominator = map(int, args[0].split('/'))
                if not 1 <= numerator <= 32 or denominator not in {1, 2, 4, 8, 16}:
                    raise ValueError("invalid time signature")
                song.beats_per_bar = Fraction(4 * numerator, denominator)
        except (ValueError, ZeroDivisionError) as exc:
            raise line.error(str(exc)) from exc
    for line in lines:
        try:
            key, *args = line.tokens
            if key == "song" and len(args) == 1:
                song.title = args[0]
            elif key in {"bpm", "time_signature"} and len(args) == 1:
                pass
            elif key in {"key", "genre"} and args:
                pass  # Descriptive metadata; pitches are always explicit.
            elif key == "length":
                song.length = duration(args, song, "second")
            elif key == "output" and len(args) == 1:
                song.output = args[0]
            elif key == "render" and len(args) == 2 and args[0] == "to":
                song.output = args[1]
            elif key == "sample_rate" and len(args) == 1:
                song.sample_rate = int(args[0])
                if song.sample_rate not in {22050, 44100, 48000, 88200, 96000}:
                    raise ValueError("sample_rate must be 22050, 44100, 48000, 88200, or 96000")
            elif key == "bit_depth" and len(args) == 1:
                song.bit_depth = int(args[0])
                if song.bit_depth not in {16, 24}:
                    raise ValueError("bit_depth must be 16 or 24")
            elif key == "seed" and len(args) == 1:
                song.seed = int(args[0])
                if not 0 <= song.seed < 2**32:
                    raise ValueError("seed must be an unsigned 32-bit integer")
            elif key == "instrument" and (len(args) == 1 or len(args) == 3 and args[1] == "from"):
                name = args[0]
                if name in song.instruments:
                    raise ValueError(f"duplicate instrument {name!r}")
                if len(args) == 3:
                    if args[2] not in song.instruments:
                        song.instruments[args[2]] = _preset(args[2], gm=not _bank)
                    inst = replace(song.instruments[args[2]], name=name, program=None)
                else:
                    try:
                        inst = _preset(name, gm=not _bank)
                    except ValueError:
                        inst = Instrument(name)
                for child in line.children:
                    try:
                        if child.children:
                            raise ValueError("instrument properties cannot contain nested blocks")
                        if child.tokens[0] in {'sample', 'sample_map'} and len(child.tokens) == 2:
                            setattr(inst, 'sample_path' if child.tokens[0] == 'sample' else 'sample_map', str((child.base_path / child.tokens[1]).resolve()))
                        else:
                            _instrument_property(inst, child.tokens.copy(), song)
                    except (ValueError, IndexError, ZeroDivisionError) as exc:
                        raise child.error(str(exc)) from exc
                if inst.engine == "sampler" and not inst.sample_path:
                    raise (line.children[-1] if line.children else line).error(f"sampler {name!r} requires a sample WAV file")
                song.instruments[name] = inst
            elif key in DRUMS and args:
                if line.children:
                    raise ValueError("drum descriptions cannot contain nested blocks")
                inst = _preset(key)
                _describe(inst, args)
                song.instruments[key] = inst
            elif key == "pattern" and len(args) == 1:
                if args[0] in song.patterns:
                    raise ValueError(f"duplicate pattern {args[0]!r}")
                song.patterns[args[0]] = _pattern(line, song, args[0])
            elif key == "drums" and not args:
                if "__drums" in song.patterns or "__drums" in song.tracks:
                    raise ValueError("duplicate shorthand drums block")
                song.patterns["__drums"] = _pattern(line, song, "__drums")
                song.tracks["__drums"] = Track("__drums", "drums", "__drums")
            elif key == "track":
                _track(line, song)
            elif key == "section" and len(args) == 1:
                if any(s.name == args[0] for s in song.sections):
                    raise ValueError(f"duplicate section {args[0]!r}")
                section = Section(args[0], song.beats_per_bar * 8)
                for child in line.children:
                    try:
                        if child.children:
                            raise ValueError("section instructions cannot contain nested blocks")
                        t = child.tokens
                        if t[0] == "length":
                            section.length = duration(t[1:], song, "bar")
                        elif len(t) == 2 and t[0] in {"add", "remove", "only"}:
                            section.actions.append((t[0], t[1]))
                        elif len(t) == 2 and t[1] == "only":
                            section.actions.append(("only", t[0]))
                        else:
                            raise ValueError("expected length, add TRACK, remove TRACK, or TRACK only")
                    except (ValueError, IndexError, ZeroDivisionError) as exc:
                        raise child.error(str(exc)) from exc
                song.sections.append(section)
            elif key == "over" and len(args) == 4 and args[2] == "in":
                ramp_length = duration(args[:2], song, "bar")
                if not line.children:
                    raise ValueError("automation block requires at least one target")
                for child in line.children:
                    try:
                        t = child.tokens
                        if child.children or len(t) != 5 or t[1] != 'from' or t[3] != 'to':
                            raise ValueError("expected TRACK.volume from -6db to -3db or TRACK.filter.cutoff from 400hz to 1200hz")
                        if t[0].endswith('.filter.cutoff'):
                            track, parameter = t[0][:-len('.filter.cutoff')], 'filter.cutoff'
                            start, end = (quantity(v, 'hz', 20, 96000) for v in (t[2], t[4]))
                        elif t[0].endswith('.volume'):
                            track, parameter = t[0][:-len('.volume')], 'volume'
                            start, end = (quantity(v, 'db', -96, 12) for v in (t[2], t[4]))
                        else:
                            raise ValueError("supported automation targets: TRACK.volume and TRACK.filter.cutoff")
                        pending_automation.append((child, Automation(args[3], track, parameter, ramp_length, start, end)))
                    except (ValueError, IndexError, ZeroDivisionError) as exc:
                        raise child.error(str(exc)) from exc
            elif key == "humanize" and args == ["all", "tracks"]:
                for child in line.children:
                    if child.children or len(child.tokens) != 2:
                        raise child.error("expected timing ±5ms or velocity ±5%")
                    parameter, value = child.tokens
                    value = value.removeprefix('±').removeprefix('+/-')
                    if parameter == "timing":
                        song.timing_ms = quantity(value, "ms", 0, 100)
                    elif parameter == "velocity":
                        song.velocity_variation = quantity(value, "%", 0, 100) / 100
                    else:
                        raise child.error("unknown humanize parameter")
            elif key == "master" and not args:
                for child in line.children:
                    if child.children or len(child.tokens) != 2 or child.tokens[0] != "peak":
                        raise child.error("supported mastering command: peak -1db (sample peak ceiling)")
                    song.peak_db = quantity(child.tokens[1], "db", -24, -0.1)
            else:
                raise ValueError(f"unsupported instruction: {' '.join(line.tokens)!r}")
        except MTLError:
            raise
        except (ValueError, IndexError, ZeroDivisionError) as exc:
            raise line.error(str(exc)) from exc
    if not song.tracks and song.patterns:
        for name in song.patterns:
            song.tracks[name] = Track(name, 'drums' if all(n.pitches[0] in DRUMS for n in song.patterns[name].notes) else 'piano', name)
    for track in song.tracks.values():
        if not track.clips:
            if not track.pattern:
                track.pattern = track.name if track.name in song.patterns else next(iter(song.patterns), '') if len(song.patterns) == 1 else ''
            if not track.instrument:
                track.instrument = track.name if _known_instrument(track.name) else 'piano'
    _resolve_references(song)
    for inst in song.instruments.values():
        if inst.engine == 'multisampler' and not inst.sample_map:
            raise MTLError(f'multisampler {inst.name!r} requires sample_map "file.json"')
        if inst.engine == 'sampler' and not inst.sample_path:
            raise MTLError(f'sampler {inst.name!r} requires a sample WAV file')
    for track in song.tracks.values():
        if track.clips:
            if track.pattern or track.instrument:
                raise MTLError(f'track {track.name!r}: audio clips and instrument patterns require separate tracks')
            for clip in track.clips:
                if clip.section is not None and not any(s.name == clip.section for s in song.sections):
                    raise MTLError(f'track {track.name!r}: unknown audio section {clip.section!r}')
            continue
        if track.pattern not in song.patterns:
            raise MTLError(f"track {track.name!r}: unknown pattern {track.pattern!r}")
        if track.instrument != "drums" and track.instrument not in song.instruments:
            try:
                song.instruments[track.instrument] = _preset(track.instrument)
            except ValueError as exc:
                raise MTLError(f"track {track.name!r}: {exc}") from exc
        for note in song.patterns[track.pattern].notes:
            is_drum = note.pitches[0] in DRUMS
            if (track.instrument == "drums") != is_drum:
                # A single drum instrument can play pitched events as triggers.
                if not (track.instrument != "drums" and song.instruments[track.instrument].engine == "drum"):
                    raise MTLError(f"track {track.name!r}: drum patterns require instrument drums; pitched patterns require a melodic instrument")
    for section in song.sections:
        for _, track in section.actions:
            if track not in song.tracks and track != "all":
                raise MTLError(f"section {section.name!r}: unknown track {track!r}")
    seen = set()
    sections = {section.name: section for section in song.sections}
    for line, automation in pending_automation:
        if automation.section not in sections:
            raise line.error(f"unknown section {automation.section!r}")
        if automation.track not in song.tracks:
            raise line.error(f"unknown track {automation.track!r}")
        if automation.duration > sections[automation.section].length:
            raise line.error("automation duration exceeds section length")
        identity = (automation.section, automation.track, automation.parameter)
        if identity in seen:
            raise line.error("duplicate automation target in section")
        seen.add(identity)
        song.automation.append(automation)
    if song.length is None:
        song.length = sum((s.length for s in song.sections), Fraction(0)) or song.beats_per_bar * 4
    song.entry_summary = entry_summary
    return song


@lru_cache(maxsize=1)
def _gm_names():
    text = (Path(__file__).parent / 'presets/general_midi.mtl').read_text(encoding='utf-8')
    return tuple(re.findall(r'^instrument (gm_\w+)', text, re.M))


@lru_cache(maxsize=1)
def _gm_bank():
    return parse_song('import bank "general_midi"', _bank=True).instruments


def _gm_name(name):
    name = name.lower().replace('-', '_').replace(' ', '_').removeprefix('gm_')
    aliases = {'grand_piano': 'acoustic_grand_piano', 'grand': 'acoustic_grand_piano',
               'piano': 'acoustic_grand_piano', 'panio': 'acoustic_grand_piano',
               'vibes': 'vibraphone', 'organ': 'drawbar_organ', 'strings': 'string_ensemble_1'}
    name = aliases.get(name, name)
    names = {n.removeprefix('gm_'): n for n in _gm_names()}
    if name in names:
        return names[name]
    ranked = sorted(((SequenceMatcher(None, name, n).ratio(), n) for n in names), reverse=True)
    if ranked[0][0] >= .8 and ranked[0][0] - ranked[1][0] >= .12:
        return names[ranked[0][1]]
    return None


def _known_instrument(name):
    return name in DRUMS | {'piano', 'guitar', 'pluck', 'bass', 'lead', 'pad', 'bell', 'sine', 'synth', 'drums'} or _gm_name(name) is not None


def _is_note_line(tokens):
    return tokens[0].lower() in {'notes', 'chord', 'play'} or tokens[0] in DRUMS or bool(re.fullmatch(r'[a-gA-G][#b]?(?:-?\d)?', tokens[0]))


def _friendly_lines(lines):
    """Lower entry shortcuts into the original instrument/pattern/track grammar."""
    result = []
    used = {t for line in lines for t in line.tokens}
    serial = 0
    entry_headers = set()

    def fresh():
        nonlocal serial
        while True:
            serial += 1
            name = f'__entry_{serial}'
            if name not in used:
                used.add(name)
                return name

    def new(line, tokens, children=None):
        return replace(line, tokens=tokens, children=children or [])

    def walk(line):
        line.tokens = normalize(line.tokens)
        for child in line.children:
            walk(child)
        return line

    def expand(line, name, instrument, children):
        pattern_name = fresh()
        pattern_lines, track_lines, voice_lines = [], [], []
        for child in children:
            key = child.tokens[0]
            if key == 'pattern' and child.children:
                pattern_lines.extend(child.children)
            elif _is_note_line(child.tokens) or key in {'length', 'swing'}:
                pattern_lines.append(child)
            elif key in {'volume', 'pan', 'instrument', 'pattern', 'audio', 'filter', 'reverb', 'delay', 'distortion'}:
                if key == 'instrument' and len(child.tokens) > 2:
                    child.tokens = ['instrument', ' '.join(child.tokens[1:])]
                track_lines.append(child)
            else:
                voice_lines.append(child)
        if voice_lines:
            voice_name = fresh()
            result.append(new(line, ['instrument', voice_name, 'from', instrument], voice_lines))
            instrument = voice_name
        if pattern_lines:
            result.append(new(line, ['pattern', pattern_name], pattern_lines))
            track_lines.insert(0, new(line, ['pattern', pattern_name]))
        if instrument:
            track_lines.insert(0, new(line, ['instrument', instrument]))
        result.append(new(line, ['track', name], track_lines))

    current = None
    for original in lines:
        line = walk(original)
        t = line.tokens
        key = t[0]
        if key == 'track':
            current = None
            # Preserve inline canonical arguments; split only tracks with inline notes.
            if any(_is_note_line(c.tokens) or c.tokens[0] == 'pattern' and c.children for c in line.children):
                header = new(line, ['track', *t[1:2]], line.children)
                extra = [new(line, t[2:])] if len(t) > 2 else []
                expand(header, t[1], '', extra + line.children)
            else:
                for child in line.children:
                    if child.tokens[0] == 'instrument' and len(child.tokens) > 2:
                        child.tokens = ['instrument', ' '.join(child.tokens[1:])]
                result.append(line)
        elif key == 'drums' and len(t) == 2 and t[1] in {'jazz', 'country', 'reggae', 'dubstep'}:
            from .arrange import drum_events
            import random
            current = None
            events = drum_events(t[1], 1, Fraction(0), Fraction(4), False, random.Random(0))
            result.append(new(line, ['drums'], [new(line, [notes[0], 'on', str(beat + 1), 'vel', str(vel)]) for beat, notes, _, vel in events] + line.children))
        elif key == 'drums' and len(t) == 2 and t[1] in {'house', 'techno', 'basic', 'rock'}:
            current = None
            beats = ['1,2,3,4', '2,4'] if t[1] in {'house', 'techno'} else ['1,3', '2,4']
            result.append(new(line, ['drums'], [new(line, ['kick', 'on', beats[0]]), new(line, ['snare', 'on', beats[1]]), new(line, ['hihat', 'every', '1/8']), *line.children]))
        elif key not in {'instrument', 'pattern', 'song', 'key', 'genre', 'output', 'section', 'render', 'import'} and _known_instrument(' '.join(t)) and key != 'drums':
            name = ' '.join(t).lower().replace(' ', '_')
            # Keep a reference to this block so unindented entry can continue it.
            current = new(line, ['track', name], line.children)
            result.append(current)
            entry_headers.add(id(current))
            current.tokens += ['instrument', name]
        elif current is not None and (_is_note_line(t) or key in PROPERTIES - {'bpm', 'tempo', 'humanize'}):
            current.children.append(line)
        elif _is_note_line(t) and key not in DRUMS:
            current = new(line, ['track', 'piano', 'instrument', 'piano'], [line])
            result.append(current)
        else:
            current = None
            result.append(line)
    # Expand bare-instrument blocks after their unindented continuation is collected.
    originals, result = result, []
    for line in originals:
        t = line.tokens
        if t[0] == 'track' and len(t) == 4 and t[2] == 'instrument' and (id(line) in entry_headers or any(_is_note_line(c.tokens) for c in line.children)):
            if id(line) in entry_headers and not any(_is_note_line(c.tokens) or c.tokens[0] in {'pattern', 'audio'} for c in line.children):
                line.children.append(new(line, ['notes', 'c4', 'e4', 'g4', 'c5']))
            expand(line, t[1], t[3], line.children)
        else:
            result.append(line)
    return result


@dataclass(frozen=True)
class PendingNote:
    pitches: tuple[str, ...]
    duration: Fraction
    velocity: float
    reference: tuple[str, ...]
    line: Line


def _reference(tokens, song, local=None, index=None):
    """Resolve a structural note onset/gate, before swing or humanization."""
    t = [x for x in tokens if x != 'the']
    fraction = Fraction(1) if t.pop(0) == 'after' else Fraction(0)
    offset = Fraction(0)
    for separator in ('plus', 'minus'):
        if separator in t:
            split = t.index(separator)
            offset = duration(t[split + 1:], song) * (1 if separator == 'plus' else -1)
            t = t[:split]
            break
    if 'of' in t and t[0] not in {'start', 'end'}:
        split = t.index('of')
        t = numeric_tokens(t[:split]) + t[split:]
    if t[:2] in [['end', 'of'], ['start', 'of']]:
        fraction, t = Fraction(t[0] == 'end'), t[2:]
    elif t[:2] == ['halfway', 'through']:
        fraction, t = Fraction(1, 2), t[2:]
    elif len(t) >= 3 and t[1] in {'of', 'through'}:
        percent = numeric_tokens([t[0]])[0]
        if not percent.endswith('%'):
            raise ValueError('use a percentage such as 50% of piano note 1')
        fraction, t = Fraction(percent[:-1]) / 100, t[2:]
        if not 0 <= fraction <= 1:
            raise ValueError('note completion percentage must be 0..100%')
    if t == ['previous', 'note']:
        if local is None or not index:
            raise ValueError('previous note requires an earlier note in this pattern')
        pattern, ordinal = local, index - 1
    else:
        if len(t) == 3 and t[1] == 'note':
            target, _, ordinal = t
            if target not in song.tracks:
                raise ValueError(f'unknown reference track {target!r}')
            pattern = song.tracks[target].pattern
        elif len(t) == 2 and t[0] == 'note' and local:
            pattern, ordinal = local, t[1]
        else:
            raise ValueError('expected previous note, note N, or TRACK note N')
        ordinal_value = Fraction(numeric_tokens([ordinal])[0])
        if ordinal_value.denominator != 1:
            raise ValueError('note number must be an integer')
        ordinal = int(ordinal_value) - 1
    if pattern not in song.patterns or not 0 <= ordinal < len(song.patterns[pattern].notes):
        raise ValueError('referenced note does not exist')
    return pattern, ordinal, fraction, offset


def _resolve_references(song):
    visiting = set()

    def resolve(name, index):
        note = song.patterns[name].notes[index]
        if isinstance(note, Note):
            return note
        identity = (name, index)
        if identity in visiting:
            raise note.line.error('cyclic note timing reference')
        if len(visiting) >= 128:
            raise note.line.error('note timing reference nesting exceeds 128')
        visiting.add(identity)
        try:
            target, ordinal, fraction, offset = _reference(note.reference, song, name, index)
            anchor = resolve(target, ordinal)
            beat = anchor.beat + fraction * anchor.duration + offset
            if beat < 0:
                raise ValueError('relative timing starts before the pattern')
            result = Note(beat, note.duration, note.pitches, note.velocity)
            song.patterns[name].notes[index] = result
            return result
        except (ValueError, IndexError, ZeroDivisionError) as exc:
            if isinstance(exc, MTLError):
                raise
            raise note.line.error(str(exc)) from exc
        finally:
            visiting.remove(identity)

    relative_patterns = {p.name for p in song.patterns.values() if any(isinstance(n, PendingNote) for n in p.notes)}
    for pattern in song.patterns.values():
        for i in range(len(pattern.notes)):
            note = resolve(pattern.name, i)
            if pattern.explicit_length and note.beat >= pattern.length:
                raise MTLError(f'pattern {pattern.name!r}: note starts outside the declared pattern length')
        if pattern.name in relative_patterns and not pattern.explicit_length:
            end = max((n.beat + n.duration for n in pattern.notes), default=0)
            pattern.length = max(pattern.length, math.ceil(end / song.beats_per_bar) * song.beats_per_bar)
    for track in song.tracks.values():
        for i, clip in enumerate(track.clips):
            if clip.reference:
                try:
                    name, index, fraction, offset = _reference(clip.reference, song)
                    note = song.patterns[name].notes[index]
                    beat = note.beat + fraction * note.duration + offset
                    tokens = [t for t in clip.reference if t != 'the']
                    target_track = tokens[tokens.index('note') - 1]
                    track.clips[i] = replace(clip, offset=beat, reference_track=target_track,
                                            reference_note=index, reference_fraction=fraction,
                                            reference_delay=offset)
                except (ValueError, IndexError, ZeroDivisionError) as exc:
                    raise MTLError(f'audio on track {track.name!r}: {exc}') from exc
