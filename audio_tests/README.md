<!-- coderabbit-ai-generated:v1 -->

# Audio tests: listen, read, and reproduce

These are original generated demonstrations of the Python renderer. The original eight WAVs are stereo 44.1 kHz, 16-bit PCM, quality 3, with no external recordings. Each WAV has the same basename as its editable `.mtl` source.

| WAV | What to listen for |
| --- | --- |
| [easy_piano.wav](easy_piano.wav) | A complete compact piano song: intro, repeated C/F/G phrase, drummer and ending. |
| [song_jazz.wav](song_jazz.wav) | C/Am/F/G piano triads, generated low bass, swung ride groove and fills. |
| [song_reggae.wav](song_reggae.wav) | Piano melody with generated bass and a one-drop drum groove. |
| [song_techno.wav](song_techno.wav) | Single-note synth bass, generated chord support and electronic dance drums. |
| [instruments.wav](instruments.wav) | Trumpet, violin, vibraphone, jazz organ, rock organ, church organ and reed organ, in that order. Each instrument slot is 4.8 seconds; the last part leaves release time. |
| [drum_styles.wav](drum_styles.wav) | Basic, jazz, country, techno, reggae, house, rock and dubstep. Each style has a two-second slot at 120 BPM; drum tails may overlap transitions. |
| [dsp_comparison.wav](dsp_comparison.wav) | The same saw phrase dry, with filter/LFO, with distortion, with delay, then with reverb. Each slot is two seconds; effect tails cross transitions. |
| [filter_automation.wav](filter_automation.wav) | Four seconds of bass alone, an eight-second build with drums and cutoff/volume automation, then four seconds without drums. |
| [song_city_of_lanterns.wav](song_city_of_lanterns.wav) ([source](song_city_of_lanterns.mtl)) | Original hybrid arrangement: velocity-responsive GeneralUser GS electric piano, flute and GM Standard kit with synth bass and pads. 48 kHz/24-bit, quality 5, two-pass mastered to -14 LUFS. |
| [song_blue_hour.wav](song_blue_hour.wav) ([source](song_blue_hour.mtl)) | Original medium-swing jazz arrangement with extended chords, a recurring tenor-sax hook, sampled fingered-bass walking line, FluidR3 GM Jazz 1 kit, Rhodes and vibraphone, plus a subtle synth pad. 48 kHz/24-bit, quality 5, two-pass mastered to -14 LUFS. |

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:843bde9116f9f8710c1d79d33c26419fecfd707d108a63133aa38924e6a4ebd1 -->

## Ten additional HQ arrangements

Listen to the [HQ set and mastering guide](HQ_GUIDE.md): classical theme, anthem, jazz, blues, dance, breakbeat, boom bap, brass instrumental, funk and dubstep. The ten new WAVs are 48 kHz/24-bit quality-5 renders with instrument DSP, section automation and measured loudness mastering. Each has its `.mtl` source and shares an editable instrument bank.

[`five_lanterns.wav`](five_lanterns.wav) and its editable source [`five_lanterns.mtl`](five_lanterns.mtl) make an original 5/4 small-combo jazz sketch with piano comping, a walking bass line, brush groove and vibes melody. The committed 48 kHz/24-bit WAV is two-pass mastered to -14 LUFS and -1.5 dBTP using the process in [HQ_GUIDE.md](HQ_GUIDE.md); rendering the source with `python -m mtl audio_tests/five_lanterns.mtl audio_tests/five_lanterns.wav --quality 5` recreates the unmastered mix.

## Reproduce a file

<!-- /coderabbit-ai-generated:v1 -->

From the repository root after installation:

```bash
python -m mtl audio_tests/easy_piano.mtl audio_tests/easy_piano.wav --sample-rate 44100 --bit-depth 16 --quality 3
python -m mtl audio_tests/instruments.mtl audio_tests/instruments.wav --sample-rate 44100 --bit-depth 16 --quality 3
```

Use the same command with any basename in this directory. The output argument overrides the source's output filename. Renders replace the selected destination after success. All other source controls, including seeds, remain in the `.mtl` file. Lowercase keywords and normal spellings are used in the examples. The renderer retains compatibility aliases for common input mistakes.

The hybrid arrangement uses GeneralUser GS 2.0.3 and FluidSynth. To reproduce it, install FluidSynth's shared library and download the SF2 from the [GeneralUser GS project](https://github.com/mrbumpy409/GeneralUser-GS) into `audio_tests/assets/GeneralUser-GS.sf2`. The bank is intentionally not tracked here; check its author's terms before redistributing it. The bank used for this render has SHA-256 `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe`. This direct MTL command creates an unmastered render:

```bash
python -m mtl audio_tests/song_city_of_lanterns.mtl audio_tests/song_city_of_lanterns.wav --quality 5
```

The jazz arrangement also uses FluidR3 GM for its fingered bass, tenor sax, muted trumpet and Jazz 1 drum kit. Download the [FluidR3 GM release](https://github.com/got-feedBack/feedBack-soundfonts/releases/tag/soundfonts-v1) into `audio_tests/assets/FluidR3_GM.sf2`; the hosting project's README describes it as MIT-style licensed. Its SHA-256 is `74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0`. Both SoundFont banks are optional local assets and are intentionally not tracked in the repository. Render the jazz source directly with `python -m mtl audio_tests/song_blue_hour.mtl audio_tests/song_blue_hour.wav --quality 5`; the gallery master uses the same two-pass FFmpeg process described in [HQ_GUIDE.md](HQ_GUIDE.md).

`manifest.json` records frame counts, durations, levels, PCM checksums and source checksums. Rendered PCM is checked before a provenance tag is added to the WAV metadata; the tag does not change the audio. File-byte hashes will differ after a fresh CLI render because the CLI does not append the gallery metadata, but PCM remains reproducible with the same environment, source and options.

## Suggested listening exercise

Start with the piano demo and change one note. Next, change the jazz drummer to country and rerender. Compare the dry phrase with the filter and reverb sections of the DSP comparison. Finally, open the automation example and increase or decrease the cutoff ramp endpoints. Keep the seed fixed while comparing sounds.

These demonstrations exercise synthesis and scheduling. They are not a claim that the synthetic instruments match commercial plugins. See the [full tutorial](../document.md) for the progression from compact input to explicit arrangements.
