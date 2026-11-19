"""Deterministic compact-song compiler. Explicit MTL blocks bypass this layer."""
from fractions import Fraction
import math
import random
import re

from .friendly import default_octave, normalize, numeric_tokens
from .model import MTLError

STYLES = {'jazz', 'country', 'techno', 'reggae', 'rock', 'house', 'basic', 'dubstep'}
NOTE = re.compile(r'([a-g](?:#|b)?)(-?\d)?(m|min|maj)?(?:(\d+(?:\.\d+)?)(ms|s|beats?))?$', re.I)
SOLFEGE = dict(zip('do re mi fa sol la ti si'.split(), 'c d e f g a b b'.split()))


def compact_source(lines):
    from .parser import _known_instrument, duration, parse_song
    if not lines or any(line.children for line in lines):
        return None
    forbidden = {'track', 'instrument', 'pattern', 'section', 'import', 'over', 'humanize', 'master', 'render'}
    if any(line.tokens[0] in forbidden for line in lines):
        return None
    metadata, phrases = [], []
    style, drums, bass, chords, auto_progression = 'basic', True, False, False, False
    intro = ending = True
    repeat = None
    explicit_compact = False
    for line in lines:
        t = line.tokens.copy()
        for groove in STYLES:
            for suffix in (['with', groove, 'drums'], ['drums', groove]):
                if len(t) > len(suffix) and t[-len(suffix):] == suffix:
                    style, drums, explicit_compact = groove, True, True
                    t = t[:-len(suffix)]
        key = t[0].lower()
        if key in {'song', 'bpm', 'tempo', 'time_signature', 'seed', 'key', 'output', 'sample_rate', 'bit_depth', 'length'}:
            metadata.append(normalize(t))
            continue
        if key in {'drum', 'drums', 'drummer', 'style'} and len(t) == 2:
            if t[1] not in STYLES | {'off', 'none', 'auto'}:
                # Leave canonical drum descriptions/errors to the normal parser.
                return None
            drums = t[1] not in {'off', 'none'}
            style = t[1] if t[1] in STYLES else style
            explicit_compact |= t[1] not in {'house', 'techno', 'basic', 'rock'}
            continue
        if key in {'intro', 'ending', 'end'} and len(t) == 2 and t[1] in {'off', 'on', 'auto'}:
            if key == 'intro': intro = t[1] != 'off'
            else: ending = t[1] != 'off'
            explicit_compact = True
            continue
        if key in {'generate', 'auto'}:
            options = set(t[1:]) - {'and', 'a', 'automatic'}
            if not options or options - {'bass', 'chords', 'progression', 'drums'}:
                raise line.error('generate accepts bass, chords, progression and drums')
            bass |= 'bass' in options
            chords |= bool(options & {'chords', 'progression'})
            auto_progression |= 'progression' in options
            explicit_compact = True
            continue
        if key == 'progression':
            auto_progression = t[1:] == ['auto']
            if not auto_progression:
                phrases.append(('piano', t[1:], True, line))
            chords = True
            explicit_compact = True
            continue
        if key in {'repeat', 'repat', 'repeate', 'loop'}:
            repeat = t[1:]
            explicit_compact = True
            continue
        role = False
        if key in {'notes', 'play'}:
            t = t[1:]
        if t and t[0] in {'chords', 'melody'}:
            role = t.pop(0) == 'chords'
        instrument = 'piano'
        # Longest recognized GM name before the first note.
        for count in range(len(t) - 1, 0, -1):
            candidate = ' '.join(t[:count]).lower()
            if _known_instrument(candidate):
                instrument, t = candidate, t[count:]
                explicit_compact = True
                break
        if t and t[0] in {'chords', 'melody'}:
            role = t.pop(0) == 'chords'
        for marker in ('repeat', 'repat', 'repeate', 'loop'):
            if marker in t:
                split = t.index(marker)
                repeat, t = t[split + 1:], t[:split]
                explicit_compact = True
                break
        if not t or not all(NOTE.fullmatch(x.strip(',').lower()) or x.lower() in SOLFEGE or re.fullmatch(r'\d+(?:\.\d+)?(?:s|ms|beats?)', x) for x in t):
            return None
        phrases.append((instrument, t, role, line))
    if not phrases and not explicit_compact:
        return None
    # Metadata is parsed through the established validation, including tempo/meter.
    meta_source = '\n'.join(' '.join(repr(v) if ' ' in v else v for v in t) for t in metadata)
    context = parse_song(meta_source, _bank=True)
    body = duration(repeat, context, 'bars') if repeat else context.length if any(t[0] == 'length' for t in metadata) else context.beats_per_bar * 4
    bars = body / context.beats_per_bar
    if bars.denominator != 1 or not 1 <= bars <= 256:
        raise MTLError('compact repeat/length must be 1..256 whole bars')
    bar = context.beats_per_bar
    offset = bar if intro else Fraction(0)
    total = offset + body + (bar if ending else 0)
    rng = random.Random(context.seed)
    output = [' '.join(repr(v) if ' ' in v else v for v in t) for t in metadata if t[0] != 'length']
    output += [f'length {total} beats']
    roots = []
    declared = set()

    def pitch(root, octave):
        return root + str(octave)

    def triad(root, minor, octave=3):
        from .parser import _chord
        return _chord(pitch(root, octave), 'minor' if minor else 'major')

    def emit(name, instrument, events, volume=-8, pan=0):
        from .parser import _preset
        if instrument not in declared and instrument != 'drums' and _preset(instrument).engine == 'piano':
            output.extend([f'instrument "{instrument}"', '    pedal 0.18', '    stereo_width 0.75'])
            declared.add(instrument)
        output.extend([f'pattern {name}', f'    length {total} beats'])
        for beat, notes, gate, vel in sorted(events, key=lambda e: e[0]):
            output.append(f"    {' '.join(notes)} on {beat + 1} hold {gate} beats vel {vel:.5f}")
        output.append(f'track {name} instrument "{instrument}" pattern {name} volume {volume}db pan {pan}')

    for index, (instrument, tokens, role, line) in enumerate(phrases):
        parsed = []
        common_gate = Fraction(1)
        if tokens and re.fullmatch(r'\d+(?:\.\d+)?(?:s|ms|beats?)', tokens[-1]):
            common_gate = duration([tokens.pop()], context)
        for token in tokens:
            token = SOLFEGE.get(token.lower(), token.lower()).strip(',')
            match = NOTE.fullmatch(token)
            if not match:
                raise line.error(f'invalid compact note {token!r}')
            root, octave, quality, amount, unit = match.groups()
            gate = duration([amount + unit], context) if amount else common_gate
            if gate > 32 or gate < Fraction(1, 16):
                raise line.error('compact note duration must be 1/16..32 beats')
            parsed.append((root, quality in {'m', 'min'}, int(octave) if octave is not None else 4, gate))
        if not parsed:
            raise line.error('enter at least one note')
        if not roots:
            roots = [(r, minor) for r, minor, _, _ in parsed]
        is_bass = 'bass' in instrument and 'bassoon' not in instrument
        events, cursor, n = [], offset, 0
        while cursor < offset + body:
            root, minor, octave, gate = parsed[n % len(parsed)]
            # Bass roles always get a single low root, including chord requests.
            notes = (pitch(root, min(octave, 2)),) if is_bass else triad(root, minor) if role else (pitch(root, octave),)
            held = min(gate * Fraction(9, 10), offset + body - cursor)
            events.append((cursor, notes, held, rng.uniform(.68, .83)))
            cursor += gate
            n += 1
        first_root, first_minor, octave, _ = parsed[0]
        closing = (pitch(first_root, min(octave, 2)),) if is_bass else triad(first_root, first_minor) if role else (pitch(first_root, octave),)
        if intro:
            events.insert(0, (0, closing, bar / 2, .52))
        if ending:
            events.append((offset + body, closing, bar / 3, .62))
        name = instrument.replace(' ', '_') if index == 0 else f'part_{index + 1}'
        emit(name, instrument, events, -5 if not is_bass else -9)
        if is_bass:
            bass = False
    if auto_progression:
        # Transpose I-vi-IV-V to the requested key, or first entered root.
        key_tokens = next((t[1:] for t in metadata if t[0] == 'key'), [])
        tonic = key_tokens[0] if key_tokens else roots[0][0] if roots else 'c'
        minor = len(key_tokens) > 1 and key_tokens[1] == 'minor'
        from .dsp import frequency
        semitone = round(69 + 12 * math.log2(frequency(default_octave(tonic)) / 440)) % 12
        names = ['c','c#','d','d#','e','f','f#','g','g#','a','a#','b']
        roots = [(names[(semitone + step) % 12], quality) for step, quality in
                 ([(0, True),(8, False),(3, False),(10, False)] if minor else [(0, False),(9, True),(5, False),(7, False)])]
    roots = roots or [('c', False), ('a', True), ('f', False), ('g', False)]
    for generated in ('bass', 'chords'):
        if not (bass if generated == 'bass' else chords):
            continue
        events = []
        for i in range(int(bars)):
            root, minor = roots[i % len(roots)]
            start = offset + i * bar
            if generated == 'bass':
                for step in (0, bar / 2):
                    events.append((start + step, (pitch(root, 2),), bar * Fraction(2, 5), .7))
            else:
                events.append((start, triad(root, minor), bar * Fraction(4, 5), .55))
        if ending:
            root, minor = roots[0]
            events.append((offset + body, (pitch(root, 2),) if generated == 'bass' else triad(root, minor), bar / 3, .6))
        emit('auto_' + generated, 'acoustic_bass' if generated == 'bass' else 'piano', events, -10 if generated == 'bass' else -14, -15 if generated == 'chords' else 0)
    if drums:
        emit('auto_drums', 'drums', drum_events(style, int(bars), offset, bar, ending, rng), -9)
    output.extend(['humanize all tracks', '    timing ±4ms', '    velocity ±2%'])
    summary = [f'Compact song: {context.bpm:g} BPM, {bars} body bars, intro {"on" if intro else "off"}, ending {"on" if ending else "off"}.',
               f'Drummer: {style if drums else "off"}; generated bass {bass}; generated chords {chords}.',
               'Bare notes use octave 4; bass roots use octave 2. Attached g2s means G4 held for 2 seconds.']
    return '\n'.join(output), summary


def drum_events(style, bars, offset, bar, ending, rng):
    """Style-specific accents, deterministic variations, setup and turnaround fills."""
    grooves = {
        'basic': {'kick':[0,2], 'snare':[1,3], 'hihat':[i/2 for i in range(8)]},
        'rock': {'kick':[0,1.5,2,2.75], 'snare':[1,3], 'hihat':[i/2 for i in range(8)]},
        'house': {'kick':[0,1,2,3], 'clap':[1,3], 'open_hat':[.5,1.5,2.5,3.5]},
        'techno': {'kick':[0,1,2,3], 'clap':[1,3], 'hihat':[i/4 for i in range(16)], 'open_hat':[.5,2.5]},
        'jazz': {'ride':[0,1,Fraction(5,3),2,3,Fraction(11,3)], 'kick':[0,2], 'snare':[Fraction(2,3),Fraction(8,3)], 'hihat':[1,3]},
        'country': {'kick':[0,2], 'snare':[i/2 for i in range(8)], 'hihat':[0,1,2,3]},
        'reggae': {'kick':[2], 'snare':[2], 'hihat':[i/2 for i in range(8)], 'perc':[1.5,3.5]},
        'dubstep': {'kick':[0, Fraction(11,4)], 'snare':[2], 'hihat':[0,.5,1,1.5,2,2.5,3,3.25,3.5,3.75]},
    }
    events = []
    scale = bar / 4
    if offset:
        for step in (0,1,2):
            events.append((step * scale, ('hihat',), Fraction(1, 8), .35))
        for step in (3,3.5,3.75):
            events.append((Fraction(str(step)) * scale, ('snare',), Fraction(1, 8), .45))
    for i in range(bars):
        start = offset + i * bar
        for sound, positions in grooves[style].items():
            for j, step in enumerate(positions):
                accent = .82 if sound == 'kick' else .72 if sound in {'snare','clap'} and Fraction(str(step)).denominator == 1 else .45
                if style == 'jazz' and sound in {'snare','kick'}: accent *= .6
                if style == 'country' and sound == 'snare': accent = .7 if step in {1,3} else .27
                vel = max(.1, min(1, accent + rng.uniform(-.045,.045)))
                events.append((start + Fraction(str(step)) * scale, (sound,), Fraction(1, 8), vel))
        if (i + 1) % 4 == 0 or i == bars - 1:
            for j, step in enumerate((3,3.25,3.5,3.75)):
                events.append((start + Fraction(str(step)) * scale, ('tom' if j >= 2 else 'snare',), Fraction(1, 8), .45 + j * .08))
    if ending:
        for sound in ('kick','cymbal'):
            events.append((offset + bars * bar, (sound,), Fraction(1, 4), .68))
    return events
