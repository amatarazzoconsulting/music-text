<!-- coderabbit-ai-generated:v1 -->

# Instrument banks, expressive synthesis and WAV tracks

## What changed

The renderer now adds dedicated **trumpet**, **violin**, **vibes**, **organ**, and single-WAV **sampler** engines. Trumpet and violin use band-limited harmonic spectra, body/formant weighting, onset shaping, delayed vibrato and breath/bow noise; trumpet brightness responds to note velocity. Vibes uses decaying fundamental/upper modes and motor tremolo. Organ has nine drawbars, percussion, a key click and rotary amplitude movement. These are synthetic approximations. They are not validated acoustic physical models, a rotary cabinet simulation, a SoundFont player, or commercial VST equivalents.

The existing oscillator, unison, filter, envelopes, modulation, effects and 2×/4× oversampling remain available. This release does not host VST plugins. For recorded instrument detail, load your own licensed WAV sample.

## Reuse instrument files

```text
import bank "general_midi"
import bank "electronic"
import "my_presets/brass.mtl"

instrument solo from gm_trumpet
    envelope attack 25ms release 200ms
    vibrato rate 5.5hz depth 0.003
```

Built-in banks are `general_midi`, `acoustic`, `organs`, `electronic`, `hybrid`, and `synth1_bank`, shipped inside the Python package. The acoustic, electronic, organ and hybrid banks include expanded original voices made with MTL's piano, pluck, FM, organ, oscillator, effects and layered synthesis models. The Synth1 bank contains 2,000 curated approximate conversions. You can also use `import bank "path/bank.mtl"`. File paths resolve relative to the file declaring the import or WAV, including nested banks. Python callers use `parse_song(text, base_path=Path(...))`; its default base is the working directory. Imported banks may contain only instrument definitions and imports. Repeated imports of the same resolved file load once; cycles, more than 32 nested imports, unknown bases and duplicate instrument names are errors. A preset must be defined/imported before `instrument NAME from PRESET`; each derived instrument is independent.

The General MIDI bank contains all **128 zero-based GM program assignments** as `gm_...` instrument names, with family-specific synthesis settings. It is a program/name map with approximate synthetic voices, not a claim of sampled GM sound fidelity or a MIDI-file player. Examples: `gm_acoustic_grand_piano` (0), `gm_vibraphone` (11), `gm_drawbar_organ` (16), `gm_violin` (40), `gm_trumpet` (56). Percussion-channel mapping is not included. Inspect the bank files in `mtl/presets/` for the complete editable definitions.

## Acoustic and organ presets

Acoustic presets: `concert_trumpet`, `solo_violin`, `studio_vibes`, `acoustic_piano`.

Organ presets include `jazz_drawbar`, `rock_drawbar`, `cathedral_organ`, `soft_reed_organ`, `smoke_wheel`, `bright_leslie`, `stone_pipe`, and `reed_chapel`. Customize the drawbar registrations:

```text
import bank "organs"
instrument my_organ from jazz_drawbar
    drawbars 8 8 8 4 0 0 0 0 0
    rotary 0.8
    percussion 0.2
    distortion light
```

Drawbars are nine levels from 0 to 8 at frequency ratios 0.5, 1.5, 1, 2, 3, 4, 5, 6 and 8 (16′ through 1′). `rotary` is modulation rate 0–10 Hz; 0 stops motion. `percussion` is transient harmonic level 0–1. `vibrato rate 5.5hz depth 0.003` selects rate and fractional pitch deviation (depth 0–0.02); for vibes, rate controls motor tremolo. The engine clips partial generation below internal Nyquist. Envelope, filter and effects commands work with these engines.

## WAV as a playable instrument

```text
instrument sampled_piano
    type sampler
    sample "samples/piano_c4.wav"
    root c4
    envelope attack 2ms decay 200ms sustain 0.8 release 150ms
    reverb room mix 0.15
```

Assign this instrument to a normal note pattern. Notes pitch-shift playback relative to the root using polyphase resampling. Playback is a one-shot with no sustain loop: short samples finish naturally, and long samples are bounded by the note gate and release. Stereo instrument samples are downmixed to mono before synthesis; use an audio track to retain stereo. No velocity layers, round robin, time stretching, multisample zones or automatic loop detection are implemented.

## WAV clips by musical time or section event

```text
length 40 seconds
section intro
    length 4 bars
section chorus
    length 8 bars

track recording
    audio "audio/texture.wav" at 0 seconds
    audio "audio/fill.wav" at 7 beats
    audio "audio/impact.wav" at section chorus
    volume -9db
    pan -20
    filter highpass cutoff 150hz
    distortion light
    delay time 0.25s feedback 0.3 mix 0.15
    reverb hall mix 0.2
```

Clip times are zero-based **offsets** (unlike one-based note positions), in beats, bars, seconds or minutes. `at section NAME` triggers once at the section's start. Note patterns triggering a sampler provide repeated note-event playback. Timed clips are independent of section `add`/`remove` actions; those actions sequence instrument-pattern tracks. A track can contain multiple audio clips or an instrument/pattern pair; use separate tracks to combine both. There is no automatic clipping of a file to the section length: it rings out until its source/effects end or the song ends. Specify song length to include the desired tails; an onset beyond the song length is an error.

Clips retain stereo. Mono clips use equal-power pan; stereo clips use balance, preserving both channels at center. Insert order is filter → saturation → delay → reverb. The same insert commands are also supported directly in instrument tracks, after the instrument's own effects. Volume automation affects clips and tails; filter-cutoff automation on an audio track controls its insert filter. Insert processing is currently per voice/clip rather than a shared bus, so overlapping clips have independent effect histories.

Input WAV supports unsigned 8-bit PCM, signed 16/24/32-bit PCM and floating-point PCM, mono/stereo at 8–192 kHz. Resampling preserves original gain; there is no automatic normalization. Each file is limited to 64 MiB and 120 seconds. Unsupported encodings, missing files and non-finite samples fail explicitly. The output is still stereo 16/24-bit integer WAV. Existing destinations are replaced only after a successful render, and input WAVs cannot be used as the output destination.

## Layered voices, arpeggiator and granular effect

The original MTL hybrid bank is available with `import bank "hybrid"`. Its dual-oscillator voices can blend a second waveform with `oscillator2`, and layered instruments combine other named presets:

```text
import bank "hybrid"
instrument my_layered_voice
    layers velvet_pad glass_string
    layer_balance 0.8 0.45
```

Layer balance values are nonnegative relative weights. Layer references must exist and cannot form cycles. These are native MTL synth combinations, not reproductions of a commercial instrument.

Put a chord pattern on a track and add an arpeggiator to turn each held chord into a repeating note sequence:

```text
track sequence instrument vector_lead pattern harmony
    arpeggiator rate 1/8 mode up_down octaves 2 gate 0.75 pattern 1,3,2,4,0
```

The default is an eighth-note up/down pattern, one octave, and an 85% gate. Modes are `up`, `down`, `up_down` and `random`; a custom comma-separated pattern uses one-based indices into ascending chord pitches across octaves, with `0` for a rest. Rate accepts note values such as `1/8` and triplets such as `1/8t`; gate is 0.05–1.

The `granular` effect is available on instruments and audio-track inserts:

```text
granular size 90ms density 14hz spray 60ms pitch 7 mix 0.25
```

It uses overlapping Hann-windowed grains, shared grain positions for stereo channels, bounded pitch shift, and seeded random spray. Grain size is 5–500 ms, density 1–200 Hz, spray 0–2 s, and pitch shift -24–24 semitones.

Run `mtl search-instruments WORDS` to search bundled preset names, banks, engines and timbral labels. `--bank` limits the search to one built-in bank or an external instrument-only `.mtl` bank, and `--limit` caps the number of results. For a guided song workflow, use `mtl interactive [OUTPUT.mtl]`: choose a bank, instruments, key and melody shape, then inspect patterns and arrange the song's sections from a menu.

The Synth1 converter reads `.sy1` text patches directly from a zip bank, including nested zip files, without extracting the archive. It keeps a diverse subset of at most 2,000 presets by default:

```bash
mtl convert-synth1 zipbank.zip mtl/presets/synth1_bank.mtl
mtl convert-synth1 zipbank.zip smaller_bank.mtl --limit 500
mtl curate-synth1 converted_bank.mtl curated_bank.mtl --limit 2000
```

After generating the package bank, songs can use `import bank "synth1_bank"` and reference a converted instrument by its generated texture/use name. Presets are selected deterministically across oscillator, filter, unison and effect families; original patch names, archive paths and source comments are omitted. `mtl curate-synth1 INPUT.mtl INPUT.mtl` safely replaces a converted bank in place when desired. Oscillator, filter, delay, chorus and saturation values are translated to the closest native controls; MTL's default envelope is used because the archive's legacy envelope fields do not map cleanly to the internal model. Synth1 controls with no MTL equivalent are not reproduced, so the resulting sounds are approximations rather than bit-exact patches. The converter limits archive size and patch count and writes the output only after the full bank has converted successfully.

## Examples

```bash
mtl examples/instrument_showcase.mtl examples/colors.wav --quality 5
mtl examples/wav_session.mtl wav_session.wav --quality 3
mtl examples/hybrid_session.mtl signal_garden.wav --quality 3
mtl examples/slow_granules.mtl soft_light.wav --quality 3
```

The first file auditions trumpet, violin, vibes and four organ registrations. The second imports that rendered WAV at an absolute offset and at a named section while a GM preset plays on another track. The new examples demonstrate layered chords, a programmable arpeggiator, bass and melody parts, and granular textures. `examples/colors.wav` is a local generated asset and is ignored by Git.
