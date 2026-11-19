<!-- coderabbit-ai-generated:v1 -->

# Audio tests: listen, read, and reproduce

These are original generated demonstrations of the Python renderer. All WAVs are stereo 44.1 kHz, 16-bit PCM, quality 3, with no external recordings. Each WAV has the same basename as its editable `.mtl` source.

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

## Reproduce a file

From the repository root after installation:

```bash
python -m mtl audio_tests/easy_piano.mtl audio_tests/easy_piano.wav --sample-rate 44100 --bit-depth 16 --quality 3
python -m mtl audio_tests/instruments.mtl audio_tests/instruments.wav --sample-rate 44100 --bit-depth 16 --quality 3
```

Use the same command with any basename in this directory. The output argument overrides the source's output filename. Renders replace the selected destination after success. All other source controls, including seeds, remain in the `.mtl` file. Lowercase keywords and normal spellings are used in the examples. The renderer retains compatibility aliases for common input mistakes.

`manifest.json` records frame counts, durations, levels, PCM checksums and source checksums. Rendered PCM is checked before a provenance tag is added to the WAV metadata; the tag does not change the audio. File-byte hashes will differ after a fresh CLI render because the CLI does not append the gallery metadata, but PCM remains reproducible with the same environment, source and options.

## Suggested listening exercise

Start with the piano demo and change one note. Next, change the jazz drummer to country and rerender. Compare the dry phrase with the filter and reverb sections of the DSP comparison. Finally, open the automation example and increase or decrease the cutoff ramp endpoints. Keep the seed fixed while comparing sounds.

These demonstrations exercise synthesis and scheduling. They are not a claim that the synthetic instruments match commercial plugins. See the [full tutorial](../document.md) for the progression from compact input to explicit arrangements.
