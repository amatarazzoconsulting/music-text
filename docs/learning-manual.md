# MTL learning manual

This manual teaches the Music Text Language (MTL) workflow from a first note to an arranged, rendered song. MTL is a local text-to-audio program: you edit a UTF-8 `.mtl` source file, validate its musical schedule, and render a WAV. It does not require an audio device or a remote service.

## 1. Install and start

Use Python 3.11 or newer from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m mtl --help
```

On Windows, activate with `.venv\Scripts\activate`. `mtl` and `python -m mtl` run the same command-line program. Paths in commands are relative to the terminal's current directory.

The main workflow is:

1. Write or edit a `.mtl` source.
2. Run `python -m mtl song.mtl --check`.
3. Render with `python -m mtl song.mtl song.wav --quality 3`.
4. Listen, revise the source, and render again.

The renderer does not start playback automatically. Keep the `.mtl` file with any WAV you share so the arrangement can be changed and rendered again.

## 2. Make a first song

Create `first_song.mtl`:

```text
song "First Steps"
bpm 96
key c major

piano c4 d4 e4 g4
```

Render it:

```bash
python -m mtl first_song.mtl first_song.wav
```

An unindented note phrase uses compact mode. MTL supplies a simple band, intro and ending around the phrase. Compact mode is useful for sketches; structured mode gives you explicit instruments, patterns, tracks and timeline sections.

## 3. Understand pitch, beat and velocity

- Notes use letters `a` through `g`; `#` raises a pitch and `b` lowers it. Examples: `f#4`, `bb3`.
- The octave number identifies register. `c4` is middle C.
- In a pattern, `on 1` is the first beat and `on 5` starts the second bar in 4/4. Note positions are one-based.
- `hold 1 beat` controls the gate before release. Effects and the instrument envelope can continue after that gate.
- `vel 0.7` is note velocity from 0 to 1. Use lower velocity for ghost notes and higher velocity for accents.
- The default meter is 4/4. `time_signature 5/4` makes a bar five quarter-note beats; positions still count beats, not bars.
- `bpm 96` sets tempo. Higher BPM makes each beat shorter.

Durations should be explicit when a phrase needs them:

```text
pattern melody
    c4 on 1 hold 0.75 beats vel 0.56
    e4 on 2 hold 0.5 beats vel 0.42
    g4 on 3 hold 1.25 beats vel 0.76
```

## 4. Learn the four arrangement building blocks

An **instrument** defines a sound, a **pattern** defines notes, a **track** assigns a sound to a pattern, and a **section** determines when tracks play.

```text
song "Evening Steps"
bpm 96
time_signature 4/4
key c major

instrument warm_keys
    type piano
    hammer 0.35
    soundboard 0.55
    pedal 0.12

pattern harmony
    length 2 bars
    c3 e3 g3 on 1 hold 3 beats vel 0.62
    f3 a3 c4 on 5 hold 3 beats vel 0.58

pattern melody
    length 2 bars
    e5 on 1 hold 0.75 beats vel 0.72
    g5 on 2 hold 0.5 beats vel 0.56
    c5 on 3 hold 1.5 beats vel 0.8
    a4 on 5 hold 0.75 beats vel 0.63
    c5 on 6 hold 0.75 beats vel 0.72
    f5 on 7 hold 1.5 beats vel 0.78

track accompaniment instrument warm_keys pattern harmony volume -12db
track tune instrument vibes pattern melody volume -8db pan 18
```

The two-bar patterns repeat until the song ends. A pattern length is measured in bars unless a unit is supplied. Track volume is in dB; start modestly and adjust parts relative to one another.

## 5. Build harmony and rhythm

For chord events, write multiple pitches on one line:

```text
pattern chords
    c3 e3 g3 b3 on 1 hold 3 beats vel 0.62
    a2 c3 e3 g3 on 5 hold 3 beats vel 0.56
```

This makes C major seventh followed by A minor seventh. You are responsible for the notes and voicing; MTL does not infer a chord progression from arbitrary structured notes.

A bass pattern can outline roots and fifths:

```text
pattern bassline
    c2 on 1 hold 0.75 beats vel 0.76
    g2 on 3 hold 0.65 beats vel 0.58
    a1 on 5 hold 0.75 beats vel 0.72
    e2 on 7 hold 0.65 beats vel 0.56
```

Drum hits use named pitches:

```text
pattern groove
    length 1 bar
    kick on 1, 3 vel 0.72
    snare on 2, 4 vel 0.58
    hihat every 1/8 vel 0.28
```

Use `swing 58` on a pattern to delay its offbeat eighth notes slightly. Use `humanize all tracks` to add bounded timing and velocity variation while keeping renders repeatable with the same seed:

```text
seed 27
humanize all tracks
    timing +/-5ms
    velocity +/-4%
```

## 6. Find and select instruments

Browse default General MIDI names with:

```bash
python -m mtl --list-instruments
```

Search bundled banks by name, bank, engine, waveform and timbral labels:

```bash
python -m mtl search-instruments glass
python -m mtl search-instruments bass --bank synth1_bank --limit 20
python -m mtl search-instruments organ --bank organs
```

Search words are case-insensitive; when multiple words are given, all must match. `--bank` accepts a built-in bank name or an external instrument-only MTL bank path:

```bash
python -m mtl search-instruments soft --bank presets/my_bank.mtl
```

Use a bank in a song with an import:

```text
import bank "electronic"
import bank "acoustic"
import bank "organs"
import bank "hybrid"
import bank "synth1_bank"
```

The acoustic bank contains synthetic piano, trumpet, violin, vibes and pluck presets. Electronic presets explore oscillator, FM, filtering, modulation, granular processing and effects. The organ bank changes drawbars, rotary speed and percussion. Hybrid instruments layer acoustic and electronic voices. These are original MTL models, not exact reproductions of commercial synthesizers or recordings.

The package Synth1 bank contains 2,000 selected approximate conversions with new texture/use names; original patch names and source comments are omitted. Oscillator, filter, unison, chorus, delay and distortion translate where MTL has a matching control. Envelope fields without a reliable mapping use MTL defaults.

## 7. Shape a sound

For an original subtractive voice, set the oscillator, filter and envelope:

```text
instrument dusk_pluck
    type synth
    oscillator saw unison 2 detune 0.004
    filter lowpass cutoff 1800hz resonance 0.75
    envelope attack 4ms decay 260ms sustain 0.35 release 180ms
    chorus rate 0.3hz depth 0.002 mix 0.16
```

- Sine is smooth, saw is bright, square is hollow, triangle is softer, and noise is unpitched.
- A lowpass filter removes high frequencies above its cutoff; a highpass removes lows below its cutoff.
- Unison layers oscillators. Small detune values widen the sound; large values can sound unstable.
- Attack is fade-in time, decay moves to the sustained level, sustain is a volume ratio, and release is fade-out after note-off.
- `oscillator2` adds a second waveform. `layers` combines complete named instruments.
- Reverb adds space, delay makes repeats, chorus adds modulated width, and distortion adds harmonics.
- A `granular` block creates overlapping grains from the synthesized voice or audio track. Use moderate mix and density for clarity.
- A track `pan` moves its sound across the stereo field.

## 8. Arrange sections into a timeline

Sections play in written order. `only` resets which tracks are active; `add` and `remove` change that set. Patterns restart at each section boundary:

```text
section intro
    length 2 bars
    only accompaniment

section verse
    length 8 bars
    only accompaniment
    add bass
    add drums
    add melody

section bridge
    length 4 bars
    only accompaniment
    add bass
    add melody

section tail
    length 1 bar
    only all
    remove all
```

The section lengths determine song duration when no top-level `length` is specified. The empty ending section provides room for voices and effects to fade. Use `--check` to inspect the assembled schedule before rendering:

```bash
python -m mtl song.mtl --check
```

The check reports tempo, meter, duration, scheduled notes, instruments and track levels. It checks note scheduling but does not open audio assets.

## 9. Use the guided composer

Run:

```bash
python -m mtl interactive new_song.mtl
```

Choose a preset bank, search for lead and harmony voices, select a key and melody shape, then use the arrangement menu to:

- print note patterns and velocities;
- inspect section lengths, active tracks and total duration;
- append verse, chorus, bridge or outro sections;
- move a section to a new timeline position;
- remove a section; and
- save a validated editable MTL file.

The composer creates a starting arrangement, not a finished production. You can edit the saved notes, instruments, volumes, effects and timeline in a text editor. Render the source separately after saving.

## 10. Add audio and sample instruments

Use an audio-only track for an existing recording or ambience:

```text
track texture
    audio "audio/texture.wav" at 0 seconds
    volume -12db
    reverb hall mix 0.18
    granular size 80ms density 14hz spray 40ms pitch 5 mix 0.18
```

Paths resolve relative to the file that declares them. For note-triggered playback, define a sampler with a WAV sample and its root pitch. Samples must be licensed and present locally; MTL does not download them.

SoundFonts can be verified with `python -m mtl --verify-soundfont file.sf2`. Rendering a SoundFont requires the FluidSynth shared library. Optional local SoundFonts are not automatically included when the project is copied.

## 11. Render and compare

Useful render controls:

```bash
python -m mtl song.mtl song.wav --quality 3
python -m mtl song.mtl final.wav --quality 5 --sample-rate 48000 --bit-depth 24
```

Quality 1–2 uses native-rate synthesis; 3–4 uses 2× oversampling; 5 uses 4×. Higher settings cost more CPU and memory. Sample rate and bit depth change output resolution, not the underlying instrument model. The output is stereo PCM WAV.

Change one thing at a time and keep `seed` fixed when comparing. Listen at matched volume. Confirm the whole piece, especially the first and last second. A master peak ceiling only attenuates peaks; it does not make a quiet arrangement louder.

## 12. Practice projects

1. **Melody:** make a four-bar melody with at least two velocities. Add rests by leaving beats empty.
2. **Harmony:** create a two-bar chord pattern, then write a bass pattern that outlines its roots.
3. **Groove:** make a one-bar kick/snare/hat pattern. Compare straight timing with a swing value near 58.
4. **Sound design:** duplicate a synth instrument and change only its filter cutoff. Compare both tracks at similar perceived loudness.
5. **Arrangement:** create intro, verse, chorus, bridge and tail sections. Mute or add parts to create contrast.
6. **Texture:** try a hybrid preset and a low granular mix, then remove the effect and compare.
7. **Interactive editing:** create a song through menus, move the bridge, inspect the timeline, and render the saved source.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| A command cannot find MTL | Activate the virtual environment or use `python -m mtl`. |
| A bank import fails | Check the bank name, file path, UTF-8 encoding and indentation. |
| The song is silent | Check the active tracks, track patterns, velocities, volume and section lengths. |
| Notes are missing at a section edge | A note starting outside the section is not played there; shorten the pattern or lengthen the section. |
| An effect tail is cut off | Add a release/tail section; effects do not extend the output automatically. |
| A sample is missing | Resolve the path relative to the declaring MTL file and ensure the local asset exists. |
| A render is too quiet | Raise track levels or velocities carefully; the master peak setting only limits peaks. |
| A 5/4 pattern drifts | Count five beats in each bar and place events using beat positions; do not treat bar numbers as beats. |

For the complete language reference, engine behavior, supported ranges and audio examples, see the [project README](../README.md), [instrument/audio guide](./instruments-and-audio.md) and [audio tests gallery](../audio_tests/README.md).
