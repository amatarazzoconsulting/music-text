"""Conservative conveniences for MTL; filenames and user identifiers stay intact."""
import re
from fractions import Fraction

WORDS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
WORDS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10))))
UNITS = {'millisecond': 'ms', 'milliseconds': 'ms', 'hz': 'hz', 'hertz': 'hz',
         's': 's', 'second': 's', 'seconds': 's', 'db': 'db', 'decibels': 'db', 'percent': '%', 'ms': 'ms', '%': '%'}
PROPERTIES = {'volume', 'pan', 'length', 'swing', 'envelope', 'filter', 'reverb', 'delay',
              'distortion', 'oscillator', 'vibrato', 'drawbars', 'rotary', 'percussion',
              'bpm', 'tempo', 'hammer', 'soundboard', 'string_detune', 'pedal', 'stereo_width', 'timing', 'velocity', 'peak', 'lfo', 'humanize'}
NUMERIC = re.compile(r'[+±-]?(?:\d+(?:\.\d*|,\d+)?|\.\d+)(?:/\d+)?\Z')


def numeric_tokens(tokens, *, decimal_comma=False):
    """Normalize numbers only in numeric grammar positions, never song/file names."""
    text = ' '.join(tokens).lower().replace('−', '-').replace('½', ' 1/2').replace('¼', ' 1/4').replace('¾', ' 3/4')
    if decimal_comma:
        text = re.sub(r'(?<=\d),(?=\d)', '.', text)
    text = re.sub(r'\b(?:about|around|roughly|approximately)\s+', '', text)
    text = re.sub(r'\b(?:a|an)\s+(?=half|quarter)', '', text)
    text = re.sub(r'\bhalf(?:\s+(?:a|one))?\b', '1/2', text)
    text = re.sub(r'\bquarter(?:\s+(?:a|one))?\b', '1/4', text)
    text = re.sub(r'\bthree quarters\b', '3/4', text)
    text = re.sub(r'\b(?:a|an)\b', '1', text)
    text = re.sub(r'\b(' + '|'.join(WORDS) + r')\b', lambda m: str(WORDS[m[0]]), text)
    text = re.sub(r'\b(\d+)\s+and\s+(1/[24]|3/4)\b', lambda m: str(Fraction(m[1]) + Fraction(m[2])), text)
    text = re.sub(r'\b([2-9]0)\s+([1-9])\b', lambda m: str(int(m[1]) + int(m[2])), text)
    # Mixed numbers such as 1½ have the same meaning as 1 and a half.
    text = re.sub(r'\b(\d+)\s+(1/[24]|3/4)\b', lambda m: str(Fraction(m[1]) + Fraction(m[2])), text)
    result = []
    for token in text.split():
        unit = UNITS.get(token)
        if unit and result and NUMERIC.fullmatch(result[-1]):
            result[-1] += unit
        else:
            result.append(token)
    return result


def normalize(tokens):
    """Recognize forgiving spellings while leaving the canonical grammar intact."""
    t = tokens.copy()
    key = t[0].lower()
    if key in PROPERTIES:
        t = [key, *numeric_tokens(t[1:], decimal_comma=True)]
        if key in {'tempo', 'bpm'}:
            t[0] = 'bpm'
            if t[-1].endswith('bpm'):
                t[-1] = t[-1][:-3]
            if t[-1] == '':
                t.pop()
        if key == 'pan':
            words = ' '.join(t[1:])
            pans = {'left': '-100', 'right': '100', 'slightly left': '-25', 'slightly right': '25', 'centre': 'center'}
            if words in pans:
                t = ['pan', pans[words]]
        if key == 'swing' and len(t) == 2:
            t[1] = t[1].removesuffix('%')
    return t


def normalize_note(tokens):
    t = tokens.copy()
    # Limit normalization to timing and dynamics; note names retain their case.
    for delimiter in ('velocity', 'vel', 'hold', 'for', 'on', 'every'):
        if delimiter in t:
            i = t.index(delimiter)
            tail = t[i + 1:]
            if delimiter in {'velocity', 'vel'}:
                tail = numeric_tokens(tail)
                tail = [str(Fraction(x.rstrip(',')[:-1]) / 100) + (',' if x.endswith(',') else '')
                        if x.rstrip(',').endswith('%') else x for x in tail]
                t = t[:i] + ['vel'] + tail
            elif delimiter == 'every':
                aliases = {'eighth note': '1/8', 'eighth': '1/8', 'quarter note': '1/4',
                           'quarter': '1/4', 'sixteenth note': '1/16', 'sixteenth': '1/16', 'half note': '1/2'}
                phrase = ' '.join(tail).removeprefix('on ')
                t = t[:i + 1] + ([aliases[phrase]] if phrase in aliases else numeric_tokens(tail))
            else:
                if delimiter == 'on' and tail and tail[0] in {'beat', 'beats'}:
                    tail = tail[1:]
                t = t[:i + 1] + numeric_tokens(tail)
    # Convenient space-separated beat lists; fractions retain exact timing.
    if 'on' in t:
        i = t.index('on')
        j = min((t.index(k) for k in ('hold', 'vel') if k in t), default=len(t))
        positions = t[i + 1:j]
        if len(positions) > 1 and all(NUMERIC.fullmatch(x) for x in positions):
            t[i + 1:j] = [','.join(positions)]
    return t


def default_octave(pitch):
    return pitch + '4' if re.fullmatch('[a-gA-G][#b]?', pitch) else pitch
