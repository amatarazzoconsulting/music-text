import subprocess
import sys
from fractions import Fraction

from mtl import parse_song
from mtl.midi import midi_to_mtl
from mtl.render import compile_timeline


def _vlq(value):
    encoded = [value & 0x7f]
    value >>= 7
    while value:
        encoded.insert(0, (value & 0x7f) | 0x80)
        value >>= 7
    return bytes(encoded)


def _track(events):
    payload = b"".join(events)
    return b"MTrk" + len(payload).to_bytes(4, "big") + payload


def _midi():
    tempo = _track([
        b"\x00\xff\x51\x03\x07\xa1\x20",
        b"\x83\x60\xff\x51\x03\x0f\x42\x40",
        b"\x00\xff\x58\x04\x03\x02\x18\x08",
        b"\x83\x60\xff\x2f\x00",
    ])
    notes = _track([
        b"\x00\xc0\x28",
        b"\x00\x90\x3c\x40",
        b"\x83\x60\x80\x3c\x00",
        b"\x00\xc0\x00",
        b"\x00\x90\x40\x7f",
        b"\x83\x60\x80\x40\x00",
        b"\x00\xff\x2f\x00",
    ])
    drums = _track([
        b"\x00\x99\x24\x64",
        b"\x83\x60\x89\x24\x00",
        b"\x00\xff\x2f\x00",
    ])
    header = b"MThd" + (6).to_bytes(4, "big") + b"\x00\x01\x00\x03\x01\xe0"
    return header + tempo + notes + drums


def test_midi_conversion_preserves_note_timing_programs_and_drums():
    source = midi_to_mtl(_midi(), "Tempo Changes")
    song = parse_song(source)
    events = compile_timeline(song)

    assert song.bpm == 120
    assert song.beats_per_bar == 3
    assert song.length == 3
    assert len(events) == 3
    assert sorted((event.sample, event.track) for event in events) == [
        (0, "midi_t2_ch1_p40"),
        (0, "midi_t3_ch10_p0"),
        (24000, "midi_t2_ch1_p0"),
    ]
    assert song.tracks["midi_t2_ch1_p40"].instrument == "gm_violin"
    assert song.patterns["midi_t2_ch1_p40_notes"].notes[0].duration == Fraction(1)
    assert song.patterns["midi_t2_ch1_p0_notes"].notes[0].duration == Fraction(2)
    assert song.tracks["midi_t3_ch10_p0"].instrument == "drums"


def test_convert_midi_cli_writes_default_mtl_path(tmp_path):
    source = tmp_path / "example.mid"
    source.write_bytes(_midi())
    process = subprocess.run(
        [sys.executable, "-m", "mtl", "convert-midi", str(source)],
        capture_output=True,
        text=True,
    )

    output = tmp_path / "example.mtl"
    assert process.returncode == 0, process.stderr
    assert output.is_file()
    assert parse_song(output.read_text(encoding="utf-8")).title == "example"


def test_invalid_midi_fails_cleanly_without_output(tmp_path):
    source = tmp_path / "invalid.mid"
    source.write_bytes(b"not MIDI")
    process = subprocess.run(
        [sys.executable, "-m", "mtl", "convert-midi", str(source)],
        capture_output=True,
        text=True,
    )

    assert process.returncode == 1
    assert "not a valid Standard MIDI File" in process.stderr
    assert "Traceback" not in process.stderr
    assert not source.with_suffix(".mtl").exists()
