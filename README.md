<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:66eda08fd5e9de9efa1211aeea5a134daeee8a7d64a152845193a4f97e6f289c -->

# Music Text Language (MTL)

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:18ad4e9519fd24d793663c249445c1c08e1f29bd19f2a1b05716e100ac78109c -->

MTL turns text files into stereo WAV music. Start with a few notes and an automatic band, or use explicit instruments, patterns, sections, audio clips and effects. The renderer is written in Python and runs locally.

The same complete reference is available as [document.md](document.md).

<!-- /coderabbit-ai-generated:v1 -->

This reference describes the **implemented language**. The [original product draft](docs/original-product-draft.md) is preserved for historical context and describes additional ideas that are not implemented. Input uses a bounded vocabulary; arbitrary prose and all draft commands are not supported.

## Install and render

Requires Python 3.11+, NumPy and SciPy. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
mtl examples/compact_piano.mtl piano.wav --quality 5
```

Windows users can activate with `.venv\Scripts\activate`. `python -m mtl` is equivalent to `mtl`. A file containing `c d e g` is enough to make a song:

```bash
mtl song.mtl song.wav
mtl song.mtl --check
mtl --list-instruments
python -m pytest -q
```

Usage: `mtl INPUT.mtl [OUTPUT.wav] [--quality 1..5] [--sample-rate RATE] [--bit-depth 16|24]`. The output argument overrides the `output` or `render to` command. Output paths are relative to the current working directory. Imported files and samples are resolved relative to the file declaring them. `--sample_rate` and `--bit_depth` are aliases. `--check` validates parsing, note scheduling and clip references, but does not read WAV assets. `--version` prints the version. A render error returns status 1 and preserves the destination; invalid CLI arguments return status 2.

Defaults are 120 BPM, 4/4, 48 kHz, 24-bit stereo PCM, quality 3 and `output.wav`. Supported rates are 22050, 44100, 48000, 88200 and 96000 Hz. Quality 1–2 uses native-rate synthesis, 3–4 uses 2× oversampling and 5 uses 4×. Rendered files are WAV, and playback is not started automatically.

## Compact songs

Write notes on a single line or a separate line for each part:

```text
panio c f g2s repat four bars
```

This creates a piano part and basic drums at 120 BPM, with four body bars, a one-bar intro and a one-bar ending. `panio` and `repat` are accepted spellings. `g2s` means G4 for two seconds; `g2` means G in octave 2. A trailing duration such as `piano c f g 2s` applies to every note. Bare notes last one beat and default to octave 4. Notes are repeated through the body, with notes at its end shortened to fit. `do re mi fa sol la ti` and `si` are C-major solfege alternatives. Separate notes with spaces.

```text
piano chords c am f g repeat eight bars
drums jazz
generate bass
tempo 104 bpm
```

- `piano c f g` creates a melody. `piano chords c am f g` plays root-position triads. Use sharps/flats and optional `m`, `min` or `maj` suffixes.
- `drums STYLE` selects `basic`, `jazz`, `country`, `techno`, `reggae`, `house`, `rock` or `dubstep`. `piano c f g repeat four bars with jazz drums` is also accepted. `drums off` disables the drummer.
- `generate bass`, `generate chords`, or `generate bass and chords` add parts based on the first phrase's roots. Bass instruments and generated bass use single low roots. An entered bass suppresses the generated bass.
- `generate progression and bass and chords` creates I–vi–IV–V in a major key or i–VI–III–VII in a minor key. `key d minor` sets its key; otherwise it uses the first root or C. Entered melody pitches are not transposed.
- `repeat four bars` or `loop 4 bars` sets 1–256 whole body bars; a top-level `length` also sets the body length. `intro off` and `ending off` remove the extra bars.
- `tempo 90 bpm`, `bpm 90` and `seed 12` override tempo and reproducible variation. Compact arrangements use ±4 ms timing, ±2% velocity variation and piano pedal/stereo defaults. Multiple instrument lines create separate parts.

Compact mode accepts unindented note/instrument phrases and its controls. Explicit `instrument`, `pattern`, `track`, `section`, imports and nested blocks use the structured language below. Plain top-level notes select compact mode. See [compact song details](docs/compact-songs-and-piano.md) and `examples/compact_*.mtl`.

## Structured songs and syntax

Use one instruction per line, with indentation for blocks. Keywords are generally lowercase; note letters can be uppercase. Quote titles, paths and names containing spaces. `//` introduces a comment outside a quoted string; `#` is part of a sharp note. Unsupported or ambiguous instructions produce errors rather than being silently ignored.

```text
song "Small Song"
bpm 100
time_signature 4/4
length 8 bars
output "small.wav"

instrument warm_bass
    oscillator saw
    warm and slightly distorted
    filter lowpass cutoff 800hz resonance 0.7
    envelope attack 3ms decay 80ms sustain 0.5 release 120ms

pattern bassline
    c2 on 1 hold 1 beat
    eb2 on 2 hold 1 beat
    g2 on 3 hold 1 beat
    bb1 on 4 hold 1 beat

track bass instrument warm_bass pattern bassline volume -6db pan center
```

A track selects an instrument and a repeating pattern. Tracks, patterns and instruments may be referenced before their definitions. An instrument's `from` base must already be defined, imported or be a built-in preset. With no tracks, patterns receive piano tracks or drum tracks. Track properties may be inline or indented; an omitted pattern can be inferred from the track name or the sole pattern, and a missing instrument defaults to the track's recognized instrument name or piano.

### Song commands and units

| Command | Meaning |
| --- | --- |
| `song "Title"` | Display title; default `Untitled`. |
| `bpm 120` / `tempo 120 bpm` | Quarter notes per minute, 20–300. |
| `time_signature 6/8` | Numerator 1–32; denominator 1, 2, 4, 8 or 16. A 6/8 bar has three quarter-note beats. |
| `length 8 bars` | Song length; also beats, seconds or minutes. A bare song length is seconds. Without it, sections determine length, otherwise four bars. |
| `output "song.wav"` / `render to "song.wav"` | Output path; positional output overrides it. |
| `sample_rate 44100`, `bit_depth 24` | Output format, overridden by CLI options. |
| `seed 42` | Reproducible humanization, synthetic noise and dither; unsigned 32-bit integer. |
| `key f minor`, `genre jazz` | Descriptive metadata in structured songs. `key` affects generated compact progressions. |

Durations can use numeric fractions (`1/2`), decimals, `half a beat`, `one and a half beats`, `2s`, or a clock form such as `1:30`. Words through ninety-nine and qualifiers such as `about` are accepted in supported numeric positions. Decimal commas work in scalar values; commas in beat and velocity lists separate values. Envelope times use `ms` or `s`. Beat positions are **one-based quarter-note beats**, even in non-4/4 meters; audio offsets are zero-based.

### Patterns, notes and drums

```text
pattern harmony
    length 2 bars
    c3 eb3 g3 on 1 hold 4 beats
    ab2 c3 eb3 on 5 hold 1 bar

pattern chords
    play c minor for 4 beats
    play ab major for 4 beats

drums
    kick on 1 and 3
    snare on 2, 4 vel 0.7
    hihat every 1/8
```

`PITCH ... on POSITIONS` plays simultaneous pitches. Use `hold DURATION`, followed optionally by `vel VALUE` or one velocity per position (0–1, or e.g. `80%`). The default gate for timed notes is half a beat. `play ROOT major|minor for DURATION` places triads in sequence; the default chord octave is 3. `every 1/4`, `every 1/8` and `every 1/8t` repeat at note values; `t` denotes a triplet. `swing 60` accepts 50–75 and delays the second eighth note of each beat.

Patterns default to one bar and grow to whole bars to contain explicit events unless `length` is specified. Pattern length defaults to bars; a note's bare duration defaults to beats. Pitches are MIDI range 0–127, with A4 = 440 Hz. Notes at or above output Nyquist are rejected. Drum names are `kick`, `snare`, `hihat`, `closed_hat`, `open_hat`, `hat`, `clap`, `tom`, `ride`, `cymbal`, and `perc`. A drum pattern on an explicit track uses `instrument drums`.

You can use a grid and spoken values:

```text
drums
    kick x...x...x...x...
    snare on two and four
    hihat every eighth note
```

`x`/`X` is a hit, `.`/`-` is a rest; grid steps divide the pattern length evenly. `drums house`, `drums techno`, `drums basic`, `drums rock`, `drums jazz`, `drums country`, `drums reggae` and `drums dubstep` also create shorthand patterns.

### Friendly blocks and relative notes

```text
piano
    notes c d e g
    volume -8 dB
    pan slightly left
vibraphone
    g5 at 50 percent of piano note one hold half a beat
    b5 after previous note
    c6 at end of piano note two plus half a beat
```

A bare instrument block creates its track and pattern. Bare notes form a sequential melody, defaulting to octave 4 and one beat; `chord c e g for two beats` plays simultaneous pitches. A bare instrument without notes auditions `c4 e4 g4 c5`. Instrument names can be GM names such as `acoustic grand piano` or `gm_trumpet` without an import.

References include `after previous note`, `after TRACK note N`, `at start of TRACK note N`, `at end of TRACK note N`, `at 25% of TRACK note N`, `at halfway through TRACK note N`, and `at end of note N` in the current pattern. Optional `plus DURATION` or `minus DURATION` shifts the event. Indices are one-based source/expansion order; a chord counts as one event, and each expanded beat is an event. Cycles, missing notes and negative positions are errors.

Melodic references use the written onset and gate before swing, humanization or section truncation and repeat with the receiving pattern. Use matching patterns when recurring parts must stay aligned. For WAV clips, a note reference triggers once at the first performed occurrence and follows its humanized onset and shortened gate. End means note-off, excluding release and effects.

### Instruments and presets

```text
import bank "general_midi"
import bank "organs"
import "my_presets/brass.mtl"

instrument solo from gm_trumpet
    envelope attack 25ms release 200ms
    vibrato rate 5.5hz depth 0.003
```

Built-in banks: `general_midi`, `acoustic`, `organs`, `electronic`. All 128 zero-based GM program names work without import; `mtl --list-instruments` lists them. Built-in GM voices are synthetic approximations, not sampled GM playback. Other implicit names include `sine`, `synth`, `bass`, `lead`, `pad`, `piano`, `guitar`, `pluck`, and `bell`. Custom declarations take precedence. Imports are relative to their declaring file and may contain instruments and imports only; repeated imports are deduplicated, cycles and duplicate names are errors. Inheritance copies the preset.

| Instrument instruction | Values / behavior |
| --- | --- |
| `type piano` | Modal piano with velocity-sensitive hammer, string detuning, soundboard and stereo image. |
| `type synth`, `wavetable`, `virtual_analog` | Analytic oscillator synthesis; the latter two are aliases. |
| `type pluck`, `bell`, `fm`, `drum` | Plucked, inharmonic bell, two-operator FM or percussion synthesis. |
| `type trumpet`, `violin`, `vibes`, `organ` | Expressive synthetic approximations. |
| `type sampler`, `multisampler` | User-supplied WAV sample or stereo multisample map. |
| `oscillator saw unison 3 detune 0.01` | `sine`, `saw`, `square`, `triangle`, `noise`; 1–8 voices and detune 0–0.1. |
| `envelope attack 5ms decay 100ms sustain 0.6 release 200ms` | Times 0–30 seconds; sustain 0–1. |
| `filter lowpass cutoff 800hz resonance 0.7` | `lowpass` or `highpass`; cutoff 20–96000 Hz, Q 0.1–10. |
| `lfo rate 1/4 target filter.cutoff depth 300hz` | Sine modulation; rate in Hz or musical note values, including triplets. Depth is Hz. |
| `distortion light` | `none`, `light`, `medium`, `heavy` or drive 0–8. |
| `delay time 0.25s feedback 0.3 mix 0.2` | Time >0–3s; feedback 0–0.9; mix 0–1. |
| `reverb hall mix 0.2` | `room`, `hall`, or `cathedral`; mix 0–1. |
| `hammer 0.6`, `soundboard 0.35`, `pedal 0.3`, `stereo_width 0.8` | Piano controls 0–1; `string_detune` is 0–10 cents. Pedal lengthens release. |
| `drawbars 8 8 8 4 0 0 0 0 0` | Nine organ levels, each 0–8; `rotary` 0–10 Hz and `percussion` 0–1. |
| `vibrato rate 5.5hz depth 0.003` | Rate 0.1–12 Hz and fractional depth 0–0.02; vibes use rate for tremolo. |
| `program 56` | GM program metadata, 0–127. |

Sound descriptors include `warm`, `dark`, `deep`, `bright`, `soft`, `short`, `long`, `punchy` and `distorted`. They adjust synthesis parameters in source order; they are a limited vocabulary.

### WAV instruments and sample maps

```text
instrument sampled_piano
    type sampler
    sample "samples/piano_c4.wav"
    root c4
    envelope attack 2ms decay 200ms sustain 0.8 release 150ms
```

`sampler` pitch-shifts one WAV relative to `root`, downmixes stereo to mono, and plays it once without a sustain loop. For stereo, key ranges, velocity layers, seeded round-robin takes and crossfaded loops, use a JSON map:

```text
instrument recorded_grand
    type multisampler
    sample_map "samples/grand.json"
    envelope attack 1ms decay 1ms sustain 1 release 350ms
    pedal 0.2
```

```json
{
  "zones": [
    {"root":"c4", "low":"a3", "high":"e4", "velocity":0.25,
     "files":["c4_soft_1.wav", "c4_soft_2.wav"], "loop":[0.4,1.2]},
    {"root":"c4", "low":"a3", "high":"e4", "velocity":0.9,
     "files":["c4_loud.wav"], "loop":[0.4,1.2]}
  ]
}
```

Paths are relative to the map, key ranges are inclusive, velocity centers are 0–1 and loop endpoints are seconds. The closest root is selected and adjacent velocity layers are interpolated. The map permits 1–2048 zones, 1–32 WAVs per zone and at most 2 MiB. Missing coverage or assets produce an error. There are no built-in commercial recordings, release samples, pedal resonance samples, SoundFont or plugin hosting. See [multisample details](docs/compact-songs-and-piano.md#recorded-piano-libraries-stereo-multisampling).

### Tracks, sections and clips

```text
track keys
    instrument piano
    pattern harmony
    volume -6db
    pan -20
    reverb hall mix 0.1

section intro
    length 4 bars
    keys only
section verse
    length 8 bars
    add drums
section ending
    length 4 bars
    remove drums
```

Volume ranges from −96 to +12 dB, default −6 dB; pan is −100 to +100, `center`, `left`, `right`, `slightly left` or `slightly right`. Sections play consecutively; default length is eight bars. `add TRACK`, `remove TRACK`, `only TRACK`, `TRACK only` and `all` control active tracks. If the first section has actions, the initial active set is empty; otherwise all tracks start active. Patterns restart and held notes enter release at each section boundary, while tails can overlap. Explicit song length can truncate or extend the arrangement.

```text
track recording
    audio "audio/texture.wav" at 0 seconds
    audio "audio/fill.wav" at 7 beats
    audio "audio/impact.wav" at section verse
    audio "audio/accent.wav" at end of keys note 1
    volume -9db
    filter highpass cutoff 150hz
    delay time 0.25s feedback 0.3 mix 0.15
    reverb hall mix 0.2
```

Audio offsets start at zero. Clips are independent of section track activation and play until source/effects finish or the song ends. Use separate tracks for audio clips and instrument patterns. Clips preserve stereo; mono uses equal-power pan, stereo uses balance. Input WAV supports 8-bit unsigned, 16/24/32-bit signed and float PCM, mono/stereo, 8–192 kHz, up to 64 MiB and 120 seconds. Input WAVs cannot be overwritten by output. Effects on tracks apply independently per clip or voice.

### Automation, humanization and mastering

```text
over 2 bars in verse
    bass.filter.cutoff from 500hz to 2400hz
    keys.volume from -12db to -6db

humanize all tracks
    timing ±5ms
    velocity ±5%
master
    peak -1db
```

Automation supports track `volume` and `filter.cutoff`, interpolates during the specified portion of a section, then holds through that section. A ramp must fit within the section; duplicate targets are rejected. LFO cutoff is added to the current automated cutoff. Humanization uses the song seed and is bounded to each section; timing is 0–100 ms and velocity 0–100%. The master sample-peak ceiling is −24 to −0.1 dB, default −1 dB, and only attenuates; it does not guarantee a true-peak or LUFS target. Allow space for effects and release tails within song length.

## Python API

```python
from pathlib import Path
from mtl import parse_song, render_song

path = Path("examples/compact_jazz.mtl")
song = parse_song(path.read_text(encoding="utf-8"), base_path=path.parent)
stats = render_song(song, "jazz.wav", quality=3)
print(stats["seconds"], stats["events"])
```

`parse_song` returns a song model; `base_path` defaults to the working directory. `render_song` writes WAV atomically and returns statistics. Errors use `MTLError`. The temporary mix uses approximately eight bytes per stereo frame on disk. Notes are limited to 60 seconds, pattern repeats and events to one million, and output to the 4 GiB RIFF limit.

## Examples and further reading

- [Compact piano](examples/compact_piano.mtl), [jazz](examples/compact_jazz.mtl), [country](examples/compact_country.mtl), [reggae](examples/compact_reggae.mtl), and [techno](examples/compact_techno.mtl).
- [Piano and note references](examples/easy_events.mtl), [synthesis and automation](examples/wobble.mtl), [instrument showcase](examples/instrument_showcase.mtl), and [WAV session](examples/wav_session.mtl). Render `instrument_showcase.mtl` to `examples/colors.wav` before running the WAV session.
- [Compact songs and piano](docs/compact-songs-and-piano.md), [friendly syntax](docs/friendly-entry-and-piano.md), [instrument banks and WAV tracks](docs/instruments-and-audio.md), [structured renderer](docs/python-renderer.md), and [algorithm assessment](docs/audio-algorithms.md).

The instruments are synthesized approximations; commercial piano or VST parity is not established. Features described only in the historical draft—such as arbitrary conversational composition, tempo maps, VST hosting, SoundFont import, live MIDI, shared buses and LUFS mastering—are not implemented.


<!-- /coderabbit-ai-generated:v1 -->