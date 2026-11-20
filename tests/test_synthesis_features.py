"""Layered synthesis, arpeggiation, granular processing, and Synth1 conversion."""
from pathlib import Path
import io
import zipfile

import numpy as np
import pytest
from scipy.io import wavfile

from mtl import MTLError, parse_song, render_song
from mtl.dsp import _granular
from mtl.model import Instrument
from mtl.render import compile_timeline
from mtl.synth1 import convert_synth1_archive, curate_synth1_bank

ROOT = Path(__file__).resolve().parents[1]


def _arp_song(options):
    return parse_song(f'''bpm 120
sample_rate 22050
length 1 bar
instrument tone
    oscillator sine
pattern chord
    length 1 bar
    chord c4 e4 g4 on 1 hold 2 beats
track arp instrument tone pattern chord
    arpeggiator {options}
''')


def test_arpeggiator_emits_ordered_notes_at_rational_subdivisions():
    song = _arp_song('rate 1/8 mode up_down gate 1')
    events = compile_timeline(song)
    assert [event.pitch for event in events] == ['c4', 'e4', 'g4', 'e4']
    assert [event.sample for event in events] == [0, 5512, 11025, 16538]
    assert all(event.gate_seconds == pytest.approx(0.25) for event in events)


def test_arpeggiator_custom_pattern_and_invalid_chord_index():
    song = _arp_song('rate 1/8 pattern 3,1,0,2 gate 0.5')
    events = compile_timeline(song)
    assert [event.pitch for event in events] == ['g4', 'c4', 'e4']
    assert [event.sample for event in events] == [0, 5512, 16538]
    assert all(event.gate_seconds == pytest.approx(0.125) for event in events)
    with pytest.raises(MTLError, match='outside its chord'):
        compile_timeline(_arp_song('pattern 4'))


def test_granular_processing_is_stereo_safe_and_dry_mix_is_exact():
    rate = 22050
    t = np.arange(rate // 2) / rate
    mono = 0.2 * np.sin(2 * np.pi * 440 * t)
    stereo = np.column_stack((mono, mono * 0.5))
    dry = _granular(stereo, rate, Instrument('dry'), np.random.default_rng(1))
    assert np.array_equal(dry, stereo)
    inst = Instrument('grain', grain_size=0.06, grain_density=18, grain_spray=0.02,
                      grain_pitch=7, grain_mix=1)
    wet = _granular(stereo, rate, inst, np.random.default_rng(1))
    assert wet.shape == stereo.shape
    assert np.isfinite(wet).all()
    assert not np.array_equal(wet, stereo)
    assert np.corrcoef(wet[:, 0], wet[:, 1])[0, 1] > 0.999


def test_granular_insert_processes_audio_track_clips(tmp_path):
    rate = 22050
    t = np.arange(rate // 4) / rate
    source = (0.25 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    wavfile.write(tmp_path / 'source.wav', rate, source)
    song = parse_song('''sample_rate 22050
bit_depth 16
length 0.5 seconds
track texture
    audio "source.wav" at 0 seconds
    granular size 40ms density 20hz spray 15ms pitch 7 mix 0.8
''', base_path=tmp_path)
    result = render_song(song, tmp_path / 'granular.wav', quality=1)
    written_rate, audio = wavfile.read(tmp_path / 'granular.wav')
    assert result['clips'] == 1
    assert written_rate == rate
    assert audio.shape == (rate // 2, 2)
    assert np.max(np.abs(audio)) > 0


def test_hybrid_layered_preset_renders_and_examples_parse(tmp_path):
    source = '''import "mtl/presets/hybrid.mtl"
sample_rate 22050
bit_depth 16
length 1 seconds
pattern chord
    chord d4 f4 a4 on 1 hold 1 beat
track pad instrument layered_sky pattern chord
'''
    song = parse_song(source, base_path=ROOT)
    assert song.instruments['layered_sky'].layers == ('velvet_pad', 'glass_string')
    result = render_song(song, tmp_path / 'layers.wav', quality=1)
    assert result['events'] == 3
    assert (tmp_path / 'layers.wav').stat().st_size > 1000
    for path in (ROOT / 'examples/hybrid_session.mtl', ROOT / 'examples/slow_granules.mtl'):
        example = parse_song(path.read_text(encoding='utf-8'), base_path=path.parent)
        assert example.tracks
        assert any(track.arpeggiator for track in example.tracks.values())


def test_synth1_nested_zip_conversion_produces_importable_bank(tmp_path):
    patch = b'''00\r\ncolor=green\r\nver=112\r\n0,3\r\n1,64\r\n3,90\r\n9,10\r\n10,25\r\n13,0\r\n14,90\r\n15,20\r\n16,92\r\n17,25\r\n18,20\r\n26,1\r\n27,32\r\n29,24\r\n30,48\r\n31,1\r\n33,40\r\n34,24\r\n35,50\r\n44,48\r\n45,12\r\n76,1\r\n'''
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('factory/001.sy1', patch)
    source = tmp_path / 'bank.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('nested/factory.zip', nested.getvalue())
    output = tmp_path / 'converted.mtl'
    assert convert_synth1_archive(source, output) == 1
    converted = output.read_text(encoding='utf-8')
    assert 'patch: 00' not in converted and 'factory/001.sy1' not in converted
    assert not any(line.lstrip().startswith('//') for line in converted.splitlines())
    song = parse_song('import "converted.mtl"', base_path=tmp_path)
    instrument = next(iter(song.instruments.values()))
    assert instrument.name.startswith(('glass_', 'ember_', 'amber_', 'velvet_'))
    assert instrument.waveform == 'triangle'
    assert instrument.oscillator2_waveform == 'saw'
    assert instrument.oscillator2_level > 0
    assert instrument.delay > 0
    assert instrument.chorus_mix > 0


def test_synth1_curator_limits_and_anonymizes_converted_bank(tmp_path):
    source = tmp_path / 'source.mtl'
    source.write_text('''// old source comment
instrument factory_one
    oscillator saw unison 1 detune 0.001
    filter lowpass cutoff 500hz resonance 0.5
instrument factory_two
    oscillator square unison 3 detune 0.004
    filter highpass cutoff 3200hz resonance 1.2
instrument factory_three
    oscillator triangle unison 5 detune 0.008
    filter lowpass cutoff 7200hz resonance 0.7
''', encoding='utf-8')
    output = tmp_path / 'curated.mtl'
    assert curate_synth1_bank(source, output, limit=2) == 2
    text = output.read_text(encoding='utf-8')
    names = [line.split()[1] for line in text.splitlines() if line.startswith('instrument ')]
    assert len(names) == len(set(names)) == 2
    assert all(name.startswith(('ember_', 'amber_', 'velvet_')) for name in names)
    assert not any(line.lstrip().startswith('//') for line in text.splitlines())
    assert all(name not in text for name in ('factory_one', 'factory_two', 'factory_three', 'old source'))


def test_synth1_package_bank_has_two_thousand_creatively_named_presets():
    song = parse_song('import bank "synth1_bank"', base_path=ROOT, _bank=True)
    names = tuple(song.instruments)
    assert len(names) == 2000
    assert len(set(names)) == 2000
    assert all(name.rsplit('_', 1)[-1].isdigit() for name in names)
    assert not any('synth1_' in name or 'zipbank' in name for name in names)


def test_expanded_modelled_preset_banks_parse_and_hybrid_voice_renders(tmp_path):
    source = '''import bank "hybrid"
sample_rate 22050
bit_depth 16
length 1 bar
pattern chord
    chord c4 e4 g4 on 1 hold 1 beat
track keys instrument coral_mallet pattern chord
'''
    song = parse_song(source, base_path=ROOT)
    assert {'felt_keys', 'nylon_pluck', 'bright_leslie', 'vapor_sweep',
            'coral_mallet', 'violet_halo'} <= set(song.instruments)
    assert song.instruments['coral_mallet'].engine == 'layered'
    result = render_song(song, tmp_path / 'preset.wav', quality=1)
    assert result['events'] == 3


def test_instrument_search_cli_finds_names_across_bundled_presets():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, '-m', 'mtl', 'search-instruments', 'velvet', '--bank', 'hybrid'],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'velvet_pad' in result.stdout
    assert 'felt_circuit' in result.stdout


def test_instrument_search_accepts_external_preset_bank(tmp_path):
    from mtl.catalog import search_instruments

    bank = tmp_path / 'custom.mtl'
    bank.write_text('''instrument glass_wash
    oscillator sine
    filter lowpass cutoff 8000hz
''', encoding='utf-8')
    matches = search_instruments('glass synth', bank=str(bank))
    assert matches == [{'name': 'glass_wash', 'bank': 'custom.mtl', 'engine': 'synth'}]


def test_interactive_composer_outputs_editable_melodic_timeline(tmp_path):
    from mtl.interactive import InteractiveComposer

    composer = InteractiveComposer(
        'Test Texture', 108, 'C major', 'c', False, 0,
        'electronic', 'cutting_lead', 'velvet_pad', 'arch',
    )
    composer.add_section('bridge', 3)
    composer.move_section(len(composer.sections) - 1, 2)
    source = composer.source()
    song = parse_song(source, base_path=ROOT)
    events = compile_timeline(song)
    assert 'pattern lead_chorus' in source and 'section bridge' in source
    assert len(song.sections) == 8
    assert events and all(event.velocity > 0 for event in events)
    assert 'lead_verse' in composer.pattern_text()
    assert 'Total:' in composer.timeline_text()


def test_interactive_cli_creates_song_from_menu_selection(tmp_path):
    import subprocess
    import sys

    output = tmp_path / 'menu_song.mtl'
    result = subprocess.run(
        [sys.executable, '-m', 'mtl', 'interactive', str(output)],
        input='Menu Sketch\n108\n1\n1\n\n1\n1\n3\n7\n',
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'Saved ' in result.stdout
    song = parse_song(output.read_text(encoding='utf-8'), base_path=tmp_path)
    assert song.title == 'Menu Sketch'
    assert song.sections and song.patterns
    assert compile_timeline(song)


def test_synth1_converter_preserves_existing_output_on_invalid_patch(tmp_path):
    source = tmp_path / 'bad.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('bad.sy1', 'not a patch')
    output = tmp_path / 'bank.mtl'
    output.write_text('preserve', encoding='utf-8')
    with pytest.raises(MTLError, match='no Synth1 parameters'):
        convert_synth1_archive(source, output)
    assert output.read_text(encoding='utf-8') == 'preserve'
