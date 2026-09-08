import io
import sys

from mafia_sim.cli import DEFAULT_RULES_CONFIG, _load_deception_hints, _print_event, load_rules
from mafia_sim.game.state import LogEntry
from mafia_sim.providers.factory import ModelSpec, build_provider
from mafia_sim.sim.logger import ResultsLogger
from mafia_sim.sim.tournament import run_tournament


def _mock_roster():
    spec = ModelSpec(key="mock-random", display_name="Mock", provider="mock", model_id="mock-random")
    return {"mock-random": (spec, build_provider(spec))}


def test_opponent_aware_hints_flow_end_to_end_through_mock_games(tmp_path):
    # Full zero-cost pipeline check: real logged games -> _load_deception_hints (the same
    # helper cmd_run uses when opponent_aware_deception is on) -> threaded through
    # run_tournament -> present on the resulting GameState. Prompt rendering itself is
    # covered separately in test_prompts.py.
    out = str(tmp_path)
    rules = load_rules(DEFAULT_RULES_CONFIG)
    rules["max_days"] = 4  # keep the mock games short

    run_tournament(
        roster=_mock_roster(),
        player_count=6,
        num_games=2,
        role_setups=rules["role_setups"],
        rules=rules,
        logger=ResultsLogger(out),
    )

    hints = _load_deception_hints(out, min_opportunities=1)
    assert hints
    assert all(0.0 <= rate <= 1.0 and n >= 1 for rate, n in hints.values())

    results = run_tournament(
        roster=_mock_roster(),
        player_count=6,
        num_games=1,
        role_setups=rules["role_setups"],
        rules=rules,
        logger=ResultsLogger(out),
        deception_hints=hints,
    )
    assert results[0].state.deception_hints == hints


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
