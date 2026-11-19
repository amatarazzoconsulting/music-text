<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e85e7a6b08948c624a1b8240fe5b4c378f58d36f61f0d7f30759dcf08844b13e -->

# Python renderer guide

## Install and run

Python 3.11 or later is required. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
mtl examples/night_drive.mtl night_drive.wav
# Equivalent without the installed console command:
python -m mtl examples/night_drive.mtl night_drive.wav
```

The positional output overrides `output "file.wav"` or `render to "file.wav"`. Paths are relative to the current working directory. WAV is the supported format. Errors return status 1 and preserve an existing destination. CLI argument errors return status 2. Rendering a file does not play it automatically.

Options: `--quality 1..5`, `--sample-rate` / `--sample_rate` (22050, 44100, 48000, 88200, 96000), `--bit-depth` / `--bit_depth` (16 or 24), `--version`. Defaults are quality 3, 48000 Hz, 24 bits. Quality 1–2 uses native rate, 3–4 uses 2× oversampling, 5 uses 4×; paired settings currently share an algorithm. This preserves the draft CLI shape without claiming five different engines.

## Write a song

Use lowercase keywords, one instruction per line, and indentation for blocks. Names are case sensitive; quote names containing spaces. Note letters can be uppercase or lowercase. `//` starts a comment outside a quoted string; `#` belongs to sharp note names. Forward references between tracks, patterns and instruments work.

```text
song "Small Song"
bpm 100
length 8 bars
output "small.wav"

instrument bass
    oscillator saw
    warm and slightly distorted
    filter lowpass cutoff 800hz resonance 0.7
    envelope attack 3ms decay 80ms sustain 0.5 release 120ms

pattern notes
    c2 on 1 hold 1 beat
    eb2 on 2 hold 1 beat
    g2 on 3 hold 1 beat
    bb1 on 4 hold 1 beat

track bass instrument bass pattern notes volume -6db pan center
```

### Song timing

- `bpm 120`: 20–300 **quarter notes** per minute, default 120.
- `time_signature 6/8`: a bar contains three quarter-note beats. Default 4/4. Supported denominators are 1, 2, 4, 8, 16.
- `length 8 bars`, `length 20 beats`, `length 30 seconds`, `length 0.5 minutes`; bare song lengths mean seconds.
- Without length: sum of sections, or four bars when there are no sections. A minimal song renders digital silence.
- `seed 42`: reproducible drums, reverberation, humanization and dither, default 0.
- `sample_rate 48000`, `bit_depth 24`: script format settings; CLI settings override them.
- `key f minor` and `genre electronic house` are descriptive metadata only. They do not transpose pitches or alter mastering.

### Notes and patterns

Beat positions start at **1**, measured in quarter notes from the start of the pattern. Positions are never bar numbers. Write `c4 on 5` for the first beat of the second 4/4 bar. Accidentals include `F#3`, `Bb2`; A4 = 440 Hz. MIDI pitches 0–127 are accepted; a pitch above output Nyquist requires a higher sample rate.

```text
pattern harmony
    length 2 bars
    c3 eb3 g3 on 1 hold 4 beats
    ab2 c3 eb3 on 5 hold 1 bar

pattern chords
    play c minor for 4 beats
    play ab major for 4 beats

pattern drums
    swing 60
    kick on 1 and 3 vel 0.9, 0.8
    snare on 2, 4 vel 0.7
    hihat every 1/8 vel 0.4
```

`play ROOT major|minor for DURATION` places successive triads in sequence; chord roots default to octave 3. Explicit note lists create simultaneous chords. Default note gate is half a beat. Use `hold DURATION` before optional `vel VALUES`. Velocity is 0–1, either one value or one per position. Repeated melodic note lists are chords, not sequential melodies.

`every 1/4`, `every 1/8`, `every 1/16`, `every 1/8t` repeat at musical note values; `t` means triplet. Swing is 50–75 and delays the second eighth in each quarter-note pair; triplets and other subdivisions retain their positions. Patterns default to one bar and grow to whole bars to contain explicit notes and gates. An explicit pattern length overrides inference. `every` fills the resolved pattern length. Repeats are compiled from absolute rational beat positions to avoid timing drift.

Supported drums: kick, snare, hihat, closed_hat, open_hat, hat, clap, tom, ride, cymbal, perc. A `drums` block creates an implicit drum pattern and track, as in the README's original “My First Beat” example. A drum pattern on an explicit track requires `instrument drums`.

### Instruments and sound descriptions

Implicit presets: sine, synth, bass, lead, pad, piano, guitar, pluck, bell, plus the 128 General MIDI names (with spaces, underscores or `gm_`). See [friendly entry and piano](friendly-entry-and-piano.md) for automatic tracks/patterns, forgiving numbers, note-relative timing, `--list-instruments` and `--check`. Custom names can still be declared with `instrument NAME`.

The supported LFO options are included in this instrument table.

| Instruction | Meaning |
| --- | --- |
| `type synth` | Oscillator synthesis; `wavetable` and `virtual_analog` are aliases for this implementation, with analytic waveforms rather than imported tables |
| `type pluck` | Damped harmonic partials; synthesized plucked-string approximation |
| `type piano` | Register-dependent stiff-string modes, detuning, hammer spectrum and transient, velocity-sensitive brightness |
| `type bell` | Damped inharmonic modes |
| `type fm` | Two-operator FM with a decaying modulation index |
| `type drum` | Kick model for a custom named instrument; built-in drum names choose their percussion model |
| `oscillator sine` | Also saw, square, triangle, noise |
| `oscillator saw unison 3 detune 0.01` | 1–8 voices, symmetric fractional frequency detune 0–0.1 |
| `filter lowpass cutoff 800hz resonance 0.7` | Lowpass or highpass biquad; resonance is Q (0.1–10), not a normalized knob |
| `envelope attack 5ms decay 100ms sustain 0.6 release 200ms` | Times need ms/s units; sustain is 0–1; time settings are 0–30 seconds |
| `lfo rate 4hz target filter.cutoff depth 300hz` | Sine LFO, 0.01–30 Hz, adds ±300 Hz to cutoff |
| `lfo rate 1/4 target filter.cutoff depth 300hz` | Tempo-synced period: `1/4` is one quarter-note beat; `1/8t` is an eighth-note triplet |
| `distortion light` | none, light, medium, heavy or numeric drive 0–8 |
| `reverb hall mix 0.2` | Diffuse mono convolution room response; room/hall/cathedral tails of 0.6/1.5/3 seconds |
| `delay time 0.25s feedback 0.3 mix 0.2` | Delay time up to 3 seconds; feedback 0–0.9, mix 0–1 |

Descriptions are a bounded vocabulary, not a general language model. `warm`/`dark`/`deep` reduce cutoff; `bright`/`airy`/`sharp` increase cutoff; `soft`/`gentle`/`smooth` soften attack; `short`/`long` change decay/release; `punchy` shortens attack; `distorted`/`gritty`/`aggressive` add saturation. Connecting words in the examples are accepted. Words such as “metal shell” label the description without selecting a shell model. Settings apply in source order; an explicit filter after a description overrides that description's cutoff.

```text
kick deep and punchy with a sharp click
snare tight and bright with metal shell
hihat sharp and short, closed
```

Percussion uses its own attack/decay synthesis; melodic ADSR controls do not redefine a drum's gate. Drum decay scales its natural tail, capped at three seconds. A “closed” descriptor does not change an open_hat into hihat: choose the appropriate drum name.

### Filter movement and automation

A filter LFO is a sine wave shared on the song clock, so voices sounding at the same instant use the same phase; it does not restart when a note starts. The depth is an offset in Hz. It is added to the current cutoff and clipped to 20 Hz–45% of the internal synthesis sample rate. The tempo-synced rate is resolved from the song BPM and musical note duration, including triplets. LFO and automation can be combined.

```text
over 2 bars in build
    bass.filter.cutoff from 500hz to 2400hz
    drums.volume from -18db to -9db
```

This README-style block starts at the named section's first beat, even if declared earlier in the file. The first ramp value takes effect at the section start; values interpolate linearly in Hz or dB for the given duration, then hold the final value until the section ends. Outside that section, the instrument's cutoff and track's volume apply. A note or effect tail crossing a section boundary follows the section currently playing. Volume applies to the entire voice, including its effects; cutoff applies to the voice before distortion, delay, and reverb. The ramp must fit within the section. Duplicate targets within a section and unknown tracks/sections produce errors. `TRACK` is a track name even for the filter target; an instrument shared by two tracks can be automated independently.

The cutoff and LFO are evaluated at a 1 kHz control rate, with filter history preserved when coefficients change; the volume ramp is evaluated per output sample. Changes are deterministic. This is an offline approximation, not a measurement of artifact-free modulation at every setting. See [the runnable wobble example](../examples/wobble.mtl).

### Tracks and sections

```text
track bass
    instrument bass
    pattern notes
    volume -6db
    pan -20

section intro
    length 4 bars
    bass only
section verse
    length 8 bars
    add drums
section ending
    length 4 bars
    remove drums
```

Track volume is -96..+12 dB, default -6 dB. Pan is -100..100 or `center`, with equal-power gains. Referencing a track again updates its properties. Sections are consecutive in declaration order; default section length is eight bars. `add TRACK`, `remove TRACK`, `only TRACK` / `TRACK only` update the active set; `all` selects all tracks. If the first section has actions it starts with an empty set; otherwise all tracks begin active. Later sections inherit the active set. Patterns restart and held notes enter release at every section boundary. Release/effect tails can overlap the next section. With no sections all tracks loop from the start. An explicit song length truncates the arrangement or extends the final active set.

```text
humanize all tracks
    timing ±5ms
    velocity ±5%
master
    peak -1db
```

Humanization is seeded and bounded within each section. `peak` is an attenuation-only **sample peak** ceiling; it preserves relative track levels and does not boost quiet material. It does not measure LUFS or guarantee true peak between samples. Final duration includes tails; allow space in the arrangement if you want a tail to ring out. A five millisecond fade at each file boundary avoids abrupt cuts. TPDF dither is applied when quantizing nonzero samples.

## Scope and resource limits

The original draft describes a much larger product. This release rejects unsupported commands instead of ignoring them. Instrument bank imports, single-WAV sampling, acoustic approximations, organ registrations and timed WAV clips are now supported; see [instruments and audio](instruments-and-audio.md). Remaining proposals include arbitrary conversational composition, tempo maps, other LFO targets/shapes, automation besides volume/cutoff, SoundFont import, realistic physical modeling, live input/MIDI, shared effect buses, compression, LUFS/true-peak mastering, FLAC/MP3 and float WAV output. The draft's forgiving lexer has intentionally been replaced with explicit diagnostics to prevent silent omissions; there was no executable compatibility baseline in the repository.

The floating point mix is backed by a temporary disk file (8 bytes per stereo frame), and a voice is generated at a time. Free disk space must accommodate the mix and output; memory scales with voice duration and oversampling. A note gate is limited to 60 seconds, compiled events and pattern repeats to one million, and output to the RIFF 4 GiB limit. Large files can take substantial CPU time. No external services or audio device are needed.

## Python API and tests

```python
from pathlib import Path
from mtl import parse_song, render_song
song = parse_song(Path("examples/first_beat.mtl").read_text(encoding="utf-8"))
stats = render_song(song, "beat.wav", quality=3)
print(stats["seconds"], stats["events"])
```

`parse_song` validates the input language and returns a mutable song model. Use the parser/CLI for validated input rather than constructing invalid model objects. Run `python -m pytest -q` after installing `.[test]`. Tests check original README drum syntax, musical timing and meter, section routing, notes/chords, parser diagnostics, actual pitch, alias reduction, release continuity, reproducible synthesis, effects tails, stereo PCM and CLI failure behavior.


<!-- /coderabbit-ai-generated:v1 -->