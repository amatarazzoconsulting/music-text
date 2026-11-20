"""Guided terminal song composer and lightweight arrangement editor."""

import argparse
import json
import os
import random
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import MTLError, parse_song
from .catalog import PRESET_BANKS, search_instruments
from .render import compile_timeline

_BANKS = (
    ("Electronic", "electronic"),
    ("Acoustic", "acoustic"),
    ("Organs", "organs"),
    ("Hybrid", "hybrid"),
    ("Synth1 textures", "synth1_bank"),
)
_KEYS = (
    ("C major", "c", False, 0),
    ("G major", "g", False, 7),
    ("D major", "d", False, 2),
    ("A minor", "a", True, 9),
    ("D minor", "d", True, 2),
    ("E minor", "e", True, 4),
)
_MELODIES = ("ascending", "descending", "arch", "pulse", "random")
_SCALE_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_SCALE_MINOR = (0, 2, 3, 5, 7, 8, 10)
_PITCH_NAMES = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")
_ACTIVE_TRACKS = {
    "intro": ("harmony", "bass", "lead_intro"),
    "verse": ("harmony", "bass", "drums", "lead_verse"),
    "chorus": ("harmony", "bass", "drums", "lead_chorus"),
    "bridge": ("harmony", "bass", "lead_bridge"),
    "outro": ("harmony", "bass", "lead_outro"),
    "tail": ("harmony",),
}
_SECTION_LENGTHS = {"intro": 2, "verse": 4, "chorus": 4, "bridge": 2, "outro": 2, "tail": 1}


@dataclass
class ArrangementSection:
    name: str
    kind: str
    bars: int


def _note_name(midi_note):
    return f"{_PITCH_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


def _slug(text):
    slug = re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")
    return slug or "new_song"


class InteractiveComposer:
    """Generate an editable arrangement, then allow section-level timeline edits."""

    def __init__(self, title, bpm, key_name, tonic, minor, tonic_midi, bank, lead, accompaniment, melody):
        self.title = title
        self.bpm = bpm
        self.key_name = key_name
        self.tonic = tonic
        self.minor = minor
        self.tonic_midi = tonic_midi
        self.bank = bank
        self.lead = lead
        self.accompaniment = accompaniment
        self.melody = melody
        self.output_name = _slug(title) + ".wav"
        self.sections = [
            ArrangementSection("intro", "intro", 2),
            ArrangementSection("verse", "verse", 4),
            ArrangementSection("chorus", "chorus", 4),
            ArrangementSection("verse_2", "verse", 4),
            ArrangementSection("chorus_2", "chorus", 4),
            ArrangementSection("outro", "outro", 2),
            ArrangementSection("tail", "tail", 1),
        ]
        self.patterns = self._make_patterns()

    def _scale_note(self, degree, octave):
        scale = _SCALE_MINOR if self.minor else _SCALE_MAJOR
        return _note_name(12 * (octave + 1) + self.tonic_midi + scale[degree % 7] + 12 * (degree // 7))

    def _chord(self, degree):
        return " ".join(self._scale_note(degree + interval, 3) for interval in (0, 2, 4))

    def _melody_degrees(self):
        rng = random.Random(27)
        shapes = {
            "ascending": (0, 1, 2, 3, 4, 5, 6, 5),
            "descending": (6, 5, 4, 3, 2, 1, 0, 1),
            "arch": (0, 2, 4, 6, 5, 3, 1, 0),
            "pulse": (0, 0, 2, 2, 4, 4, 2, 2),
            "random": tuple(rng.randrange(7) for _ in range(8)),
        }
        return shapes[self.melody]

    def _melody_lines(self, degrees, *, octave=4, velocity=0.7, reverse=False, count=8):
        values = tuple(reversed(degrees)) if reverse else degrees
        lines = []
        for index, degree in enumerate(values[:count]):
            note = self._scale_note(degree, octave)
            beat = index * 2 + 1
            length = 1.5 if index % 2 == 0 else 0.75
            strength = min(0.94, velocity + (0.05 if index % 4 == 0 else 0))
            lines.append(f"    {note} on {beat} hold {length:g} beats vel {strength:.2f}")
        return lines

    def _make_patterns(self):
        degrees = self._melody_degrees()
        progression = (0, 4, 5, 3) if not self.minor else (0, 5, 2, 6)
        chords, bass = [], []
        for bar, degree in enumerate(progression):
            start = bar * 4
            chords.append(f"    {self._chord(degree)} on {start + 1} hold 3.5 beats vel {0.52 + (bar % 2) * 0.04:.2f}")
            bass.append(f"    {self._scale_note(degree, 2)} on {start + 1} hold 1.5 beats vel 0.72")
            bass.append(f"    {self._scale_note(degree + 4, 2)} on {start + 3} hold 0.75 beats vel 0.58")
        return {
            "chords": (4, chords),
            "bassline": (4, bass),
            "groove": (1, [
                "    kick on 1, 3",
                "    snare on 2, 4 vel 0.56",
                "    hihat every 1/8 vel 0.3",
            ]),
            "lead_intro": (4, self._melody_lines(degrees, velocity=0.56, count=4)),
            "lead_verse": (4, self._melody_lines(degrees, velocity=0.68)),
            "lead_chorus": (4, self._melody_lines(degrees, octave=5, velocity=0.78)),
            "lead_bridge": (4, self._melody_lines(degrees, octave=4, velocity=0.62, reverse=True)),
            "lead_outro": (4, self._melody_lines(degrees, velocity=0.5, reverse=True, count=4)),
        }

    def add_section(self, kind, bars=None):
        if kind not in _SECTION_LENGTHS or kind == "intro" or kind == "tail":
            raise ValueError("only verse, chorus, bridge, and outro sections can be added")
        bars = _SECTION_LENGTHS[kind] if bars is None else bars
        if not isinstance(bars, int) or not 1 <= bars <= 32:
            raise ValueError("section length must be from 1 to 32 bars")
        used_names = {section.name for section in self.sections}
        name = kind
        number = 2
        while name in used_names:
            name = f"{kind}_{number}"
            number += 1
        self.sections.append(ArrangementSection(name, kind, bars))

    def move_section(self, from_index, to_index):
        if not (0 <= from_index < len(self.sections) and 0 <= to_index < len(self.sections)):
            raise ValueError("section number is outside the timeline")
        section = self.sections.pop(from_index)
        self.sections.insert(to_index, section)

    def remove_section(self, index):
        if not 0 <= index < len(self.sections):
            raise ValueError("section number is outside the timeline")
        if len(self.sections) == 1:
            raise ValueError("a song must keep at least one section")
        return self.sections.pop(index)

    def source(self):
        rows = [
            f"song {json.dumps(self.title)}",
            f"bpm {self.bpm:g}",
            f"key {self.tonic} {'minor' if self.minor else 'major'}",
            "seed 27",
            f"output {json.dumps(self.output_name)}",
            f'import bank "{self.bank}"',
            "",
        ]
        for name, (bars, notes) in self.patterns.items():
            rows.extend([f"pattern {name}", f"    length {bars} bars", *notes, ""])
        rows.extend([
            f"track harmony instrument {self.accompaniment} pattern chords volume -11db pan -12",
            "track bass instrument bass pattern bassline volume -8db",
            "track drums instrument drums pattern groove volume -11db",
        ])
        for name in ("lead_intro", "lead_verse", "lead_chorus", "lead_bridge", "lead_outro"):
            rows.append(f"track {name} instrument {self.lead} pattern {name} volume -8db pan 12")
        rows.append("")
        for section in self.sections:
            tracks = _ACTIVE_TRACKS[section.kind]
            rows.extend([f"section {section.name}", f"    length {section.bars} bars", f"    only {tracks[0]}"])
            rows.extend(f"    add {track}" for track in tracks[1:])
        rows.extend(["", "humanize all tracks", "    timing +/-5ms", "    velocity +/-4%"])
        return "\n".join(rows) + "\n"

    def pattern_text(self):
        rows = []
        for name, (bars, notes) in self.patterns.items():
            rows.append(f"{name} ({bars} bar{'s' if bars != 1 else ''}, {len(notes)} events)")
            rows.extend(f"  {line.strip()}" for line in notes)
        return "\n".join(rows)

    def timeline_text(self):
        rows = []
        total_bars = 0
        for index, section in enumerate(self.sections, 1):
            tracks = ", ".join(_ACTIVE_TRACKS[section.kind])
            seconds = section.bars * 4 * 60 / self.bpm
            rows.append(f"{index:2d}. {section.name:<12} {section.bars:2d} bars ({seconds:5.1f}s)  [{tracks}]")
            total_bars += section.bars
        seconds = total_bars * 4 * 60 / self.bpm
        rows.append(f"Total: {total_bars} bars, {seconds:.1f}s at {self.bpm:g} BPM; {len(self.sections)} sections.")
        return "\n".join(rows)

    def summary(self):
        events = sum(len(notes) for _, notes in self.patterns.values())
        bars = sum(section.bars for section in self.sections)
        return (
            f"{self.title} | {self.bpm:g} BPM | {self.key_name} | "
            f"{bars} bars / {bars * 4 * 60 / self.bpm:.1f}s | "
            f"{self.bank} bank | lead: {self.lead} | harmony: {self.accompaniment} | "
            f"{len(self.patterns)} patterns / {events} pattern events"
        )


def _save(composer, destination):
    destination = Path(destination).resolve()
    source = composer.source()
    song = parse_song(source, base_path=destination.parent)
    events = compile_timeline(song)
    if not events:
        raise MTLError("the arrangement has no scheduled notes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=destination.parent,
                prefix=".mtl-interactive-", suffix=".mtl", delete=False) as output:
            temporary = Path(output.name)
            output.write(source)
        os.replace(temporary, destination)
    except OSError as exc:
        raise MTLError(f"cannot save song source {destination}: {exc}") from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return destination, song, len(events)


def run_interactive(argv=None, *, input_fn=input, stream=None):
    parser = argparse.ArgumentParser(
        prog="mtl interactive",
        description="Create a melody-led song and edit its arrangement from terminal menus.",
    )
    parser.add_argument("output", nargs="?", type=Path, help="destination .mtl source")
    parser.add_argument("--force", action="store_true", help="allow replacing an existing source file")
    args = parser.parse_args(argv)
    stream = stream or sys.stdout

    def show(text=""):
        print(text, file=stream)

    def prompt(text):
        return input_fn(text).strip()

    def menu(title, options):
        show(title)
        for index, value in enumerate(options, 1):
            show(f"  {index}. {value}")
        while True:
            answer = prompt("Choose a number (q to cancel): ").casefold()
            if answer == "q":
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            show(f"Enter a number from 1 to {len(options)}, or q.")

    try:
        title = prompt("Song title [Texture Study]: ") or "Texture Study"
        while True:
            raw_bpm = prompt("Tempo in BPM [108]: ") or "108"
            try:
                bpm = float(raw_bpm)
            except ValueError:
                bpm = 0
            if 30 <= bpm <= 240:
                break
            show("Tempo must be from 30 to 240 BPM.")

        key_choice = menu("Choose a key:", [key[0] for key in _KEYS])
        if key_choice is None:
            return 0
        key_name, tonic, minor, tonic_midi = _KEYS[key_choice]

        bank_choice = menu("Choose a preset bank:", [label for label, _ in _BANKS])
        if bank_choice is None:
            return 0
        bank = _BANKS[bank_choice][1]

        def choose_preset(label):
            while True:
                query = prompt(f"Search {label} presets (blank lists the first matches): ")
                try:
                    hits = search_instruments(query, bank=bank, limit=20)
                except ValueError as exc:
                    show(str(exc))
                    return None
                if not hits:
                    show("No presets matched; try another search.")
                    continue
                show(f"{label} choices:")
                for index, hit in enumerate(hits, 1):
                    show(f"  {index:2d}. {hit['name']} ({hit['engine']})")
                answer = prompt("Preset number, or q to cancel: ").casefold()
                if answer == "q":
                    return None
                if answer.isdigit() and 1 <= int(answer) <= len(hits):
                    return hits[int(answer) - 1]["name"]
                show(f"Enter a number from 1 to {len(hits)}, or q.")

        lead = choose_preset("lead")
        if lead is None:
            return 0
        accompaniment_choice = menu("Choose harmony sound:", [f"Reuse {lead}", "Select another preset"])
        if accompaniment_choice is None:
            return 0
        accompaniment = lead if accompaniment_choice == 0 else choose_preset("harmony")
        if accompaniment is None:
            return 0

        melody_choice = menu("Choose a melody shape:", _MELODIES)
        if melody_choice is None:
            return 0
        composer = InteractiveComposer(
            title, bpm, key_name, tonic, minor, tonic_midi, bank,
            lead, accompaniment, _MELODIES[melody_choice],
        )
        show("")
        show(composer.summary())
        show(composer.timeline_text())

        while True:
            choice = menu(
                "Arrangement editor:",
                ("Show patterns and notes", "Show timeline", "Song information",
                 "Append a section", "Move a section", "Remove a section",
                 "Save song source", "Quit"),
            )
            if choice is None or choice == 7:
                return 0
            if choice == 0:
                show(composer.pattern_text())
            elif choice == 1:
                show(composer.timeline_text())
            elif choice == 2:
                show(composer.summary())
            elif choice == 3:
                kind_choice = menu("Section to append:", ("Verse", "Chorus", "Bridge", "Outro"))
                if kind_choice is None:
                    continue
                kind = ("verse", "chorus", "bridge", "outro")[kind_choice]
                default_bars = _SECTION_LENGTHS[kind]
                raw_bars = prompt(f"Length in bars [{default_bars}]: ") or str(default_bars)
                try:
                    composer.add_section(kind, int(raw_bars))
                except ValueError as exc:
                    show(f"Cannot add section: {exc}")
                else:
                    show(composer.timeline_text())
            elif choice == 4:
                show(composer.timeline_text())
                try:
                    source_index = int(prompt("Move section number: ")) - 1
                    target_index = int(prompt("To position number: ")) - 1
                    composer.move_section(source_index, target_index)
                except ValueError as exc:
                    show(f"Cannot move section: {exc}")
                else:
                    show(composer.timeline_text())
            elif choice == 5:
                show(composer.timeline_text())
                try:
                    index = int(prompt("Remove section number: ")) - 1
                    removed = composer.remove_section(index)
                except ValueError as exc:
                    show(f"Cannot remove section: {exc}")
                else:
                    show(f"Removed {removed.name}.")
                    show(composer.timeline_text())
            else:
                destination = args.output
                if destination is None:
                    default = _slug(title) + ".mtl"
                    destination = Path(prompt(f"Save as [{default}]: ") or default)
                if destination.exists() and not args.force:
                    overwrite = prompt(f"{destination} exists. Replace it? [y/N]: ").casefold()
                    if overwrite not in {"y", "yes"}:
                        show("Save cancelled.")
                        continue
                destination, song, event_count = _save(composer, destination)
                show(f"Saved {destination}: {event_count} scheduled notes, "
                     f"{song.bpm:g} BPM, {float(song.length * 60 / song.bpm):.1f}s.")
                return 0
    except EOFError:
        show("")
        show("Input ended; leaving the composer without saving.")
        return 0
    except (MTLError, OSError) as exc:
        print(f"mtl: {exc}", file=sys.stderr)
        return 1
