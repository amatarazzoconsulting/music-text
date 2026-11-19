"""External assets, original synthesis models, stereo clips, and preset contracts."""
from pathlib import Path
from dataclasses import replace
import wave

import numpy as np
import pytest
from scipy.io import wavfile

from mtl import MTLError, parse_song, render_song
from mtl.audio import read_audio
from mtl.dsp import synthesize
from mtl.model import Instrument

ROOT = Path(__file__).resolve().parents[1]


def test_nested_relative_imports_and_inheritance(tmp_path):
    (tmp_path / 'bank').mkdir()
    (tmp_path / 'bank/base.mtl').write_text('instrument tone\n    oscillator saw\n    envelope attack 20ms\n')
    (tmp_path / 'bank/main.mtl').write_text('import "base.mtl"\ninstrument soft from tone\n    filter lowpass cutoff 500hz\n')
    song = parse_song('import bank "bank/main.mtl"\nimport "bank/base.mtl"\ninstrument mine from soft\n    envelope attack 80ms', base_path=tmp_path)
    assert len(song.instruments) == 3
    assert song.instruments['mine'].attack == .08
    assert song.instruments['tone'].attack == .02
    assert song.instruments['mine'].waveform == 'saw'


def test_cyclic_import_and_forbidden_song_content(tmp_path):
    (tmp_path/'a.mtl').write_text('import "b.mtl"')
    (tmp_path/'b.mtl').write_text('import "a.mtl"')
    with pytest.raises(MTLError, match='cyclic import'):
        parse_song('import "a.mtl"', base_path=tmp_path)
    (tmp_path/'a.mtl').write_text('bpm 100')
    with pytest.raises(MTLError, match='only instruments'):
        parse_song('import "a.mtl"', base_path=tmp_path)
    (tmp_path/'a.mtl').write_text('instrument x\n    unknown thing')
    with pytest.raises(MTLError, match=r'a.mtl:line 2'):
        parse_song('import "a.mtl"', base_path=tmp_path)


def test_general_midi_assignments_and_all_preset_engines_render():
    song = parse_song('import bank "general_midi"', base_path=ROOT)
    programs = {i.program for i in song.instruments.values() if i.program is not None}
    assert programs == set(range(128))
    assert song.instruments['gm_trumpet'].program == 56
    assert song.instruments['gm_violin'].program == 40
    assert song.instruments['gm_vibraphone'].program == 11
    assert song.instruments['gm_drawbar_organ'].program == 16
    for inst in song.instruments.values():
        audio = synthesize(replace(inst, reverb=0, delay=0), 'a4', .05, 22050, 3, np.random.default_rng(0))
        assert np.isfinite(audio).all() and np.max(np.abs(audio)) > .001, inst.name


def test_organ_drawbars_and_acoustic_models():
    inst = Instrument('organ', engine='organ', drawbars=(0,0,8,0,0,0,0,0,0),
                      vibrato_depth=0, percussion=0, rotary=0, sustain=1)
    a = synthesize(inst, 'a4', .8, 22050, 3, np.random.default_rng(0))
    b = synthesize(replace(inst, drawbars=(0,0,0,8,0,0,0,0,0)), 'a4', .8, 22050, 3, np.random.default_rng(0))
    f = np.fft.rfftfreq(10000, 1/22050)
    assert abs(f[np.argmax(abs(np.fft.rfft(a[3000:13000])))]-440) < 3
    assert abs(f[np.argmax(abs(np.fft.rfft(b[3000:13000])))]-880) < 3
    for engine in ['trumpet','violin','vibes']:
        audio = synthesize(Instrument(engine, engine=engine), 'a4', .8, 22050, 5, np.random.default_rng(0))
        assert np.isfinite(audio).all() and np.max(abs(audio)) > .05


@pytest.mark.parametrize('dtype', [np.int16,np.int32,np.float32,np.uint8])
def test_wav_decoding_and_resampling(tmp_path,dtype):
    rate=16000
    x=.3*np.sin(2*np.pi*440*np.arange(rate)/rate)
    if dtype==np.uint8:
        x=((x+1)*128).clip(0,255).astype(dtype)
    elif np.issubdtype(dtype,np.integer):
        x=(x*(2**(np.dtype(dtype).itemsize*8-1)-1)).astype(dtype)
    else:
        x=x.astype(dtype)
    wavfile.write(tmp_path/'in.wav',rate,x)
    audio=read_audio(tmp_path/'in.wav',22050)
    assert audio.shape==(22050,1)
    assert abs(np.max(audio)-.3)<.015
    assert np.argmax(abs(np.fft.rfft(audio[:,0]))) == 440


def read_render(path):
    with wave.open(str(path),'rb') as wav:
        return np.frombuffer(wav.readframes(wav.getnframes()),'<i2').reshape(-1,2)/32768


def test_stereo_clips_at_time_and_section_with_effects(tmp_path):
    rate=22050
    t=np.arange(rate//4)/rate
    wavfile.write(tmp_path/'stereo.wav',rate,np.column_stack([.2*np.sin(2*np.pi*440*t),np.zeros(len(t))]).astype('float32'))
    song=parse_song('''bpm 120
sample_rate 22050
bit_depth 16
section intro
    length 1 bar
section drop
    length 1 bar
track audio
    audio "stereo.wav" at 1 beats
    audio "stereo.wav" at section drop
    volume 0db
    delay time 0.3s feedback 0 mix 0.3
''',base_path=tmp_path)
    result=render_song(song,tmp_path/'out.wav')
    audio=read_render(tmp_path/'out.wav')
    assert result['clips']==2 and result['events']==0
    assert not audio[:10000].any()
    assert np.max(abs(audio[12000:16000,0]))>.05
    assert np.max(abs(audio[23000:26000,0]))>.01  # echo tail
    assert np.max(abs(audio[45000:48000,0]))>.05
    assert not audio[:,1].any()


def test_sampler_relative_to_bank_and_pitch(tmp_path):
    folder=tmp_path/'bank';folder.mkdir()
    rate=22050;t=np.arange(rate)/rate
    wavfile.write(folder/'tone.wav',rate,(.5*np.sin(2*np.pi*440*t)).astype('float32'))
    (folder/'sample.mtl').write_text('instrument sampled\n    type sampler\n    sample "tone.wav"\n    root a4\n    envelope attack 1ms decay 1ms sustain 1 release 20ms')
    song=parse_song('''import "bank/sample.mtl"
sample_rate 22050
bit_depth 16
length 1 seconds
pattern notes
    a5 on 1 hold 1 beat
track sample instrument sampled pattern notes
''',base_path=tmp_path)
    render_song(song,tmp_path/'out.wav')
    y=read_render(tmp_path/'out.wav')[1000:9000,0]
    freq=np.fft.rfftfreq(len(y),1/rate)[np.argmax(abs(np.fft.rfft(y)))]
    assert abs(freq-880)<4


def test_missing_audio_preserves_destination_and_rejects_nonfinite(tmp_path):
    output=tmp_path/'out.wav';output.write_bytes(b'preserve')
    song=parse_song('track x\n    audio "missing.wav" at 0 beats',base_path=tmp_path)
    with pytest.raises(MTLError,match='cannot read WAV'):
        render_song(song,output)
    assert output.read_bytes()==b'preserve'
    wavfile.write(tmp_path/'nan.wav',22050,np.array([np.nan],np.float32))
    with pytest.raises(MTLError,match='non-finite'):
        read_audio(tmp_path/'nan.wav',22050)


def test_cli_imports_resolve_from_input_directory(tmp_path):
    import subprocess
    import sys
    assets=tmp_path/'assets';assets.mkdir()
    (assets/'bank.mtl').write_text('instrument tone\n    oscillator sine')
    (assets/'song.mtl').write_text('import "bank.mtl"\nlength 0.1 seconds\npattern note\n    c4 on 1\ntrack a instrument tone pattern note')
    process=subprocess.run([sys.executable,'-m','mtl',str(assets/'song.mtl'),str(tmp_path/'out.wav')],cwd=tmp_path,capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    assert (tmp_path/'out.wav').is_file()
