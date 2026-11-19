<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8b93a833b356382bbc6dccd1891e85623ed4c8699f3667fb21e8ad1ee6f4f1ce -->

# Audio algorithm assessment

## Piano update

The implicit piano now uses a dedicated modal approximation with inharmonic string modes, register-dependent detuned strings, dynamic hammer spectra, two-stage modal decay and brief body resonances. This replaces the earlier pluck default. See [piano controls, tests and limitations](friendly-entry-and-piano.md#dedicated-piano-synthesis).

<!-- /coderabbit-ai-generated:v1 -->

## Baseline inspected

The repository at `28c8fed88db942b819ab95b3f310c7fa59987419` contained only README.md: a product manual with embedded C++ source drafts, without a buildable project, dependency manifest or executable tests. Findings below are based on those snippets, not measured behavior of an installed original engine. The new Python implementation provides a runnable core and does not establish equivalence to commercial synthesizers named in the draft.

## Problems and implemented solutions

| Draft location | Problem | Python solution |
| --- | --- | --- |
| `generateAudio`, `generatePattern`, `mixTracks` | Every pattern writes drum buffers directly into the master. Tracks, instruments, pattern loops and arrangement are not routed through a common event scheduler; `mixTracks` only normalizes. | Parse a typed song, resolve patterns/sections into absolute note events, synthesize the selected instrument, and apply velocity, track dB gain and pan before summing. |
| `synthesizeKick` | `sin(2π f(t) t)` has instantaneous frequency `f(t) + t f′(t)`, distorting the requested sweep. | For `f(t)=f_end+Δf exp(-t/τ)`, use phase `2π[f_end t + Δf τ(1-exp(-t/τ))]`. The derivative gives the intended sweep. |
| `synthesizeWavetable` | Naive saw/square discontinuities fold high harmonics below Nyquist; unison supports only sine/saw in its secondary path and offsets are asymmetric. | PolyBLEP correction for saw/square, a finite odd-harmonic triangle, and symmetric detuned voices. 2×/4× oversampling plus filtered decimation reduces nonlinear aliasing. This reduces aliasing rather than promising its elimination. |
| `applyEnvelope` | The fixed buffer's final release region assumes sustain level; note-off during attack/decay can jump. Units are also used differently across drum and envelope code. | Parse ms/s into seconds once; release from the actual ADS level at note-off, with short boundary ramps. Gate and release are distinct. |
| `applyEQ` | Low/high-pass normalization is usable, but the peak branch divides by `1+alpha` while its denominator requires `1+alpha/A`. Shelf normalization also needs its own denominator. | Implement the required low/high-pass RBJ biquads with the complete denominator and safe Q/cutoff bounds. Do not expose incorrect peak/shelf EQ. |
| `applyCompression` | `gain=(level/threshold)^(-1/ratio)` gives output slope `1-1/ratio` above threshold; the desired ratio needs exponent `1/ratio-1`. | Do not advertise an unverified compressor. Attenuation-only sample peak control prevents sample overload while preserving a quiet mix. A future compressor should validate its static curve, attack/release, stereo linking and gain reduction separately. |
| `applyReverb` | One feedback delay creates a comb/echo with strong periodic coloration rather than a diffuse room. | Seeded, damped, diffuse FIR response and FFT convolution, with bounded room tails. This is a basic mono ambience effect; stereo room geometry and commercial realism are outside the current claim. |
| `writeWAV` | The fallback writes float samples while the header keeps format tag 1 (integer PCM), so 32-bit output is mislabeled. No dither or RIFF overflow guard is present. | Explicit little-endian 16/24-bit PCM, TPDF dither for nonzero samples, exact frame count, RIFF size guard, and atomic destination replacement. Unsupported formats fail explicitly. |
| Import methods / mastering description | SoundFont/bank loading is placeholder code; normalization is not LUFS measurement or transparent limiting. | Reject unsupported imports and LUFS commands. Clearly document the implemented sample peak ceiling and synthesized acoustic approximations. |

## Timing and mixing decisions

The musical clock uses rational quarter-note beats. A timestamp is rounded once as `round(beat × 60 × sample_rate / bpm)`; repeating a rounded “samples per beat” value would accumulate error at tempos such as 137 BPM. Note positions are one based, with a single conversion to zero-based offsets. Meter determines beats per bar; BPM continues to count quarter notes in 6/8.

The mix remains float32 on disk until export. A global attenuation factor applies only when the measured sample peak exceeds the selected ceiling. Constant-power panning uses `left=cos(theta)` and `right=sin(theta)`, with `theta=(pan+1)π/4`. Independent normalization of each track would destroy intentional balance and is avoided.

Plucked sounds sum harmonic modes with frequency-dependent damping. Bells sum inharmonic modes. These are useful deterministic synthetic timbres, not validated models of a sampled piano, a bowed violin or an acoustic body. Future realism work should add a properly licensed multisample/SoundFont playback engine with pitch resampling, velocity layers, loop crossfades and explicit missing-asset errors.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:b91d18f4469f2575172a08055bb936774fafd1c06c6dbf63e131d9ef50d5c88a -->

## Time-varying filter and mix controls

The Python renderer evaluates section automation against the absolute sample clock, and the sine LFO against the same clock. The cutoff is updated at 1 kHz in the oversampled domain. At every update, the RBJ coefficients are recalculated and the filter's state is reconstructed from its last two input and output samples. This avoids resetting the filter at each control update, but changing coefficients can still produce artifacts with extreme depth or resonance; fixed-coefficient stability alone does not establish stability under every time-varying sweep. Cutoff bounds and finite-output checks reduce the risk, and extreme settings have regression coverage. Track-volume automation is applied per output sample to each contribution, including effect tails. Different tracks sharing an instrument retain independent automation.

Ramps are linear in Hz for cutoff and dB for volume, with the final value held through the section. They reset to the configured value outside that section. Values are composed with the LFO before bounding cutoff. The implementation makes no LUFS or true-peak claims.

## Validation strategy

<!-- /coderabbit-ai-generated:v1 -->

Tests independently measure rendered pitch and spectral alias energy, check known musical timestamps over many repeats, decode signed 16/24-bit PCM, inspect actual WAV headers/frame counts, verify panning and relative gain, and exercise CLI errors. Seeded repeat renders must have identical bytes in the same dependency environment. Exact output bytes across different NumPy/SciPy releases are not guaranteed. Automated signal checks do not replace listening or comparisons against reference recordings.

For production mastering, the next steps are a measured BS.1770 loudness implementation and oversampled true-peak detection, with reference vectors and listening comparisons. For larger arrangements, replace per-note full buffers and repeated convolution with block voices, shared effect buses and partitioned convolution. The present implementation already keeps the full song mix on disk.

## Primary references checked

- [W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/): normalized biquad coefficients and filter-specific denominators.
- [SciPy polyphase resampling](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html): FIR filtering before decimation.
- [SciPy SOS filtering](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html): second-order sections in direct-form II transposed structure.

No external source is evidence that this renderer meets a commercial audio quality standard. Its guarantees are the implemented behavior and measured regression checks described above.
