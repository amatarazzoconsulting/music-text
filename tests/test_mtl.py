"""Contract tests cover timing, synthesis, PCM encoding, and CLI behavior."""

import hashlib
from dataclasses import replace
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import periodogram

from mtl import MTLError, parse_song, render_song
from mtl.dsp import envelope, frequency, oscillator, synthesize
from mtl.model import Instrument
from mtl.render import _pcm, compile_timeline, sample_at

ROOT = Path(__file__).resolve().parents[1]


def read_pcm(path):
    with wave.open(str(path), 'rb') as wav:
        width = wav.getsampwidth()
        payload = wav.readframes(wav.getnframes())
        metadata = (wav.getnframes(), wav.getframerate(), wav.getnchannels(), width)
    if width == 2:
        audio = np.frombuffer(payload, '<i2').astype(float) / 32768
    else:
        b = np.frombuffer(payload, np.uint8).reshape(-1, 3).astype(np.int32)
        n = b[:, 0] | b[:, 1] << 8 | b[:, 2] << 16
        audio = ((n ^ 0x800000) - 0x800000) / 8388608
    return metadata, audio.reshape(-1, 2)


def melodic(extra='', pitch='a4'):
    return f'''song "Tone"
bpm 120
length 1 seconds
{extra}
pattern tone
    {pitch} on 1 hold 1 beat
track tone instrument sine pattern tone volume -6db
'''


def test_readme_first_beat_loops():
    # This is the README's original example, including its implicit defaults.
    song = parse_song('''song "My First Beat"
bpm 90
drums
    kick on 1 and 3
    snare on 2 and 4
    hihat every 1/8
output "my_beat.wav"
''')
    events = compile_timeline(song)
    assert song.length == 16
    assert len(events) == 48
    assert sum(e.pitch == 'kick' for e in events) == 8
    assert sorted(e.sample for e in events if e.pitch == 'snare')[:2] == [32000, 96000]


def test_chords_duration_and_forward_references():
    song = parse_song('''track keys instrument piano pattern chords
pattern chords
    play c minor for 4 beats
    play ab major for 4 beats
length 2 bars
''')
    assert song.patterns['chords'].length == 8
    assert song.patterns['chords'].notes[0].pitches == ('c3', 'd#3', 'g3')
    assert song.patterns['chords'].notes[1].pitches == ('g#3', 'c4', 'd#4')
    assert len(compile_timeline(song)) == 6


def test_fractional_timing_has_no_accumulated_rounding():
    song = parse_song('''bpm 137
length 40 bars
pattern beat
    hihat every 1/8t
track drums instrument drums pattern beat
''')
    events = compile_timeline(song)
    for i, event in enumerate(events):
        assert event.sample == round(Fraction(i, 3) * 60 * 48000 / 137)


def test_meter_and_tempo_declaration_order():
    song = parse_song('''length 2 bars
pattern beat
    kick every 1/4
track drums instrument drums pattern beat
time_signature 6/8
bpm 90
''')
    assert song.length == 6
    assert song.patterns['beat'].length == 3
    assert len(compile_timeline(song)) == 6
    assert sample_at(song.length, song) == 192000


def test_section_add_remove_and_restart():
    song = parse_song('''pattern note
    c4 on 1 hold 4 beats
track a instrument sine pattern note
track b instrument bell pattern note
section intro
    length 1 bar
    a only
section verse
    length 1 bar
    add b
section end
    length 1 bar
    remove a
''')
    events = compile_timeline(song)
    assert [(e.sample, e.track) for e in events] == [(0, 'a'), (96000, 'a'), (96000, 'b'), (192000, 'b')]
    assert all(e.gate_seconds == 2 for e in events)


def test_swing_delays_only_offbeat_eighth():
    song = parse_song('''length 1 bar
pattern beat
    swing 75
    hihat every 1/8
track drums instrument drums pattern beat
''')
    assert [e.sample for e in compile_timeline(song)][:4] == [0, 18000, 24000, 42000]


@pytest.mark.parametrize('source, message', [
    ('bpm 0', 'line 1'), ('bpm nan', 'line 1'),
    ('bpm 120 extra', 'line 1'), ('length -2 bars', 'line 1'),
    ('time_signature 4/0', 'line 1'),
    ('instrument test\n    type sampler', 'line 2'),
    ('instrument test\n    oscillator saw mystery 2', 'line 2'),
    ('instrument test\n    envelope sustain 2', 'line 2'),
    ('pattern x\n    c4 on 0', 'line 2'),
    ('pattern x\n    length 1 bar\n    c4 on 5', 'line 3'),
    ('pattern x\n    snare every 0', 'line 2'),
    ('pattern x\n    x4 on 1', 'line 2'),
    ('track a instrument missing pattern missing', 'unknown pattern'),
    ('pattern x\n    c4 on 1\ntrack a instrument missing pattern x', 'unknown instrument'),
    ('pattern x\n    c4 on 1\ntrack a instrument drums pattern x', 'drum patterns'),
    ('master\n    loudness -14lufs', 'line 2'),
    ('song "Oops"\n    bpm 100', 'line 1'),
    ('section intro\n    add unknown', 'unknown track'),
])
def test_invalid_or_unsupported_instructions(source, message):
    with pytest.raises(MTLError, match=message):
        parse_song(source)


def test_quotes_comments_accidentals_and_metadata():
    song = parse_song('''song "https://example.test/#song"
key f minor
genre electronic house
pattern line
    F#3 Bb3 b3 on 1 // three notes
track lead instrument sine pattern line
''')
    assert song.title == 'https://example.test/#song'
    assert len(compile_timeline(song)) == 12
    assert frequency('A4') == 440
    assert frequency('b3') == frequency('B3')
    assert frequency('Bb3') == frequency('a#3')


def test_release_is_continuous_when_note_ends_during_attack():
    inst = Instrument('test', attack=0.5, release=0.1)
    env = envelope(1200, 100, inst, 10000)
    assert env[0] == 0 and env[-1] == 0
    assert abs(env[100] - env[99]) < 0.001
    assert np.all(np.diff(env[100:]) <= 0)


def test_sine_pitch_and_saw_alias_reduction():
    rate, freq, count = 48000, 5000, 48000
    _, power = periodogram(oscillator('sine', 440, count, rate), rate)
    assert np.argmax(power) == 440
    naive = 2 * (np.arange(count) * freq / rate % 1) - 1
    corrected = oscillator('saw', freq, count, rate)
    allowed = np.zeros(count // 2 + 1, dtype=bool)
    allowed[0] = True
    allowed[np.arange(freq, rate // 2, freq)] = True
    _, before = periodogram(naive, rate)
    _, after = periodogram(corrected, rate)
    assert after[~allowed].sum() < before[~allowed].sum() * 0.15


@pytest.mark.parametrize('engine', ['synth', 'pluck', 'bell', 'fm', 'drum'])
def test_instruments_finite_and_have_fades(engine):
    inst = Instrument('kick' if engine == 'drum' else 'test', engine=engine, waveform='saw')
    audio = synthesize(inst, 'a4', 0.2, 22050, 5, np.random.default_rng(0))
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) > 0.01
    assert abs(audio[-1]) < 0.001


@pytest.mark.parametrize('bits', [16, 24])
def test_wav_format_pitch_determinism_and_pan(tmp_path, bits):
    song = parse_song(melodic(f'sample_rate 22050\nbit_depth {bits}'))
    song.tracks['tone'].pan = -1
    one, two = tmp_path / 'one.wav', tmp_path / 'two.wav'
    result = render_song(song, one)
    render_song(song, two)
    meta, audio = read_pcm(one)
    assert meta == (22050, 22050, 2, bits // 8)
    assert hashlib.sha256(one.read_bytes()).digest() == hashlib.sha256(two.read_bytes()).digest()
    assert np.max(np.abs(audio[:, 1])) == 0
    assert 0.02 < np.max(np.abs(audio[:, 0])) < 0.9
    assert result['events'] == 1
    # Estimate cycles in the sustained portion, independently of oscillator code.
    segment = audio[2205:8820, 0]
    crossings = np.count_nonzero((segment[:-1] <= 0) & (segment[1:] > 0))
    assert abs(crossings / (len(segment) / 22050) - 440) < 5


def test_pcm_signed_extremes():
    for bits in [16, 24]:
        raw = _pcm(np.array([[-1., 1.], [0., 0.]]), bits, np.random.default_rng(0))
        width = bits // 8
        decoded = [int.from_bytes(raw[i:i + width], 'little', signed=True) for i in range(0, len(raw), width)]
        assert decoded == [-2**(bits - 1), 2**(bits - 1) - 1, 0, 0]


def test_silence_and_exact_truncation(tmp_path):
    song = parse_song('song "Empty"\nlength 0.1 seconds\nsample_rate 22050')
    result = render_song(song, tmp_path / 'silence.wav')
    _, audio = read_pcm(result['path'])
    assert len(audio) == 2205 and not audio.any()


def test_peak_ceiling_and_relative_volume(tmp_path):
    loud = parse_song(melodic())
    loud.tracks['tone'].volume = 12
    for i in range(4):
        loud.tracks[f'loud{i}'] = replace(loud.tracks['tone'], name=f'loud{i}')
    result = render_song(loud, tmp_path / 'loud.wav')
    _, audio = read_pcm(result['path'])
    assert np.max(np.abs(audio)) == pytest.approx(10**(-1 / 20), abs=2 / 8388608)
    quiet = parse_song(melodic())
    quieter = parse_song(melodic())
    quieter.tracks['tone'].volume -= 6
    a = render_song(quiet, tmp_path / 'a.wav')['peak']
    b = render_song(quieter, tmp_path / 'b.wav')['peak']
    assert b / a == pytest.approx(10**(-6 / 20), rel=1e-5)


def test_reverb_and_delay_extend_release():
    dry = Instrument('test', release=0.02)
    wet = Instrument('test', release=0.02, reverb=0.3, delay=0.2)
    a = synthesize(dry, 'c4', 0.1, 22050, 3, np.random.default_rng(0))
    b = synthesize(wet, 'c4', 0.1, 22050, 3, np.random.default_rng(0))
    assert len(b) > len(a)
    assert np.sum(b[len(a):]**2) > 0.001


def test_cli_and_existing_destination_preserved_on_error(tmp_path):
    good = subprocess.run([sys.executable, '-m', 'mtl', str(ROOT / 'examples/first_beat.mtl'), str(tmp_path / 'beat.wav'), '--sample_rate', '22050', '--bit_depth', '16'], capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    output = tmp_path / 'beat.wav'
    original = output.read_bytes()
    invalid = tmp_path / 'invalid.mtl'
    invalid.write_text('instrument piano\n    type imaginary')
    bad = subprocess.run([sys.executable, '-m', 'mtl', str(invalid), str(output)], capture_output=True, text=True)
    assert bad.returncode == 1 and 'line 2' in bad.stderr and 'Traceback' not in bad.stderr
    assert output.read_bytes() == original


def test_humanization_is_reproducible_and_bounded():
    song = parse_song('''length 2 bars
seed 42
pattern beat
    kick every 1/8
track drums instrument drums pattern beat
humanize all tracks
    timing ±5ms
    velocity ±5%
''')
    events = compile_timeline(song)
    assert events == compile_timeline(song)
    assert all(abs(e.sample - i * 12000) <= 240 for i, e in enumerate(events))
    assert all(0.75 <= e.velocity <= 0.85 for e in events)



def test_unrepresentable_pitch_rejected_before_output(tmp_path):
    song = parse_song(melodic('sample_rate 22050', 'g9'))
    with pytest.raises(MTLError, match='Nyquist'):
        render_song(song, tmp_path / 'invalid.wav')
    assert not (tmp_path / 'invalid.wav').exists()


def test_short_empty_pattern_rejected_without_looping(tmp_path):
    song = parse_song('length 1 bar\npattern empty\n    length 1/10000000 beats\ntrack tone instrument sine pattern empty')
    with pytest.raises(MTLError, match='one million pattern repeats'):
        render_song(song, tmp_path / 'invalid.wav')
