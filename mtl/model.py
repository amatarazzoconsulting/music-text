"""Validated song representation. Musical positions use quarter-note beats."""

from dataclasses import dataclass, field
from fractions import Fraction


class MTLError(ValueError):
    """An actionable song or rendering error."""


@dataclass
class Instrument:
    name: str
    engine: str = "synth"
    waveform: str = "sine"
    attack: float = 0.005
    decay: float = 0.12
    sustain: float = 0.65
    release: float = 0.15
    cutoff: float = 12000.0
    resonance: float = 0.707
    filter_type: str = "lowpass"
    unison: int = 1
    detune: float = 0.01
    drive: float = 0.0
    reverb: float = 0.0
    reverb_seconds: float = 1.5
    delay: float = 0.0
    delay_time: float = 0.25
    feedback: float = 0.3
    lfo_rate: float = 0.0
    lfo_depth: float = 0.0
    program: int | None = None
    drawbars: tuple[float, ...] = (8, 8, 8, 0, 0, 0, 0, 0, 0)
    rotary: float = 0.8
    percussion: float = 0.15
    vibrato_rate: float = 5.5
    vibrato_depth: float = 0.003
    sample_path: str = ""
    root_pitch: str = "c4"
    hammer: float = .5
    soundboard: float = .35
    string_detune: float = .7
    pedal: float = 0
    stereo_width: float = .65
    sample_map: str = ""


@dataclass(frozen=True)
class AudioClip:
    path: str
    offset: Fraction = Fraction(0)
    section: str | None = None
    reference: tuple[str, ...] = ()
    reference_track: str = ""
    reference_note: int = 0
    reference_fraction: Fraction = Fraction(0)
    reference_delay: Fraction = Fraction(0)


@dataclass(frozen=True)
class Note:
    beat: Fraction
    duration: Fraction
    pitches: tuple[str, ...]
    velocity: float = 0.8


@dataclass
class Pattern:
    name: str
    length: Fraction
    notes: list[Note] = field(default_factory=list)
    swing: float = 50.0
    explicit_length: bool = False


@dataclass
class Track:
    name: str
    instrument: str = ""
    pattern: str = ""
    volume: float = -6.0
    pan: float = 0.0
    clips: list[AudioClip] = field(default_factory=list)
    effects: Instrument | None = None


@dataclass
class Section:
    name: str
    length: Fraction
    actions: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Automation:
    section: str
    track: str
    parameter: str
    duration: Fraction
    start: float
    end: float


@dataclass
class Song:
    title: str = "Untitled"
    bpm: float = 120.0
    beats_per_bar: Fraction = Fraction(4)
    length: Fraction | None = None
    output: str = "output.wav"
    sample_rate: int = 48000
    bit_depth: int = 24
    instruments: dict[str, Instrument] = field(default_factory=dict)
    patterns: dict[str, Pattern] = field(default_factory=dict)
    tracks: dict[str, Track] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)
    automation: list[Automation] = field(default_factory=list)
    seed: int = 0
    peak_db: float = -1.0
    timing_ms: float = 0.0
    velocity_variation: float = 0.0
    entry_summary: list[str] = field(default_factory=list)
