<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3eea8e1c006c13be04d28c99125554763815535ef8efe53909a1c55154e30e49 -->

# Music Text Language: from your first notes to a finished song

MTL is a Python program that reads a text song file and renders stereo WAV audio. You can enter a few notes and let it build a band, or specify each instrument, pattern, section and effect yourself.

**Start here, in order.** This tutorial is followed by the full language reference and all 128 default instrument names. Audio you can listen to and edit is in [audio_tests](audio_tests/README.md). The historical product draft describes future ideas; this manual describes the working Python implementation.

## 1. Install once

Install Python 3.11 or newer, download or clone this repository, and open a terminal in its folder. Create a private Python environment:

```bash
python -m venv .venv
```

Activate it on macOS/Linux with `source .venv/bin/activate`, or on Windows with `.venv\Scripts\activate`. Then install:

```bash
python -m pip install -e '.[test]'
mtl --version
```

The install downloads NumPy and SciPy for audio calculation; no account, audio device or external audio service is needed. Activate the same environment in future terminal sessions. If your terminal cannot find `mtl`, try `python -m mtl` after activating it. Paths in the commands below are relative to the terminal's current folder.

## 2. Make your first song

Create a plain UTF-8 text file named `first_song.mtl`. Avoid a word processor that inserts formatting. Put this single line in it:

```text
c d e g
```

Render it:

```bash
mtl first_song.mtl first_song.wav
```

Open `first_song.wav` in your music player. Rendering creates a file; it does not automatically play it. You should hear a piano with a basic drummer, a short intro, four bars of repeated melody and an ending. A bar is a group of beats: the default is four beats per bar. At the default 120 BPM, each beat lasts half a second. Six bars including intro and ending therefore last twelve seconds.

Each entered note lasts one beat. `c` defaults to C4; C4 is middle C. Add an octave to move up or down: `c3` is one octave lower. `f#4` is F sharp; `bb3` is B flat. Solfege also works in compact songs: `do re mi fa sol`. Write spaces between notes.

Before rendering, inspect the program's choices with:

```bash
mtl first_song.mtl --check
```

It prints tempo, length, parts and inferred defaults. It checks musical scheduling but does not load external audio assets. Use a real render when checking sample files.

## 3. Choose a style and change the pace

Replace the file contents with this complete compact song:

```text
piano c e g c5 g e d g repeat four bars
drums country
generate bass and chords
tempo 112 bpm
seed 8
```

The first line is your melody. `repeat four bars` sets the body length; intro and ending add a bar each. `drums country` selects the groove. `generate bass and chords` adds low roots and supporting triads, using the first phrase's note roots. This is a simple starting accompaniment, not a harmonic analysis of your melody. Listen and adjust the entered roots or create separate structured patterns when you want exact harmony.

Change `country` to `jazz`, `reggae`, `techno`, `house`, `rock`, `basic` or `dubstep`. Jazz uses swung ride timing; reggae emphasizes a one-drop beat; techno uses steady kicks and busy hats. Change tempo to 88 for a slower result. `seed 8` makes timing and dynamics reproducible.

Try a second complete song with a deliberate chord progression:

```text
piano chords c am f g repeat eight bars
drums jazz
generate bass
tempo 104 bpm
```

`chords` turns each root into a triad. `am` means A minor. Without `chords`, the same roots become a single-note melody. A bass instrument always plays one low root, even if you write `bass chords c am f g`. For a generated progression, use `generate progression and bass and chords`; add `key d minor` if desired. Major generation uses I–vi–IV–V; minor generation uses i–VI–III–VII.

### Compact timing and switches

- `piano c f g2s repeat four bars`: C and F last one beat; G4 lasts two seconds. `g2` without `s` means low G2.
- `piano c f g 2s repeat four bars`: all three notes last two seconds.
- `intro off`, `ending off`, `drums off`: put each on its own line to remove that generated part.
- Body length is 1–256 whole bars. A phrase cycles until the body is full; a final note is shortened if it reaches the boundary.
- Compact arrangements deliberately add gentle timing and velocity variation. For exact note placement, use structured mode.

Spelling in the examples uses `piano` and `repeat`. The parser retains compatibility aliases for common typing slips. It recognizes a defined set of phrases; it does not understand arbitrary conversational requests.

## 4. Take control with structured mode

Once you want independent harmony and melody, save the following as `structured.mtl`. This is a complete file:

```text
song "Evening Steps"
bpm 96
length 4 bars

instrument soft_keys from piano
    hammer 0.4
    pedal 0.2
    stereo_width 0.6

pattern harmony
    length 2 bars
    c3 e3 g3 on 1 hold 4 beats vel 0.65
    f3 a3 c4 on 5 hold 4 beats vel 0.60

pattern melody
    length 2 bars
    e5 on 1 hold 1 beat vel 0.8
    g5 on 2 hold half a beat vel 0.7
    c5 on 3 hold 2 beats vel 0.75
    a4 on 5 hold 1 beat vel 0.7
    c5 on 6 hold 1 beat vel 0.8
    f5 on 7 hold 2 beats vel 0.65

track accompaniment instrument soft_keys pattern harmony volume -12db
track tune instrument vibes pattern melody volume -6db pan 20

drums
    kick on 1 and 3
    snare on 2 and 4
    hihat every 1/8 vel 0.35
```

The building blocks are **instrument** (how a note sounds), **pattern** (what notes happen), and **track** (which sound plays which pattern). The harmony track and melody track each repeat their two-bar pattern until the four-bar song ends. The drum shorthand creates its own track.

A `pattern` block is indented. `c3 e3 g3 on 1` means play those three pitches together on beat one. Beat positions continue across bars: beat five is the start of the second 4/4 bar. `hold 4 beats` controls the time before note-off; release and reverb can continue afterward. `vel` is the strength of a note, from 0 to 1. It affects both loudness and, on expressive voices, tone.

**Do not confuse three kinds of time:** `on 1` means the first beat, `every 1/8` means an eighth-note interval, and `audio ... at 1 beat` means a zero-based offset one beat after the start. A number without a unit also depends on context: bare song lengths are seconds; bare pattern and section lengths are bars; note durations are beats. Explicit units are clearest.

Structured mode is selected by explicit instrument/track/pattern/section commands or nested blocks. Compact automatic intros, endings and generated bands do not get inserted into an explicit arrangement. You decide which tracks and sections exist.

## 5. Choose and shape sounds

Run `mtl --list-instruments` to browse the 128 GM names. `piano`, `violin`, `trumpet`, `vibes` and `organ` are useful starting names. Quote multiword names in inline commands, for example `instrument "acoustic grand piano"`. A custom instrument based on one of these lets you adjust the sound without editing package presets.

A piano's `hammer` changes brightness, `string_detune` changes string beating, `soundboard` controls body modes, `stereo_width` changes its keyboard image, and `pedal` lengthens release. The last is static; it is not a performance of sustain-pedal presses. A SoundFont instrument uses `soundfont "file.sf2" preset "Preset Name"` and renders through the installed FluidSynth library. Its presets receive note velocities, and named drum notes use the percussion channel when the instrument selects a kit. For WAV recordings, the reference explains sampler and stereo multisampler maps.

For a synth, the oscillator makes the raw waveform. Sine is smooth; saw is bright; square is hollow; triangle is softer; noise makes an unpitched texture. A filter removes frequency ranges. Lowpass removes highs; highpass removes lows. Cutoff is measured in Hz. Resonance emphasizes frequencies near the cutoff.

The envelope changes volume through a note: **attack** is fade-in time, **decay** moves toward the held level, **sustain** is that level (not a time), and **release** is fade-out after note-off. A slow attack can hide very short notes. A long release needs room at the song's end.

Track volume is in dB: lowering it makes the part quieter; 0 dB means no gain change. `vel` is per-note expression; it is not a substitute for balancing tracks. Pan moves a sound left or right. Start with low levels and adjust tracks together; the master only reduces excessive peaks and will not boost a quiet song.

## 6. Build an advanced arrangement with effects

Save this complete example as `advanced.mtl`:

```text
song "Night Glass"
bpm 108
seed 21

instrument pulse
    type synth
    oscillator saw unison 2 detune 0.006
    envelope attack 5ms decay 100ms sustain 0.55 release 180ms
    filter lowpass cutoff 900hz resonance 0.8
    lfo rate 1/4 target filter.cutoff depth 300hz
    distortion light

pattern low
    c2 on 1 hold 0.75 beats vel 0.8
    g2 on 2.5 hold 0.5 beats vel 0.7
    bb1 on 3 hold 0.75 beats vel 0.75
    g2 on 4 hold 0.5 beats vel 0.65
pattern notes
    c5 on 1 hold 1 beat
    eb5 on 2 hold half a beat
    g5 on 3 hold 1 beat
    bb5 on 4 hold half a beat
pattern beat
    kick on 1, 2, 3, 4
    snare on 2, 4 vel 0.65
    hihat every 1/8 vel 0.35

track bass instrument pulse pattern low volume -9db
track melody instrument vibes pattern notes volume -9db pan 20
    delay time 0.3s feedback 0.4 mix 0.2
    reverb hall mix 0.12
track drums instrument drums pattern beat volume -9db

section opening
    length 2 bars
    only melody
section build
    length 2 bars
    add bass
section full
    length 4 bars
    add drums
section finish
    length 1 bar
    remove all

over 2 bars in build
    bass.filter.cutoff from 500hz to 2200hz
over 2 bars in full
    drums.volume from -15db to -9db
humanize all tracks
    timing ±3ms
    velocity ±3%
master
    peak -1db
```

Render with `mtl advanced.mtl advanced.wav --quality 5`. The first section plays only the melody; the next adds bass; the full section adds drums. Each section restarts active patterns. The final empty section leaves time for release and effects. No explicit song length is needed because the section lengths determine it.

The bass LFO is a periodic cutoff movement. Section automation sets a larger sweep from 500 to 2200 Hz. Modulation depth is added to that cutoff. The drum volume ramp makes its entry grow. Only volume and filter cutoff currently support section automation.

Delay repeats notes at a fixed interval; feedback determines how quickly repeats die away. Reverb adds a diffuse tail. Distortion changes tone and can increase brightness. Insert order is filter → distortion → delay → reverb. Track inserts process each voice separately, after its instrument effects; these are not shared mixer buses. The [DSP comparison WAV](audio_tests/dsp_comparison.wav) plays the same phrase dry, filtered, distorted, delayed and reverberated in successive two-second sections.

## 7. Reuse instruments, samples and relative events

Put instrument declarations in a separate `.mtl` file and load them with `import "presets/my_keys.mtl"`. Imports may contain instruments and other imports, not song tracks. Paths are relative to the file that declares them. A sample path inside that bank is relative to the bank, not the terminal.

A `sampler` plays a single WAV at different pitches; its `root` says which pitch the recording already contains. It downmixes stereo to mono. A `multisampler` map preserves stereo and adds key ranges, velocity interpolation, round-robin takes and explicit loops. Use this when you have recordings of an instrument across notes and dynamics. The reference below gives both complete formats and their limits.

To place a recording in the song, make an audio-only track with `audio "texture.wav" at 0 seconds`. Use `at section full` for a section trigger or `at 50% of melody note 1` to trigger halfway through its first performed note. The recording must actually exist; the command does not synthesize or download a missing file. Clips and instrument patterns require separate tracks.

For written note relationships, `g5 after previous note` starts at the preceding note's held end. `c6 at end of piano note two plus half a beat` uses another pattern's written position. Written melodic references repeat with their pattern; audio references trigger once against the first actual scheduled occurrence. They are deliberately different scheduling rules; see the detailed timing reference below before combining differing pattern lengths.

## 8. Finish, troubleshoot and experiment

1. Run `--check` to inspect inferred parts and arrangement duration.
2. Render a short version first. Keep track levels moderate and leave an empty ending section for tails.
3. Listen to the whole file, including the first and last second. Change one setting at a time and compare renders with the same seed.
4. Use quality 3 during editing and quality 5 for a final render if the extra computation is worthwhile. 16-bit is convenient for demonstrations; 24-bit keeps more resolution for further editing. Sample rate and bit depth do not by themselves make an instrument realistic.
5. Keep the `.mtl` with the WAV so someone else can reproduce it.

| Symptom | What to check |
| --- | --- |
| `mtl` not found | Activate the environment; try `python -m mtl`. |
| A command reports a source line error | Check indentation, keyword spelling, and the documented argument order. |
| A song is silent | Check active tracks, pattern references, velocity, volume, sample coverage and whether events occur before the song ends. |
| A note sounds much shorter than expected | Check its `hold`, envelope attack, section boundary and source sample length. |
| A reverb tail is cut off | Leave additional song time; effects do not extend the file length automatically. |
| A source file cannot be found | Resolve imports/samples relative to their declaring file; output paths use the terminal's working folder. |
| A beat is in the wrong bar | Positions are quarter-note beats starting at 1, not bar numbers. |
| A file is quieter than expected | Track volume and velocities determine level; the master ceiling only attenuates. |
| A low bass is a chord | In structured mode, enter one pitch per event. Compact bass roles enforce one low root. |

Explore [all eight demonstrations](audio_tests/README.md), then use the command reference that follows for exact ranges and formats.

---

# Complete language and command reference

# Music Text Language (MTL)

MTL turns text files into stereo WAV music. Start with a few notes and an automatic band, or use explicit instruments, patterns, sections, audio clips and effects. The renderer is written in Python and runs locally.

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
mtl convert-midi performance.mid
mtl --list-instruments
python -m pytest -q
```

Usage: `mtl INPUT.mtl [OUTPUT.wav] [--quality 1..5] [--sample-rate RATE] [--bit-depth 16|24]`. The output argument overrides the `output` or `render to` command. Output paths are relative to the current working directory. Imported files and samples are resolved relative to the file declaring them. `--sample_rate` and `--bit_depth` are aliases. `--check` validates parsing, note scheduling and clip references, but does not read WAV assets. `--version` prints the version. `mtl convert-midi INPUT.mid [OUTPUT.mtl]` creates editable MTL source; the output defaults to the input filename with an `.mtl` extension. Tempo changes are baked into note positions at 120 BPM. A render error returns status 1 and preserves the destination; invalid CLI arguments return status 2.

Defaults are 120 BPM, 4/4, 48 kHz, 24-bit stereo PCM, quality 3 and `output.wav`. Supported rates are 22050, 44100, 48000, 88200 and 96000 Hz. Quality 1–2 uses native-rate synthesis, 3–4 uses 2× oversampling and 5 uses 4×. Rendered files are WAV, and playback is not started automatically.

## Compact songs

Write notes on a single line or a separate line for each part:

```text
piano c f g2s repeat four bars
```

This creates a piano part and basic drums at 120 BPM, with four body bars, a one-bar intro and a one-bar ending. Common typing slips are accepted as compatibility aliases. `g2s` means G4 for two seconds; `g2` means G in octave 2. A trailing duration such as `piano c f g 2s` applies to every note. Bare notes last one beat and default to octave 4. Notes are repeated through the body, with notes at its end shortened to fit. `do re mi fa sol la ti` and `si` are C-major solfege alternatives. Separate notes with spaces.

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

Patterns default to one bar and grow to whole bars to contain explicit events unless `length` is specified. Pattern length defaults to bars; a note's bare duration defaults to beats. Pitches are MIDI range 0–127, with A4 = 440 Hz. Notes at or above output Nyquist are rejected. Drum names are `kick`, `snare`, `hihat`, `closed_hat`, `open_hat`, `hat`, `clap`, `tom`, `ride`, `cymbal`, and `perc`. A drum pattern on an explicit track uses `instrument drums` or a SoundFont instrument configured with a percussion kit.

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

Paths are relative to the map, key ranges are inclusive, velocity centers are 0–1 and loop endpoints are seconds. The closest root is selected and adjacent velocity layers are interpolated. The map permits 1–2048 zones, 1–32 WAVs per zone and at most 2 MiB. Missing coverage or assets produce an error. The multisampler has no built-in commercial recordings, release samples or pedal-resonance samples. SoundFont playback is a separate instrument engine; VST hosting is not supported. See [multisample details](docs/compact-songs-and-piano.md#recorded-piano-libraries-stereo-multisampling).

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

The built-in instruments are synthesized approximations; commercial piano or VST parity is not established. Features described only in the historical draft—such as arbitrary conversational composition, tempo maps, VST hosting, live MIDI, shared buses and LUFS mastering—are not implemented.


<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:49d931a69141586e6c9b8d86ebb82583ec2116ff36687e149dff0066a25ef412 -->


## Command-line options, explained

| Option | When to use it | Accepted values / default |
| --- | --- | --- |
| `INPUT.mtl` | The song text file to read. | Required except with `--help`, `--version` or `--list-instruments`. |
| `OUTPUT.wav` | Select the destination for this render. | Optional; overrides `output` / `render to`; otherwise `output.wav`. |
| `convert-midi INPUT.mid [OUTPUT.mtl]` | Convert a Standard MIDI File to editable MTL source. | Format 0/1, PPQN timing; tempo changes are represented as note timing at 120 BPM. |
| `--quality N` | Trade more computation for higher internal sample rate. | 1–5; default 3. Pairs 1/2 and 3/4 share algorithms. |
| `--sample-rate N` / `--sample_rate N` | Choose the output sample rate. | 22050, 44100, 48000, 88200, 96000; default 48000. Overrides the script. |
| `--bit-depth N` / `--bit_depth N` | Choose integer PCM resolution. | 16 or 24; default 24. Overrides the script. |
| `--check` | Inspect tempo, duration, inferred tracks and note scheduling without writing a WAV. | Does not decode sample assets. |
| `--list-instruments` | Print the complete default GM name catalog. | No input file required. |
| `--version` | Print the installed package version. | No input file required. |
| `--help` / `-h` | Show usage in the terminal. | No input file required. |

There are no command-line tempo, key, instrument or style flags. Write those in the song file. A rerender with the same seed and inputs is repeatable in the same runtime; changing the rate, quality, sample assets or library versions can change the resulting bytes.

## Parameter rules and processing details

- **Instrument versus track effects:** an instrument declaration defines reusable synthesis and effects. A track's own filter, distortion, delay and reverb are an additional insert chain. Setting a track reverb does not replace an instrument's reverb. Overlapping voices keep independent effect histories.
- **Envelope units:** attack, decay and release are durations, not percentages. Sustain is 0–1. Release starts at the current envelope level, including notes released during attack. Percussion uses its own short natural decay; a held drum event does not become an indefinitely sustained note.
- **LFO units:** `rate 5hz` means five cycles per second; `rate 1/4` means a quarter-note cycle at the song tempo. Effective rates are limited to 0.01–30 Hz. Depth is a frequency offset, not a normalized fraction. Only a sine LFO targeting `filter.cutoff` is implemented. Phase follows the song clock.
- **Filter safety:** cutoff is clamped internally to 20 Hz–45% of internal sample rate. Resonance is Q, not a 0–1 wetness control. Automation of cutoff uses Hz; volume automation uses dB.
- **Delay controls:** `time` is the spacing between echoes; `feedback` is how much carries to later echoes; `mix` balances dry and delayed sound. Echo trains are bounded to three seconds / 64 repeats. Reverb presets use approximate tails of 0.6 seconds (room), 1.5 seconds (hall), and 3 seconds (cathedral).
- **Humanize controls:** timing accepts up to 100 ms and velocity up to 100%. Both are symmetric random deviations around written values, bounded to legal section and velocity ranges. Compact songs already enable small values automatically.
- **Pan controls:** numeric pan is a percentage, −100 left to +100 right. `slightly left` / `slightly right` mean −25 / +25. Mono uses equal-power panning; stereo input uses channel balance. `pan 0` does not collapse a stereo recording to mono.
- **Sound words:** warm/dark/deep reduce cutoff; bright/airy/sharp increase it; soft/gentle/smooth lengthen attack; short/long change decay/release; punchy changes attack/decay; distorted/gritty/aggressive set drive. These descriptions are applied in source order, so a later explicit filter overrides a preceding sound word. Other permitted connecting words do not create additional physical models.
- **Resource limits:** a note gate may be at most 60 seconds. Pattern-line repeat expansion is limited to 100000 events; compiled scheduling and pattern repeats have million-event guards. WAV output uses standard RIFF, up to approximately 4 GiB. Input WAVs are limited to 120 seconds and 64 MiB each. Rendering needs temporary disk space for the floating-point stereo mix as well as the destination file.
- **File formats:** `.mtl` is plain UTF-8 text, preset banks use the same instrument grammar, multisample maps are JSON, and audio input/output is WAV. Standard MIDI format 0/1 files with PPQN timing can be converted to MTL with `mtl convert-midi`; SMPTE-timed and format 2 MIDI files are not supported. MP3, FLAC and proprietary plugin containers are not accepted by this release. SF2 banks are supported as instrument assets through FluidSynth.

## Default General MIDI instrument catalog

<!-- /coderabbit-ai-generated:v1 -->

Program numbers are zero-based. Use the `gm_` name below or its words with spaces. These are synthesized approximations; the names do not imply recorded GM assets.

| Program | Instrument name |
| --- | --- |
| 0 | `gm_acoustic_grand_piano` |
| 1 | `gm_bright_acoustic_piano` |
| 2 | `gm_electric_grand_piano` |
| 3 | `gm_honky_tonk_piano` |
| 4 | `gm_electric_piano_1` |
| 5 | `gm_electric_piano_2` |
| 6 | `gm_harpsichord` |
| 7 | `gm_clavinet` |
| 8 | `gm_celesta` |
| 9 | `gm_glockenspiel` |
| 10 | `gm_music_box` |
| 11 | `gm_vibraphone` |
| 12 | `gm_marimba` |
| 13 | `gm_xylophone` |
| 14 | `gm_tubular_bells` |
| 15 | `gm_dulcimer` |
| 16 | `gm_drawbar_organ` |
| 17 | `gm_percussive_organ` |
| 18 | `gm_rock_organ` |
| 19 | `gm_church_organ` |
| 20 | `gm_reed_organ` |
| 21 | `gm_accordion` |
| 22 | `gm_harmonica` |
| 23 | `gm_tango_accordion` |
| 24 | `gm_nylon_guitar` |
| 25 | `gm_steel_guitar` |
| 26 | `gm_jazz_guitar` |
| 27 | `gm_clean_guitar` |
| 28 | `gm_muted_guitar` |
| 29 | `gm_overdriven_guitar` |
| 30 | `gm_distortion_guitar` |
| 31 | `gm_guitar_harmonics` |
| 32 | `gm_acoustic_bass` |
| 33 | `gm_electric_bass_finger` |
| 34 | `gm_electric_bass_pick` |
| 35 | `gm_fretless_bass` |
| 36 | `gm_slap_bass_1` |
| 37 | `gm_slap_bass_2` |
| 38 | `gm_synth_bass_1` |
| 39 | `gm_synth_bass_2` |
| 40 | `gm_violin` |
| 41 | `gm_viola` |
| 42 | `gm_cello` |
| 43 | `gm_contrabass` |
| 44 | `gm_tremolo_strings` |
| 45 | `gm_pizzicato_strings` |
| 46 | `gm_orchestral_harp` |
| 47 | `gm_timpani` |
| 48 | `gm_string_ensemble_1` |
| 49 | `gm_string_ensemble_2` |
| 50 | `gm_synth_strings_1` |
| 51 | `gm_synth_strings_2` |
| 52 | `gm_choir_aahs` |
| 53 | `gm_voice_oohs` |
| 54 | `gm_synth_voice` |
| 55 | `gm_orchestra_hit` |
| 56 | `gm_trumpet` |
| 57 | `gm_trombone` |
| 58 | `gm_tuba` |
| 59 | `gm_muted_trumpet` |
| 60 | `gm_french_horn` |
| 61 | `gm_brass_section` |
| 62 | `gm_synth_brass_1` |
| 63 | `gm_synth_brass_2` |
| 64 | `gm_soprano_sax` |
| 65 | `gm_alto_sax` |
| 66 | `gm_tenor_sax` |
| 67 | `gm_baritone_sax` |
| 68 | `gm_oboe` |
| 69 | `gm_english_horn` |
| 70 | `gm_bassoon` |
| 71 | `gm_clarinet` |
| 72 | `gm_piccolo` |
| 73 | `gm_flute` |
| 74 | `gm_recorder` |
| 75 | `gm_pan_flute` |
| 76 | `gm_blown_bottle` |
| 77 | `gm_shakuhachi` |
| 78 | `gm_whistle` |
| 79 | `gm_ocarina` |
| 80 | `gm_square_lead` |
| 81 | `gm_saw_lead` |
| 82 | `gm_calliope_lead` |
| 83 | `gm_chiff_lead` |
| 84 | `gm_charang_lead` |
| 85 | `gm_voice_lead` |
| 86 | `gm_fifths_lead` |
| 87 | `gm_bass_lead` |
| 88 | `gm_new_age_pad` |
| 89 | `gm_warm_pad` |
| 90 | `gm_polysynth_pad` |
| 91 | `gm_choir_pad` |
| 92 | `gm_bowed_pad` |
| 93 | `gm_metallic_pad` |
| 94 | `gm_halo_pad` |
| 95 | `gm_sweep_pad` |
| 96 | `gm_rain_fx` |
| 97 | `gm_soundtrack_fx` |
| 98 | `gm_crystal_fx` |
| 99 | `gm_atmosphere_fx` |
| 100 | `gm_brightness_fx` |
| 101 | `gm_goblins_fx` |
| 102 | `gm_echoes_fx` |
| 103 | `gm_sci_fi_fx` |
| 104 | `gm_sitar` |
| 105 | `gm_banjo` |
| 106 | `gm_shamisen` |
| 107 | `gm_koto` |
| 108 | `gm_kalimba` |
| 109 | `gm_bagpipe` |
| 110 | `gm_fiddle` |
| 111 | `gm_shanai` |
| 112 | `gm_tinkle_bell` |
| 113 | `gm_agogo` |
| 114 | `gm_steel_drums` |
| 115 | `gm_woodblock` |
| 116 | `gm_taiko_drum` |
| 117 | `gm_melodic_tom` |
| 118 | `gm_synth_drum` |
| 119 | `gm_reverse_cymbal` |
| 120 | `gm_guitar_fret_noise` |
| 121 | `gm_breath_noise` |
| 122 | `gm_seashore` |
| 123 | `gm_bird_tweet` |
| 124 | `gm_telephone_ring` |
| 125 | `gm_helicopter` |
| 126 | `gm_applause` |
| 127 | `gm_gunshot` |


<!-- /coderabbit-ai-generated:v1 -->