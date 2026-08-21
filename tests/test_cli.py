import io
import sys

from mafia_sim.cli import _print_event
from mafia_sim.game.state import LogEntry


def test_print_event_survives_characters_the_console_codepage_cant_encode(monkeypatch):
    # Reproduces a real crash: Windows' default console codepage (cp1252) can't encode
    # arbitrary Unicode -- e.g. native-script text from some roster models -- and
    # print() used to take the whole game down instead of just garbling one line.
    # main() now reconfigures stdout with errors="replace"; this confirms that
    # setting actually prevents the crash rather than just hoping it does.
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="replace")
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    entry = LogEntry(day=1, phase="day", kind="thought", speaker="Player1", text="你好世界")
    _print_event(entry)  # must not raise UnicodeEncodeError
    fake_stdout.flush()
