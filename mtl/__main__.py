"""Command line entry point: python -m mtl song.mtl [output.wav]."""

import argparse
import sys
from fractions import Fraction
from pathlib import Path

from . import MTLError, __version__, parse_song, render_song


def main(argv=None):
    parser = argparse.ArgumentParser(description='Render a Music Text Language song to stereo WAV.')
    parser.add_argument('--version', action='version', version=f'MTL {__version__}')
    parser.add_argument('input', nargs='?', type=Path, help='UTF-8 .mtl song file')
    parser.add_argument('--list-instruments', action='store_true', help='show all 128 default General MIDI names')
    parser.add_argument('--check', action='store_true', help='validate input and show inferred tracks without rendering')
    parser.add_argument('output', nargs='?', type=Path, help='override the song output path')
    parser.add_argument('--quality', type=int, choices=range(1, 6), default=3,
                        help='1–2: native rate, 3–4: 2x oversampling, 5: 4x (default: 3)')
    parser.add_argument('--sample-rate', '--sample_rate', type=int, choices=[22050, 44100, 48000, 88200, 96000])
    parser.add_argument('--bit-depth', '--bit_depth', type=int, choices=[16, 24])
    args = parser.parse_args(argv)
    if args.list_instruments:
        from .parser import _gm_bank, _gm_names
        bank = _gm_bank()
        for name in _gm_names():
            print(f"{bank[name].program:3d}  {name.removeprefix('gm_').replace('_', ' ')}")
        return 0
    if args.input is None:
        parser.error('an input song is required (or use --list-instruments)')
    try:
        song = parse_song(args.input.read_text(encoding='utf-8'), base_path=args.input.resolve().parent)
        if args.sample_rate is not None:
            song.sample_rate = args.sample_rate
        if args.bit_depth is not None:
            song.bit_depth = args.bit_depth
        if args.check:
            from .render import compile_timeline, _clip_events
            events = compile_timeline(song)
            _clip_events(song, events)
            print(f"{song.title}: {song.bpm:g} BPM, {song.beats_per_bar} beats/bar, "
                  f"{float(song.length * 60 / Fraction(str(song.bpm))):.3f}s, {len(events)} scheduled notes")
            for message in song.entry_summary:
                print("  " + message)
            for track in song.tracks.values():
                sound = f"{track.instrument} ({song.instruments[track.instrument].engine})" if track.instrument and track.instrument != 'drums' else 'drums' if track.instrument else f'{len(track.clips)} audio clips'
                print(f"  {track.name}: {sound}, pattern {track.pattern or 'none'}, {track.volume:g}dB")
            return 0
        output = args.output or Path(song.output)
        if output.resolve() == args.input.resolve():
            raise MTLError('output must not overwrite the input song')
        result = render_song(song, output, quality=args.quality)
    except (MTLError, OSError, UnicodeError) as exc:
        print(f'mtl: {exc}', file=sys.stderr)
        return 1
    print(f"Rendered {result['path']}: {result['seconds']:.3f}s, {result['events']} notes, "
          f"{song.sample_rate} Hz, stereo {song.bit_depth}-bit PCM")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
