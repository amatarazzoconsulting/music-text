<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:0d030b2164e92d6c57aefd00ee10484b637df2095ae7071e6ca15c88e6dbc0dd -->

<!-- coderabbit-ai-generated-section:v1:7c676c27ebb42294a73cedf10ec7ece276c330db44cb3af18d3faf550c112dc7 -->

# Easier song entry and the piano voice

For the newest shortcuts and piano options, see [compact automatic songs and multisample pianos](compact-songs-and-piano.md).

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:c070e4eb6348a5c0d74201b5cd5b37c62905120c0ece5525700581fd0f903ba4 -->

Existing supported `.mtl` commands continue to work. Shortcuts are expanded into the same instruments, patterns and tracks. The [original product draft](original-product-draft.md) is preserved separately; arbitrary prose and every proposed draft command are not implemented.

<!-- /coderabbit-ai-generated:v1 -->

## Start with an instrument

```text
tempo about ninety bpm
length four bars
piano
    notes c d e g
    volume -8 dB
    pan slightly left

drums house
```

`piano` creates the instrument, pattern and track. Bare notes form a melody with one beat per note; letters without octaves use octave 4. Use `chord c e g for two beats` to play simultaneous notes. Explicit `c4 e4 g4 on 1` still means a chord and retains the original half-beat default gate. `c4 for a beat` plays sequentially, and major/minor phrases such as `c minor for four beats` also work.

Indentation is recommended. After a bare instrument heading, unindented notes and track properties can continue that heading until the next structural instruction. Use indentation and an explicit top-level `length` before the heading to avoid confusing song length with pattern length.

A bare instrument alone auditions `c4 e4 g4 c5`. Top-level bare notes use a piano. Patterns without tracks receive piano tracks (or drum tracks when all notes are drum hits). Tracks with inline notes receive a pattern; a track without an instrument uses its recognized instrument name or a piano. An omitted pattern is inferred from the track's name or the sole available pattern. Multiple ambiguous patterns produce an error.

Defaults: 120 BPM, 4/4, four bars, C4 for omitted octaves, velocity 0.8, track volume −6 dB, centered pan, 48 kHz stereo, 24-bit WAV. Patterns repeat. Explicit song lengths and sections keep their existing behavior.

## General MIDI names are available automatically

No import is required for the 128 bank voices. Spaces, underscores and the `gm_` prefix are accepted, for example:

```text
acoustic grand piano
    chord c3 e3 g3 b3 for four beats
violin
    e5 for two beats
vibraphone
    g5 on beats one three

track brass
    instrument muted trumpet
    c5 for a beat
```

Aliases include `grand piano`, `vibes`, `organ` and `strings`. `panio` is accepted as piano. Other close spellings are accepted only with a sufficiently clear unique match. Explicit instrument definitions take precedence. Custom banks and `instrument NAME from BASE` remain supported, and BASE can now be a built-in name. GM program numbers stay zero-based (0–127). The bank supplies synthesized family approximations and names; it does not provide a sampled GM library.

Inspect the full list or preview inferred tracks without writing a WAV:

```bash
mtl --list-instruments
mtl examples/easy_piano.mtl --check
mtl examples/easy_piano.mtl window_light.wav --quality 5
```

`--check` validates syntax, scheduling and clip references. It does not read or validate WAV assets; rendering performs those checks.

## Forgiving numbers and time

| Entry | Meaning |
| --- | --- |
| `tempo about eighty four bpm` | 84 BPM |
| `length 1:30` | 90 seconds |
| `length two and a half bars` | 2.5 bars |
| `hold half a beat` / `hold 1½ beats` | Exact fractional beats |
| `on beats one two three` | One-based positions 1, 2, 3 |
| `velocity 80 percent` / `vel 80%` | Velocity 0.8 |
| `envelope attack 2 ms release 300 ms` | Millisecond envelope values |
| `filter lowpass cutoff 4000 hz` | 4000 Hz |
| `envelope decay 0,1 s` | 0.1 seconds |
| `volume -8` / `volume -8 dB` | −8 dB |
| `pan slightly left` | 25% left |

Numbers support zero through ninety-nine, halves and quarters, rational fractions, Unicode fractions, optional `about`/`around`/`roughly`/`approximately`, and spacing before ms/s/Hz/dB/percent. Decimal commas are accepted in scalar values and durations; commas in beat and velocity lists remain list separators. Thousands separators are not supported. Existing range and finite-value checks still apply. Do not use percentages for dB volume.

## Drums

```text
drums
    kick x...x...x...x...
    snare on two and four
    hihat every eighth note
```

An `x`/`X` is a hit and `.`/`-` is a rest. A grid divides the pattern length into equal steps. `X` currently has the same velocity as `x`. `drums house` or `drums techno` creates a four-on-the-floor beat; `drums basic` or `drums rock` uses kick on 1 and 3. Add normal drum lines inside the starter block when desired. The original `on`, `every 1/8`, triplet, swing and velocity commands remain available.

## Notes relative to notes

```text
piano
    c4 for two beats
    e4 for a beat
vibraphone
    g5 at 50 percent of piano note one hold half a beat
    b5 after previous note
    c6 at end of piano note two plus half a beat
```

Supported references:

- `after previous note` or `after TRACK note N` — end of its held duration.
- `at start of TRACK note N` / `at end of TRACK note N`.
- `at 25% of TRACK note N` / `at halfway through TRACK note N`.
- `at end of note N` — a note in the current pattern.
- Optional `plus DURATION` or `minus DURATION`.

A note index is one-based **source/expansion order** within a pattern, not pitch order or order after sorting by time. A chord counts as one note event; a beat list or `every` line expands to multiple note events. `previous note` means the preceding expanded event. Forward references work. Cycles, missing notes, negative starts and onsets outside explicit pattern lengths are errors.

Melodic references use the target pattern's written onset and duration, measured from a shared pattern origin, before swing, humanization and section truncation. They repeat with the receiving pattern. They do not dynamically follow every performance occurrence of another track when pattern lengths or section states differ. Use matching pattern lengths for recurring phrases that should stay together.

### Trigger WAV audio from a performed note

```text
track accent
    audio "accent.wav" at end of piano note 1
    audio "texture.wav" at 75% of piano note 2 plus half a beat
    reverb hall mix 0.15
```

Audio references fire once, following the **first actual scheduled occurrence** of the referenced track/note in the arrangement, including its humanized onset and any gate shortening at the section boundary. A chord is one trigger. An instrument entering in a later section moves its clip trigger with it. An unscheduled reference is an error. End means note-off; release, reverb and delay tails are not included. Repeating note-triggered audio can still use the sampler instrument. Existing `audio ... at 2 bars` and `at section NAME` retain their meanings.

## Dedicated piano synthesis

The implicit `piano` and acoustic GM piano presets now use a new `type piano` engine. This intentionally changes their sound from the earlier pluck approximation. Explicit `type pluck`, electric FM pianos, samples and other engines remain available.

The model adds:

- Up to 96 damped string modes with stiff-string inharmonicity, bounded below the internal Nyquist limit.
- One, two or three simulated strings by register, with small detuning and beating.
- A hammer-position spectral shape and velocity-dependent brightness and felt transient.
- Faster decay of high modes, different bass/treble decay, and a blend of fast and slow energy decay.
- Brief soundboard modes and the normal note-off damping, filters, track effects and oversampled rendering.

```text
instrument my_grand from piano
    hammer 0.65
    soundboard 0.35
    string_detune 0.7
    envelope attack 1ms decay 40ms sustain 1 release 350ms
```

`hammer` and `soundboard` are 0–1; `string_detune` is 0–10 cents. Harder hammer values brighten the attack. Higher detuning produces a honky-tonk character. Velocity changes both the spectrum and final note gain. The piano's modes decay naturally even with envelope sustain at 1; a long hold lets them ring until note-off.

This is an original procedural approximation. It has no recorded velocity layers, pedal controller, sympathetic interaction between simultaneously sounding voices, or measured acoustic calibration. Signal tests verify pitch, decay, velocity response and numerical behavior; they do not establish parity with a concert grand or commercial piano VST.

Listen and edit: `examples/easy_piano.mtl` (“Window Light”) and `examples/easy_events.mtl`. The last bar in Window Light removes the tracks to leave space for release/effect tails.


<!-- /coderabbit-ai-generated:v1 -->