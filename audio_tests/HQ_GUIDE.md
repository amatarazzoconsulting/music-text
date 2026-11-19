<!-- coderabbit-ai-generated:v1 -->

# HQ listening set: arrangements, synthesis and mastering

This set adds ten longer arrangements to the first eight demonstrations. It contains two arrangements of public-domain melodies and eight original compositions in the requested genres. The original tracks are not covers of commercial songs. All sound comes from the Python renderer's procedural instruments; no recordings or commercial VST assets are included.

## Listen in order

| Track | Arrangement and sound design |
| --- | --- |
| [01 · Ode to Joy](hq_01_ode_to_joy.wav) | Beethoven's theme arranged for felt-like piano, supporting bowed strings, vibraphone harmony and a quiet bass foundation. A gradual opening volume lift and brighter supporting harmony shape the entrance. This is the theme, rather than a performance of the complete Ninth Symphony. |
| [02 · The Star-Spangled Banner](hq_02_anthem.wav) | A simplified instrumental arrangement of the traditional anthem melody, with trumpet, strings, organ and bass in 3/4. The brass grows in level while the organ opens in brightness. |
| [03 · Midnight Terrace](hq_03_midnight_terrace.wav) | Original jazz: extended ii–V–I–VI voicings, walking bass, swung ride pattern, piano comping and vibraphone lead. |
| [04 · Copper Street Twelve](hq_04_copper_street.wav) | Original twelve-bar blues in C: dominant-seventh piano chords, rotary drawbar lead, shuffled hats, bass roots/fifths, turnaround and a second lead phrase. |
| [05 · Prism Transit](hq_05_prism_transit.wav) | Original dance: four-on-the-floor drums, detuned plucked saw lead, filtered bass, soft pad, tempo-related echoes and a breakdown before the second section. |
| [06 · Cut Glass](hq_06_cut_glass.wav) | Original breakbeat: syncopated kick pattern, ghost snares, short lead attacks, minor-seventh harmony and a moving bass filter. |
| [07 · Corner Notebook](hq_07_corner_notebook.wav) | Original boom bap: laid-back hats, displaced kicks, ghost snares, minor-seventh piano and vibraphone phrases. Drum hits are synthesized, not sampled from a record. |
| [08 · Sunlit Brass](hq_08_sunlit_brass.wav) | Original brass instrumental: restrained trumpet vibrato, soft room reflections, major-seventh harmony, bass and a light funk rhythm section. |
| [09 · After Hours Circuit](hq_09_after_hours.wav) | Original funk: syncopated bass and kicks, seventh-chord movement, short brass phrases, left/right placement and a contrasting second melody. |
| [10 · Tidal Engine](hq_10_tidal_engine.wav) | Original dubstep: half-time snare, square-wave bass lead with eighth-note cutoff modulation, lightly driven low bass, atmospheric chords and an automated filter opening. |

Each WAV has an editable `.mtl` file with the same basename. The instrument definitions are externalized in [hq_instruments.mtl](hq_instruments.mtl). Look in each song's `over ... in ...` blocks for automation. Sections restart the active patterns, so the second melody uses its own track and pattern rather than relying on a pattern's playhead carrying across the breakdown.

## What makes these renders HQ

- The renderer runs at **quality 5**, using its highest oversampling setting for synthesis/effects, and writes **48 kHz stereo, 24-bit PCM WAV**.
- Piano hammer brightness, soundboard level, detuning, pedal release and stereo image are set explicitly. Strings and brass have adjusted envelopes, cutoff and restrained vibrato. The organ uses its drawbars, percussion and rotary controls.
- Synth voices use small unison detuning, shaped envelopes and filtering. The bass stays centered; supporting parts and leads have modest opposing pan positions.
- Reverb mixes stay small so attacks remain clear. Echo time on the second lead is three quarters of a beat. The dubstep voice also has synchronized cutoff modulation and saturation.
- Section automation changes volume and cutoff. The acoustic melodies gain level over their opening phrase. The originals open gradually, reduce layers in the bridge and fade accompaniment during the outro.
- A final empty section allows release and effect tails to finish. Final-file validation also checks the last ten milliseconds are quiet.

The arrangement controls are audible creative decisions. Quality 5, sample rate and bit depth alone do not establish commercial instrument realism.

## Playback level and master processing

The published WAVs go through an explicit post-render mastering stage using the installed FFmpeg `loudnorm` filter. The working target is **−14 LUFS integrated**, with **−1.5 dBTP** as the processing target and a verified final ceiling of **−1 dBTP**. This is a consistent listening target for this gallery; radio stations and distribution services have their own delivery requirements.

Processing order:

1. Render the mixed arrangement with 3 dB of sample-peak headroom.
2. Apply a 28 Hz high-pass and 19 kHz low-pass to remove unnecessary extremes.
3. Apply a gentle compressor at ratio 1.4:1, threshold 0.2 linear amplitude, 20 ms attack and 180 ms release.
4. Measure loudness, range and true peaks in a first pass.
5. Run a second measured `loudnorm` pass, with dynamic normalization enabled and an 11 LU range setting.
6. Resample the mastered result to 48 kHz and encode 24-bit PCM. Measure the actual encoded WAV again.

The checked tolerance is −14 ±1 LUFS. The manifest reports the measured range and true peak of each file; it does not assume the range setting is achieved exactly. The mastering stage is a gallery utility, not an additional MTL language command. Direct `mtl --quality 5` output contains the song mix and its sample-peak ceiling; it does not apply this loudness process.

The algorithm and filter options are documented in the [official FFmpeg loudnorm reference](https://ffmpeg.org/ffmpeg-filters.html#loudnorm). The anthem arrangement uses the traditional melody; the historical [1814 Carr score](https://commons.wikimedia.org/wiki/File:Star_Spangled_Banner_%28Carr%29_%281814%29.png) is a reference for the composition, not an audio source.

## Reproduce or edit

From the repository root, activate the Python environment described in the main README. The Python package and NumPy/SciPy must be installed. Install FFmpeg separately if it is absent; this gallery was made with FFmpeg 8.0.1. Check `ffmpeg -version` and `ffmpeg -hide_banner -h filter=loudnorm`.

Render and master all ten tracks:

```bash
python audio_tests/render_hq.py --jobs 2
```

Render and master just one:

```bash
python audio_tests/render_hq.py --only hq_05_prism_transit --jobs 1
```

These commands replace the selected HQ WAVs and update `hq_manifest.json`. They leave the original eight demonstrations alone. Lower `--jobs` if memory or CPU capacity is limited. Quality 5 and overlapping piano/strings are expensive: allow several minutes per longer track on a small machine.

To hear the instrument mix before gallery mastering:

```bash
python -m mtl audio_tests/hq_05_prism_transit.mtl unmastered.wav --quality 5
```

Change a single instrument parameter or automation endpoint, rerender the selected track and compare at matched playback volume. Keep the seed unchanged during comparisons. Changing the shared bank affects every song that imports it; rerender all ten when publishing a new version of that bank.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:42be2c01a34ec98bef228271067229e80f3174e8dd6e6d797fd7376d1f4f2c0d -->

## Measured final masters

| Track | Seconds | Integrated LUFS | True peak dBTP |
| --- | ---: | ---: | ---: |
| Ode to Joy - Chamber Theme | 43.20 | -14.00 | -1.96 |
| The Star-Spangled Banner - Brass and Strings | 67.50 | -14.01 | -3.11 |
| Midnight Terrace | 49.29 | -14.14 | -1.46 |
| Copper Street Twelve | 70.19 | -13.96 | -1.48 |
| Prism Transit | 43.12 | -13.96 | -1.46 |
| Cut Glass | 41.19 | -13.96 | -1.48 |
| Corner Notebook | 60.00 | -14.18 | -1.47 |
| Sunlit Brass | 48.42 | -14.12 | -1.50 |
| After Hours Circuit | 47.59 | -14.10 | -1.50 |
| Tidal Engine | 39.43 | -14.14 | -1.50 |

These values were measured from the encoded stereo WAVs.

## Verification and limits

<!-- /coderabbit-ai-generated:v1 -->

[hq_manifest.json](hq_manifest.json) records the render quality, source and bank hashes, renderer-script hash, event counts, frame counts, durations, PCM hashes, integrated loudness, loudness range and sample/true peaks. Every published file passes the renderer's scheduling checks and the gallery driver's final PCM and loudness checks. Numerical checks detect clipping and level inconsistencies; they do not replace a producer listening on monitors and headphones. These are demonstrations of procedural synthesis and arrangement, not a certification of broadcast acceptance or parity with recorded acoustic instruments.
