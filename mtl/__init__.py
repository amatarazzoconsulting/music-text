"""Music Text Language: compile a song description and render stereo PCM WAV."""

from .parser import MTLError, parse_song
from .render import render_song

__version__ = "0.1.0"
__all__ = ["MTLError", "parse_song", "render_song"]
