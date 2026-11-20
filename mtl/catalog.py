"""Searchable index of bundled instrument banks."""

from functools import lru_cache
from pathlib import Path

from . import parse_song

PRESET_BANKS = ("general_midi", "acoustic", "organs", "electronic", "hybrid", "synth1_bank")


@lru_cache(maxsize=len(PRESET_BANKS))
def _bank_entries(bank):
    if bank not in PRESET_BANKS:
        raise ValueError(f"unknown preset bank {bank!r}; choose from {', '.join(PRESET_BANKS)}")
    song = parse_song(f'import bank "{bank}"', _bank=True)
    entries = []
    for instrument in song.instruments.values():
        fields = (
            instrument.name, bank, instrument.engine, instrument.waveform,
            instrument.oscillator2_waveform, instrument.filter_type,
            instrument.reverb_type, instrument.sf2_preset, *instrument.layers,
        )
        entries.append((instrument.name, instrument.engine, " ".join(fields).casefold()))
    return tuple(entries)


def _external_entries(bank):
    path = Path(bank).expanduser().resolve()
    try:
        song = parse_song(path.read_text(encoding="utf-8"), base_path=path.parent, _bank=True)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read preset bank {path}: {exc}") from exc
    if not song.instruments or song.patterns or song.tracks or song.sections:
        raise ValueError(f"{path} is not an instrument-only preset bank")
    entries = []
    for instrument in song.instruments.values():
        fields = (
            instrument.name, path.name, instrument.engine, instrument.waveform,
            instrument.oscillator2_waveform, instrument.filter_type,
            instrument.reverb_type, instrument.sf2_preset, *instrument.layers,
        )
        entries.append((instrument.name, instrument.engine, " ".join(fields).casefold()))
    return tuple(entries), path.name


def search_instruments(query="", *, bank=None, limit=50):
    """Return matching bundled presets, requiring every query word to match."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("search result limit must be positive")
    banks = (bank,) if bank else PRESET_BANKS
    terms = query.casefold().split()
    matches = []
    for bank_name in banks:
        if bank_name in PRESET_BANKS:
            entries, label = _bank_entries(bank_name), bank_name
        else:
            entries, label = _external_entries(bank_name)
        for name, engine, search_text in entries:
            if all(term in search_text for term in terms):
                matches.append({"name": name, "bank": label, "engine": engine})
    return matches[:limit]
