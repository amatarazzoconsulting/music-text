"""Compact input, automatic accompaniment, and recorded-piano playback contracts."""
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from mtl import parse_song, render_song, MTLError
from mtl.dsp import synthesize
from mtl.render import compile_timeline
from mtl.piano import piano_image


def test_requested_compact_phrase_and_defaults():
    song = parse_song('panio c f g2s repat four bars')
    assert song.bpm == 120 and song.length == 24
    assert set(song.tracks) == {'panio', 'auto_drums'}
    assert song.entry_summary and len(compile_timeline(song)) > 30
    notes = song.patterns['panio'].notes
    assert notes[1].pitches == ('c4',) and notes[2].pitches == ('f4',)
    assert notes[3].pitches == ('g4',) and notes[3].duration == Fraction(18, 5)
    assert notes[-1].beat == 20


@pytest.mark.parametrize('style', ['jazz','country','reggae','techno','house','rock','basic','dubstep'])
def test_styles_generate_different_grooves_and_valid_arrangements(style):
    song = parse_song('c f g\ndrums ' + style)
    events = compile_timeline(song)
    assert song.length == 24 and all(0 <= e.sample < 576000 for e in events)
    body = [n for n in song.patterns['auto_drums'].notes if 4 <= n.beat < 8]
    kicks = [n.beat - 4 for n in body if n.pitches == ('kick',)]
    if style == 'reggae': assert kicks == [2]
    if style == 'techno': assert kicks == [0,1,2,3]
    if style == 'jazz': assert any(n.beat.denominator == 3 for n in body)
    assert any(n.pitches == ('tom',) for n in song.patterns['auto_drums'].notes)


def test_child_notes_solfege_and_controls():
    song = parse_song('do re mi fa sol\ndrums off\nintro off\nending off\nrepeat two bars')
    assert song.length == 8 and set(song.tracks) == {'piano'}
    assert [n.pitches[0] for n in song.patterns['piano'].notes[:5]] == ['c4','d4','e4','f4','g4']
    assert parse_song('c f g').entry_summary
    assert not parse_song('pattern p\n    c4 on 1\ntrack keys instrument piano pattern p').entry_summary


def test_generated_bass_chords_progression_and_bass_instrument_monophony():
    song = parse_song('piano c f g\ngenerate bass and chords\ndrums jazz')
    assert {'auto_bass','auto_chords'} <= set(song.tracks)
    assert all(len(n.pitches) == 1 and n.pitches[0].endswith('2') for n in song.patterns['auto_bass'].notes)
    assert all(len(n.pitches) == 3 for n in song.patterns['auto_chords'].notes)
    bass = parse_song('bass chords c f g repeat four bars\ngenerate bass')
    assert 'auto_bass' not in bass.tracks
    assert all(len(n.pitches) == 1 and n.pitches[0].endswith('2') for n in bass.patterns['bass'].notes)
    generated = parse_song('generate progression and bass and chords\nkey d minor')
    assert generated.patterns['auto_chords'].notes[0].pitches == ('d3','f3','a3')


def test_compact_tempo_reproducibility_bounds_and_explicit_mtl():
    source = 'piano c f g 2s repeat two bars\ntempo ninety bpm\nseed 12'
    a, b = parse_song(source), parse_song(source)
    assert a.bpm == 90 and a.patterns == b.patterns
    assert a.patterns['piano'].notes[1].duration == Fraction(27,10)
    with pytest.raises(MTLError, match='1..256'): parse_song('c f g repeat 1000000 bars')
    assert not parse_song('piano\n    notes c d e').entry_summary


def write_map(tmp_path, loop=False):
    rate = 22050
    t = np.arange(rate) / rate
    for name, frequency in [('soft',440),('hard',880)]:
        audio = .5 * np.sin(2 * np.pi * frequency * t)
        wavfile.write(tmp_path/(name+'.wav'), rate, np.column_stack([audio,np.zeros(rate)]).astype('float32'))
    data = {'zones':[{'root':'a4','low':'a3','high':'a5','velocity':v,'files':[name+'.wav'], **({'loop':[.1,.8]} if loop else {})} for v,name in [(0,'soft'),(1,'hard')]]}
    (tmp_path/'piano.json').write_text(json.dumps(data))
    return parse_song('instrument grand\n    type multisampler\n    sample_map "piano.json"\n    envelope attack 1ms decay 1ms sustain 1 release 50ms',base_path=tmp_path).instruments['grand']


def test_multisample_velocity_interpolation_stereo_pitch_and_loops(tmp_path):
    inst = write_map(tmp_path, loop=True)
    def voice(v, pitch='a4', gate=1.5):
        return synthesize(inst,pitch,gate,22050,3,np.random.default_rng(0),velocity=v)
    soft, hard, blend = voice(0), voice(1), voice(.5)
    assert soft.shape[1] == 2 and not soft[:,1].any()
    assert np.allclose(blend, .5 * (soft+hard), atol=1e-6)
    assert np.mean(soft[26000:30000,0]**2) > .001
    pitched = voice(0, 'a5', .3)[1000:6000,0]
    assert abs(np.fft.rfftfreq(len(pitched),1/22050)[np.argmax(abs(np.fft.rfft(pitched)))]-880)<5
    with pytest.raises(MTLError,match='covers'): voice(1,'c7')


def test_multisample_errors_and_source_overwrite_protection(tmp_path):
    inst = write_map(tmp_path)
    song = parse_song('instrument grand\n    type multisampler\n    sample_map "piano.json"\npattern p\n    a4 on 1\ntrack piano instrument grand pattern p', base_path=tmp_path)
    before = (tmp_path/'soft.wav').read_bytes()
    with pytest.raises(MTLError,match='overwrite'): render_song(song,tmp_path/'soft.wav')
    assert (tmp_path/'soft.wav').read_bytes() == before
    (tmp_path/'piano.json').write_text('{"zones":[]}')
    with pytest.raises(MTLError,match='zones'): synthesize(inst,'a4',.1,22050,3,np.random.default_rng(0))
    with pytest.raises(MTLError,match='requires sample_map'): parse_song('instrument x\n    type multisampler')


def test_piano_stereo_register_and_pedal():
    inst = parse_song('instrument piano\n    pedal 0.6').instruments['piano']
    dry = synthesize(replace(inst,pedal=0,reverb=0),'a4',.2,22050,3,np.random.default_rng(0))
    wet = synthesize(replace(inst,reverb=0),'a4',.2,22050,3,np.random.default_rng(0))
    assert len(wet)>len(dry) and np.sum(wet[len(dry):]**2)>.001
    a = piano_image(dry,110,22050,.8)
    b = piano_image(dry,1760,22050,.8)
    assert np.sum(a[:,0]**2)>np.sum(a[:,1]**2)
    assert np.sum(b[:,1]**2)>np.sum(b[:,0]**2)


def test_spoken_suffix_structured_style_and_short_sample_loop(tmp_path):
    assert 'jazz' in parse_song('piano c f g repeat two bars with jazz drums').entry_summary[1]
    song = parse_song('piano\n    c4 for four beats\ndrums reggae')
    assert song.patterns['__drums'].notes
    inst = write_map(tmp_path, loop=True)
    audio = synthesize(inst,'a4',.05,22050,3,np.random.default_rng(0))
    assert len(audio) == 2205 and np.max(abs(audio)) > .01


@pytest.mark.parametrize('text', ['piano c f g repeat zero bars', 'piano c f g repeat 1/0 bars', 'piano c0s', 'piano c f g repeat nonsense'])
def test_invalid_compact_numbers_are_user_errors(text):
    with pytest.raises(MTLError):
        parse_song(text)
