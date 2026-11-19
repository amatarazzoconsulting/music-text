<!-- coderabbit-ai-generated:v1 -->

# Compact songs, automatic accompaniment and piano

## A whole song in a few words

```text
panio c f g2s repat four bars
```

This accepts the spelling slips and creates a piano track, a basic drummer, four body bars, a one-bar intro and a one-bar ending. Default tempo is **120 BPM**. The total is six bars (12 seconds in 4/4). `g2s` means G4 for two seconds; C and F use one beat each. `g2` without `s` means G2. A separate trailing duration, as in `piano c f g 2s`, applies to all three notes. Notes crossing the body boundary are shortened to fit.

Children can start with just:

```text
c d e g
```

or:

```text
do re mi fa sol
```

Omitted octaves use 4, omitted note durations use one beat, and the default body is four bars. Note spelling supports sharps/flats, explicit octaves and compact chord roots such as `am`, `f#min` and `gmaj`. `do re mi fa sol la ti/si` maps to C major. Whitespace separates tokens; attached runs such as `cdefg` are not supported.

## Choose the drummer and accompaniment

```text
piano chords c am f g repeat eight bars
drums jazz
generate bass
tempo 104 bpm
```

`piano c f g` plays a melody. `piano chords c f g` plays triads. `generate chords` adds triads based on the entered roots, one per bar; `generate bass` adds single low roots. `generate bass and chords` adds both. Minor suffixes affect triads; a melody still plays the root pitch.

Bass instruments always play **one low root at a time**, even with the `chords` keyword. `bass chords c f g` uses C2, F2 and G2. A requested generated bass is suppressed when an entered track already uses a bass sound. Bass recognition uses the instrument name (containing `bass`, excluding `bassoon`).

To create a progression without entering one:

```text
generate progression and bass and chords
key d minor
drums reggae
```

Automatic major harmony uses I–vi–IV–V; minor uses i–VI–III–VII. It transposes to the stated key or the first entered root, otherwise C. Explicitly entered melody pitches are preserved. The generated progressions use simple root-position triads; they are editable starting points.

Available drummer styles: `jazz`, `country`, `techno`, `reggae`, `house`, `rock`, `basic`, `dubstep`. Jazz uses swung ride timing, quiet kick/snare comping and hi-hat foot accents; country uses a train-style snare; reggae uses a one-drop kick/snare; techno uses quarter-note kicks and sixteenth hats. Grooves include accented dynamics, seeded variation, turnaround fills and a closing kick/cymbal. These are synthetic drum sounds, not recorded drummers.

You can also write `piano c f g repeat four bars with jazz drums`. Structured `.mtl` files can use `drums jazz`, `drums country`, `drums reggae` or `drums dubstep` as a new one-bar pattern shorthand; these structured shortcuts use 4/4 groove positions. Compact arrangements scale groove positions to the configured meter.

## Defaults and controls

- `tempo 90 bpm` or `bpm 90` overrides 120 BPM.
- `repeat four bars`, `loop 4 bars` or a top-level `length 4 bars` sets body length. Compact mode allows 1–256 whole bars. Intro/ending are additional bars.
- `intro off`, `ending off`, `drums off` disable generated parts independently.
- `seed 12` reproduces the same dynamics and timing. Compact arrangements add ±4 ms timing and ±2% velocity variation.
- Compact pianos use gentle static pedal (`0.18`) and stereo width (`0.75`). Other existing defaults remain 48 kHz stereo, 24-bit WAV and quality 3 unless overridden.
- Multiple compact instrument lines make separate tracks. Each phrase repeats through the body. The first line supplies the roots for requested accompaniment.

```bash
mtl examples/compact_piano.mtl --check
mtl examples/compact_jazz.mtl jazz.wav --quality 5
mtl --list-instruments
```

`--check` shows the inferred tempo, arrangement length, tracks, drummer and accompaniment choices.

Compact mode is selected for unindented note/instrument phrases and compact control lines. Files with explicit `instrument`, `track`, `pattern`, `section`, `import` or nested blocks continue through the existing structured parser. **Plain top-level notes now opt into automatic arrangement**; this intentionally extends the earlier plain-note shortcut. An instrument block such as `piano` followed by indented notes retains its earlier behavior. Use structured commands when you need precise control or want to mix samples, automation and custom arrangements. This is a bounded grammar, not arbitrary-language understanding.

## Improved piano synthesis

The procedural piano now has up to 96 inharmonic modes, small seeded strike-to-strike coupling variation, damper noise, static pedal-dependent release, keyboard-position stereo placement and weak early soundboard reflections. The prior velocity-sensitive hammer spectrum, register-dependent strings and high-mode decay remain.

```text
instrument grand from piano
    hammer 0.6
    soundboard 0.35
    string_detune 0.7
    pedal 0.3
    stereo_width 0.8
```

`pedal` and `stereo_width` accept 0–1. Pedal lengthens release; it is a static setting, not MIDI pedal events or a simulation of interactions among all vibrating strings. Width 0 centers a mono image. Existing piano presets intentionally sound different after this update. Other engines retain their public interfaces.

## Recorded piano libraries: stereo multisampling

A recorded library can supply detail the procedural model cannot reproduce. The new `multisampler` engine loads your WAV recordings, preserves stereo, interpolates neighboring velocity layers, selects seeded round-robin takes and supports crossfaded sustain loops.

```text
instrument recorded_grand
    type multisampler
    sample_map "samples/grand.json"
    envelope attack 1ms decay 1ms sustain 1 release 350ms
    pedal 0.2
```

Map file (paths relative to the JSON file):

```json
{
  "zones": [
    {"root":"c4", "low":"a3", "high":"e4", "velocity":0.25,
     "files":["c4_soft_1.wav", "c4_soft_2.wav"], "loop":[0.4,1.2]},
    {"root":"c4", "low":"a3", "high":"e4", "velocity":0.9,
     "files":["c4_loud_1.wav"], "loop":[0.4,1.2]}
  ]
}
```

Key ranges are inclusive. For covered keys, the closest root is chosen; velocity layers for that root interpolate linearly. Each layer's velocity is a center from 0–1. Add more roots to reduce pitch shifting and more layers for richer dynamics. Each zone supports 1–32 round-robin files. Loop values are seconds at the original recording's pitch; playback resampling adjusts them. Omit `loop` for one-shot playback. Note-off uses the instrument's envelope/release. Loop points should be chosen in a stable part of the recording.

Limits: 2 MiB JSON, 1–2048 zones; each WAV retains existing decoding/rate/duration limits. Missing coverage or assets produce errors. Rendering cannot overwrite mapped source WAV files. There are no separate release samples, pedal resonance samples, microphone positions, SF2/Kontakt/VST loading or streaming from disk. A commercial library's proprietary container must be converted into a supported WAV map where permitted; no recorded commercial assets are included.

The implementation and demos are tested for timing, pitch, dynamics, stereo behavior and file integrity. Commercial-or-better piano quality has **not** been established; that requires suitable recordings and listening comparisons.
