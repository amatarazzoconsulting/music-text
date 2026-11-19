"""Verify modulation against audible signals and independently calculated timing."""
import wave

import numpy as np
import pytest

from mtl import MTLError, parse_song, render_song
from mtl.dsp import synthesize
from mtl.model import Instrument
from mtl.render import _automation_curves, _control_value


def rms(samples):
    return np.sqrt(np.mean(np.square(samples)))


def mono(path):
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, 2)[:, 0] / 32768


def source(automation=''):
    return f'''bpm 120
sample_rate 22050
bit_depth 16
instrument tone
    oscillator sine
    filter lowpass cutoff 800hz
    envelope attack 1ms decay 1ms sustain 1 release 10ms
pattern line
    a4 on 1 hold 4 beats
track tone instrument tone pattern line volume -12db
section intro
    length 1 bar
section build
    length 2 bars
section end
    length 1 bar
{automation}
'''


def test_ramp_absolute_timing_hold_and_section_scoping():
    song = parse_song(source('''over 1 bar in build
    tone.volume from -24db to -6db
    tone.filter.cutoff from 300hz to 2000hz
'''))
    curves = _automation_curves(song)
    points = np.array([0, 1.99, 2, 3, 4, 5.99, 6, 7.0])
    values = _control_value(points, -12, curves['tone', 'volume'])
    assert values == pytest.approx([-12, -12, -24, -15, -6, -6, -12, -12])
    cutoff = _control_value(points, 800, curves['tone', 'filter.cutoff'])
    assert cutoff == pytest.approx([800, 800, 300, 1150, 2000, 2000, 800, 800])


def test_volume_automation_changes_rendered_samples_continuously(tmp_path):
    baseline = parse_song(source())
    automated = parse_song(source('''over 2 bars in build
    tone.volume from -24db to -6db
'''))
    render_song(baseline, tmp_path / 'base.wav', quality=1)
    render_song(automated, tmp_path / 'volume.wav', quality=1)
    a = mono(tmp_path / 'base.wav')
    b = mono(tmp_path / 'volume.wav')
    rate = baseline.sample_rate
    for sec in (2.5, 3.5, 5.5):
        sl = slice(int(sec * rate), int((sec + 0.1) * rate))
        measured = rms(b[sl]) / rms(a[sl])
        db = -24 + (sec + 0.05 - 2) * 18 / 4
        assert measured == pytest.approx(10 ** ((db + 12) / 20), rel=0.01)
    assert np.max(np.abs(b[int(0.2 * rate):int(1.8 * rate)] - a[int(0.2 * rate):int(1.8 * rate)])) <= 2 / 32768


def test_filter_sweep_changes_sustained_note_during_gate(tmp_path):
    base = source().replace('a4 on 1', 'a6 on 1')
    automated = base + '''over 1 bar in build
    tone.filter.cutoff from 300hz to 6000hz
'''
    render_song(parse_song(automated), tmp_path / 'sweep.wav', quality=1)
    samples = mono(tmp_path / 'sweep.wav')
    rate = 22050
    early = rms(samples[int(2.2 * rate):int(2.3 * rate)])
    late = rms(samples[int(3.6 * rate):int(3.7 * rate)])
    assert late > early * 2.5
    assert np.isfinite(samples).all()


def test_lfo_modulates_filter_and_is_song_clock_synced():
    inst = Instrument('lfo', waveform='sine', attack=.001, decay=.001, sustain=1,
                      release=.01, cutoff=1200, lfo_rate=1, lfo_depth=1100)
    rate = 22050
    long = synthesize(inst, 'a6', 2, rate, 1, np.random.default_rng(1))
    window = int(.08 * rate)
    open_level = rms(long[int(.21 * rate):int(.21 * rate) + window])
    closed_level = rms(long[int(.71 * rate):int(.71 * rate) + window])
    assert open_level > 8 * closed_level
    later = synthesize(inst, 'a6', 1, rate, 1, np.random.default_rng(1), start_sample=rate // 2)
    # After attack and filter settling, a later note observes the same absolute LFO phase.
    assert rms(later[int(.2 * rate):int(.28 * rate)]) < open_level / 8


def test_tempo_sync_resolves_forward_bpm_and_triplets():
    song = parse_song('''instrument bass
    lfo rate 1/4 target filter.cutoff depth 300hz
instrument lead
    lfo rate 1/8t target filter.cutoff depth 200hz
bpm 90
''')
    assert song.instruments['bass'].lfo_rate == pytest.approx(1.5)
    assert song.instruments['lead'].lfo_rate == pytest.approx(4.5)


@pytest.mark.parametrize('text, reason', [
    ('instrument bass\n    lfo rate 0hz target filter.cutoff depth 300hz', 'line 18'),
    ('instrument bass\n    lfo rate 1/0 target filter.cutoff depth 300hz', 'line 18'),
    ('instrument bass\n    lfo rate 4hz target pitch depth 300hz', 'line 18'),
    ('over 1 bar in missing\n    tone.volume from -6db to -3db', 'unknown section'),
    ('over 1 bar in build\n    missing.volume from -6db to -3db', 'unknown track'),
    ('over 3 bars in build\n    tone.volume from -6db to -3db', 'exceeds section length'),
    ('over 1 bar in build\n    tone.reverb.mix from 0.1 to 0.5', 'supported automation targets'),
    ('over 1 bar in build\n    tone.volume from -6db to -3db\n    tone.volume from -3db to 0db', 'duplicate automation'),
])
def test_invalid_modulation_reports_source(text, reason):
    with pytest.raises(MTLError, match=reason):
        parse_song(source(text))


def test_strong_lfo_high_resonance_remains_finite():
    inst = Instrument('extreme', waveform='saw', cutoff=2000, resonance=10,
                      lfo_rate=30, lfo_depth=10000)
    audio = synthesize(inst, 'c3', 2, 22050, 3, np.random.default_rng(0))
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) < 100


def test_volume_ramp_affects_delay_tail_crossing_section_boundary(tmp_path):
    base = '''bpm 120
sample_rate 22050
bit_depth 16
instrument echo
    oscillator sine
    envelope attack 1ms decay 1ms sustain 1 release 50ms
    delay time 0.6s feedback 0 mix 1
pattern line
    a4 on 1 hold 1 beat
track echo instrument echo pattern line volume -12db
section intro
    length 1 beat
section tail
    length 1 beat
    remove echo
'''
    ramp = '''over 1 beat in tail
    echo.volume from -12db to -24db
'''
    render_song(parse_song(base), tmp_path / 'base.wav', quality=1)
    render_song(parse_song(base + ramp), tmp_path / 'ramp.wav', quality=1)
    a, b = mono(tmp_path / 'base.wav'), mono(tmp_path / 'ramp.wav')
    rate = 22050
    for sec in (0.7, 0.9):
        window = slice(round(sec * rate), round((sec + .05) * rate))
        actual = rms(b[window]) / rms(a[window])
        expected_db = -12 * ((sec + .025 - .5) / .5)
        assert actual == pytest.approx(10 ** (expected_db / 20), rel=.01)


def test_filter_automation_preserves_unaffected_section_audio(tmp_path):
    base = source().replace('a4 on 1', 'a6 on 1')
    sweep = '''over 1 bar in build
    tone.filter.cutoff from 300hz to 6000hz
'''
    render_song(parse_song(base), tmp_path / 'base.wav', quality=3)
    render_song(parse_song(base + sweep), tmp_path / 'sweep.wav', quality=3)
    a, b = mono(tmp_path / 'base.wav'), mono(tmp_path / 'sweep.wav')
    # Before the build the automated filter equals the configured cutoff.
    assert np.max(np.abs(a[2205:39690] - b[2205:39690])) <= 2 / 32768
