"""Command line entry point for rendering, preset search, guided authoring and conversion."""

import argparse
import sys
from fractions import Fraction
from pathlib import Path

from . import MTLError, __version__, parse_song, render_song


def _convert_midi(argv):
    parser = argparse.ArgumentParser(
        prog='mtl convert-midi',
        description='Convert a Standard MIDI File to editable MTL source.',
    )
    parser.add_argument('input', type=Path, help='Standard MIDI file')
    parser.add_argument('output', nargs='?', type=Path, help='destination .mtl file')
    args = parser.parse_args(argv)
    output = args.output or args.input.with_suffix('.mtl')
    try:
        if output.resolve() == args.input.resolve():
            raise MTLError('output must not overwrite the MIDI input')
        from .midi import midi_to_mtl
        text = midi_to_mtl(args.input.read_bytes(), args.input.stem)
        output.write_text(text, encoding='utf-8')
    except (MTLError, OSError) as exc:
        print(f'mtl: {exc}', file=sys.stderr)
        return 1
    print(f"Created {output}")
    return 0


def _convert_synth1(argv):
    parser = argparse.ArgumentParser(
        prog='mtl convert-synth1',
        description='Convert Synth1 .sy1 patches in a zip bank to an importable MTL preset bank.',
    )
    parser.add_argument('input', type=Path, help='zip bank containing .sy1 patches or nested zip banks')
    parser.add_argument('output', nargs='?', type=Path, help='destination .mtl bank')
    parser.add_argument('--limit', type=int, default=2000, help='maximum diverse presets to write (default: 2000)')
    args = parser.parse_args(argv)
    output = args.output or args.input.with_name(args.input.stem + '_mtl_presets.mtl')
    try:
        from .synth1 import convert_synth1_archive
        count = convert_synth1_archive(args.input, output, limit=args.limit)
    except (MTLError, OSError) as exc:
        print(f'mtl: {exc}', file=sys.stderr)
        return 1
    print(f"Converted {count} Synth1 patches to {output}")
    return 0


def _curate_synth1(argv):
    parser = argparse.ArgumentParser(
        prog='mtl curate-synth1',
        description='Reduce and creatively rename an existing converted Synth1 MTL bank.',
    )
    parser.add_argument('input', type=Path, help='converted Synth1 .mtl bank')
    parser.add_argument('output', nargs='?', type=Path, help='destination bank (default: add _curated)')
    parser.add_argument('--limit', type=int, default=2000, help='maximum diverse presets to keep (default: 2000)')
    args = parser.parse_args(argv)
    output = args.output or args.input.with_name(args.input.stem + '_curated.mtl')
    try:
        from .synth1 import curate_synth1_bank
        count = curate_synth1_bank(args.input, output, limit=args.limit)
    except (MTLError, OSError) as exc:
        print(f'mtl: {exc}', file=sys.stderr)
        return 1
    print(f"Curated {count} Synth1 presets to {output}")
    return 0


def _search_instruments(argv):
    parser = argparse.ArgumentParser(
        prog='mtl search-instruments',
        description='Search bundled presets by name, bank, synthesis engine, and timbral terms.',
    )
    parser.add_argument('query', nargs='?', default='', help='space-separated terms; all terms must match')
    parser.add_argument('--bank', help='search one bundled bank or an external instrument-only .mtl bank')
    parser.add_argument('--limit', type=int, default=50, help='maximum results to print (default: 50)')
    args = parser.parse_args(argv)
    try:
        from .catalog import search_instruments
        results = search_instruments(args.query, bank=args.bank, limit=args.limit)
    except (MTLError, OSError, ValueError) as exc:
        print(f'mtl: {exc}', file=sys.stderr)
        return 1
    if not results:
        print("No matching instruments.")
        return 0
    for instrument in results:
        print(f"{instrument['name']:<36} {instrument['engine']:<14} {instrument['bank']}")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'convert-midi':
        return _convert_midi(argv[1:])
    if argv and argv[0] == 'convert-synth1':
        return _convert_synth1(argv[1:])
    if argv and argv[0] == 'curate-synth1':
        return _curate_synth1(argv[1:])
    if argv and argv[0] == 'search-instruments':
        return _search_instruments(argv[1:])
    if argv and argv[0] == 'interactive':
        from .interactive import run_interactive
        return run_interactive(argv[1:])
    parser = argparse.ArgumentParser(
        description='Render a Music Text Language song to stereo WAV.',
        epilog='Commands: search-instruments, interactive, convert-midi, convert-synth1, curate-synth1',
    )
    parser.add_argument('--version', action='version', version=f'MTL {__version__}')
    parser.add_argument('input', nargs='?', type=Path, help='UTF-8 .mtl song file')
    parser.add_argument('--list-instruments', action='store_true', help='show all 128 default General MIDI names')
    parser.add_argument('--check', action='store_true', help='validate input and show inferred tracks without rendering')
    parser.add_argument('--verify-soundfont', metavar='SF2', type=Path,
                        help='verify an SF2 file and list its presets')
    parser.add_argument('output', nargs='?', type=Path, help='override the song output path')
    parser.add_argument('--quality', type=int, choices=range(1, 6), default=3,
                        help='1–2: native rate, 3–4: 2x oversampling, 5: 4x (default: 3)')
    parser.add_argument('--sample-rate', '--sample_rate', type=int, choices=[22050, 44100, 48000, 88200, 96000])
    parser.add_argument('--bit-depth', '--bit_depth', type=int, choices=[16, 24])
    args = parser.parse_args(argv)
    if args.verify_soundfont:
        try:
            from .soundfont import verify_soundfont
            info = verify_soundfont(args.verify_soundfont)
        except MTLError as exc:
            print(f'mtl: {exc}', file=sys.stderr)
            return 1
        print(f"SoundFont: {info['path']}")
        print(f"  Size: {info['bytes']} bytes, {info['sample_frames']} 16-bit sample frames")
        print(f"  Presets: {info['preset_count']}")
        for name in info['presets']:
            print(f"    {name}")
        return 0
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
