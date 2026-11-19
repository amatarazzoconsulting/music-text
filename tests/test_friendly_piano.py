"""Human entry contracts, structural timing, and independent piano signal checks."""
from dataclasses import replace
from fractions import Fraction
import subprocess
import sys

import numpy as np
import pytest
from scipy.io import wavfile
from scipy.signal import periodogram

from mtl import MTLError, parse_song, render_song
from mtl.dsp import synthesize
from mtl.render import compile_timeline


def test_bare_instruments_and_unindented_entry():
    song = parse_song('''tempo about ninety bpm
length two bars
Panio
notes c d e g
volume -8 dB
pan slightly left
violin
    c5 for two beats
    d5 for two beats
''')
    assert song.bpm == 90 and song.length == 8
    assert set(song.tracks) == {'panio', 'violin'}
    piano = song.tracks['panio']
    assert piano.volume == -8 and piano.pan == -.25
    assert song.instruments[piano.instrument].engine == 'piano'
    notes = song.patterns[piano.pattern].notes
    assert [n.beat for n in notes] == [0, 1, 2, 3]
    assert [n.pitches for n in notes] == [('c4',), ('d4',), ('e4',), ('g4',)]
    assert song.instruments['violin'].program == 40


def test_default_track_and_multiword_gm_names():
    song = parse_song('''track keys
    instrument acoustic grand piano
    chord c e g for a beat
    c5 for one and a half beats
    d5 for half a beat
''')
    assert song.instruments['acoustic grand piano'].program == 0
    assert song.patterns[song.tracks['keys'].pattern].notes[1].duration == Fraction(3, 2)
    assert song.patterns[song.tracks['keys'].pattern].notes[2].duration == Fraction(1, 2)
    assert parse_song('pattern phrase\n    c4 on 1').tracks['phrase'].instrument == 'piano'
    assert parse_song('c4 d4 e4').tracks['piano'].instrument == 'piano'


def test_fuzzy_numbers_beats_dynamics_and_clock():
    song = parse_song('''bpm 100bpm
length 0:30
piano
    envelope attack 2 ms decay 0,1 s sustain 1 release 300 ms
    c on beats one two three hold 1½ beats velocity 80 percent
''')
    assert song.length == 50
    inst = next(i for n, i in song.instruments.items() if n.startswith('__entry'))
    assert inst.attack == .002 and inst.decay == .1 and inst.release == .3
    notes = song.patterns[song.tracks['piano'].pattern].notes
    assert [n.beat for n in notes] == [0, 1, 2]
    assert all(n.duration == Fraction(3, 2) and n.velocity == .8 for n in notes)


def test_drum_grids_and_starter_patterns():
    song = parse_song('''drums
    kick x...x...x...x...
    snare on two and four
    hihat every eighth note
''')
    p = song.patterns['__drums']
    assert [n.beat for n in p.notes if n.pitches == ('kick',)] == [0, 1, 2, 3]
    assert len(p.notes) == 14
    assert len(parse_song('drums house').patterns['__drums'].notes) == 14


def test_relative_notes_forward_tracks_and_previous():
    song = parse_song('''length 2 bars
track answer
    instrument vibraphone
    e5 at 50% of piano note 1 hold half a beat
    g5 after previous note hold 1 beat
    c6 at end of piano note 2 plus half a beat
piano
    c4 for two beats
    d4 for one beat
''')
    notes = song.patterns[song.tracks['answer'].pattern].notes
    assert [n.beat for n in notes] == [1, Fraction(3, 2), Fraction(7, 2)]
    assert song.instruments['vibraphone'].program == 11
    event = next(e for e in compile_timeline(song) if e.track == 'answer' and e.pitch == 'e5')
    assert event.sample == 24000


def test_relative_cycles_missing_notes_and_explicit_length():
    for source, error in [
        ('piano\n    c4 after previous note', 'earlier note'),
        ('piano\n    c4 after note 2\n    d4 after note 1', 'cyclic'),
        ('piano\n    c4 at 120% of note 2\n    d4', '0..100'),
        ('piano\n    c4 after violin note 9', 'unknown reference'),
        ('piano\n    length 1 bar\n    c4 on 4 hold 2 beats\n    d4 after previous note', 'outside'),
        ('piano\n    c4 at start of note 2 minus two beats\n    d4', 'before'),
    ]:
        with pytest.raises(MTLError, match=error):
            parse_song(source)


def test_audio_relative_to_note_completion(tmp_path):
    rate = 22050
    wavfile.write(tmp_path / 'hit.wav', rate, (.2 * np.sin(2 * np.pi * 750 * np.arange(2205) / rate)).astype('float32'))
    song = parse_song('''sample_rate 22050
bit_depth 16
length 1 bar
piano
    c4 for two beats
track hit
    audio "hit.wav" at halfway through piano note 1
    volume 0db
''', base_path=tmp_path)
    assert song.tracks['hit'].clips[0].offset == 1
    # Isolate the audio track to verify its actual trigger in the WAV.
    pattern = song.patterns[song.tracks['piano'].pattern]
    pattern.notes = [replace(n, velocity=0) for n in pattern.notes]
    result = render_song(song, tmp_path / 'out.wav')
    _, audio = wavfile.read(tmp_path / 'out.wav')
    assert result['clips'] == 1 and not audio[:rate // 2].any()
    assert np.max(abs(audio[rate // 2:rate // 2 + 2205])) > 1000


def test_gm_names_default_and_custom_instruments_win():
    song = parse_song('''instrument violin
    oscillator square
    type synth
pattern p
    a4 on 1
track solo instrument violin pattern p
track brass instrument gm_trumpet pattern p
''')
    assert song.instruments['violin'].engine == 'synth'
    assert song.instruments['gm_trumpet'].program == 56
    with pytest.raises(MTLError, match='unsupported instruction'):
        parse_song('some completely unknown words')
    with pytest.raises(MTLError, match='unknown instrument'):
        parse_song('pattern p\n    c4 on 1\ntrack t instrument pianissimo_xyz pattern p')


def test_piano_tuning_decay_velocity_and_registers():
    inst = replace(parse_song('piano\n    a4').instruments['piano'], reverb=0, delay=0, cutoff=20000)
    def voice(pitch='a4', velocity=.8, seed=0, gate=2):
        return synthesize(inst, pitch, gate, 22050, 3, np.random.default_rng(seed), velocity=velocity)
    a = voice()
    assert np.array_equal(a, voice()) and not np.array_equal(a, voice(seed=1))
    assert np.isfinite(a).all() and abs(a[-1]) < .001
    f, p = periodogram(a[2205:22050], 22050)
    assert abs(f[np.argmax(p)] - 440) < 2
    assert np.mean(a[2000:6000]**2) > 2 * np.mean(a[33000:37000]**2)
    # Compare normalized spectral energy: loud notes change timbre, not only gain.
    f, soft = periodogram(voice(velocity=.15)[:10000], 22050)
    _, hard = periodogram(voice(velocity=1)[:10000], 22050)
    assert hard[f > 2500].sum() / hard.sum() > 2 * soft[f > 2500].sum() / soft.sum()
    for pitch in ('a0', 'c4', 'c8'):
        y = voice(pitch, gate=.2)
        assert np.isfinite(y).all() and np.max(abs(y)) > .005


def test_piano_release_and_detuned_strings():
    inst = replace(parse_song('piano\n    c4').instruments['piano'], reverb=0)
    dry = synthesize(replace(inst, string_detune=0), 'a4', .8, 22050, 3, np.random.default_rng(0))
    detuned = synthesize(replace(inst, string_detune=7), 'a4', .8, 22050, 3, np.random.default_rng(0))
    assert not np.allclose(dry, detuned)
    assert np.mean(dry[-1000:]**2) < np.mean(dry[10000:11000]**2) * .02


def test_forward_references_extend_each_implicit_pattern():
    song = parse_song('''track a
    c4 after b note 2
track b
    c4 for 5 beats
    d4 after previous note
''')
    assert song.patterns[song.tracks['a'].pattern].length == 8
    assert song.patterns[song.tracks['b'].pattern].length == 8
    assert any(e.track == 'b' and e.sample == 120000 for e in compile_timeline(song))


def test_cli_instrument_list_and_inferred_defaults(tmp_path):
    process = subprocess.run([sys.executable, '-m', 'mtl', '--list-instruments'], capture_output=True, text=True)
    assert process.returncode == 0 and len(process.stdout.splitlines()) == 128
    assert 'acoustic grand piano' in process.stdout and '127  gunshot' in process.stdout
    path = tmp_path / 'easy.mtl'
    path.write_text('piano')
    process = subprocess.run([sys.executable, '-m', 'mtl', str(path), '--check'], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert '16 scheduled notes' in process.stdout and 'piano (piano)' in process.stdout
    assert not (tmp_path / 'output.wav').exists()


def test_audio_note_reference_follows_section_entry_and_clamped_gate():
    from mtl.render import _clip_events
    song = parse_song('''track clip
    audio "hit.wav" at end of piano note 1
piano
    c4 for eight beats
section silence
    length one bar
    only clip
section entry
    length one bar
    add piano
''')
    events = compile_timeline(song)
    assert events[0].sample == 96000
    assert events[0].gate_seconds == 2  # eight-beat gate cut at section end
    assert _clip_events(replace(song, length=12), events)[0][0] == 192000
    with pytest.raises(MTLError, match='never scheduled'):
        _clip_events(song, [])


def test_audio_reference_offset_is_measured_from_actual_late_note():
    from mtl.render import _clip_events
    song = parse_song('''piano
    c4 for two beats
track cue
    audio "hit.wav" at end of piano note one minus three beats
section intro
    only cue
    length one bar
section entry
    add piano
    length one bar
''')
    assert _clip_events(song, compile_timeline(song))[0][0] == 72000


def test_existing_examples_and_spaced_beat_velocity_lists_remain_valid():
    from pathlib import Path
    song = parse_song('''drums
    kick on 1, 2, 3, 4 vel 0.9, 0.75, 0.85, 0.75
''')
    assert [n.beat for n in song.patterns['__drums'].notes] == [0, 1, 2, 3]
    assert [n.velocity for n in song.patterns['__drums'].notes] == [.9, .75, .85, .75]
    for path in (Path(__file__).resolve().parents[1] / 'examples').glob('*.mtl'):
        parse_song(path.read_text(), base_path=path.parent)
