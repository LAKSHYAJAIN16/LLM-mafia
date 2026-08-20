from collections import Counter

from mafia_sim.providers.factory import ModelSpec, build_provider
from mafia_sim.sim.tournament import _sample_model_keys, setup_game

ROLE_SETUPS = {8: {"mafia": 2, "detective": 1, "doctor": 1}}
RULES = {"max_format_retries": 1}


def _roster(vendor_counts: dict[str, int]):
    roster = {}
    for vendor, n in vendor_counts.items():
        for i in range(n):
            key = f"{vendor}-{i}"
            spec = ModelSpec(
                key=key, display_name=key, provider="mock", model_id="mock-random", vendor=vendor
            )
            roster[key] = (spec, build_provider(spec))
    return roster


def test_sample_never_repeats_vendor_when_enough_vendors_exist():
    # 8 distinct vendors, one model each -- e.g. anthropic/openai/google/... never collide.
    roster = _roster({f"vendor{i}": 1 for i in range(8)})
    for _ in range(20):
        chosen = _sample_model_keys(roster, player_count=8)
        vendors = [roster[k][0].vendor for k in chosen]
        assert len(vendors) == len(set(vendors)), vendors


def test_sample_avoids_stacking_one_vendor_when_multiple_models_share_it():
    # 3 anthropic models (e.g. Opus/Sonnet/Haiku) plus 7 single-model vendors.
    vendor_counts = {"anthropic": 3, **{f"vendor{i}": 1 for i in range(7)}}
    roster = _roster(vendor_counts)
    for _ in range(20):
        chosen = _sample_model_keys(roster, player_count=8)
        vendors = [roster[k][0].vendor for k in chosen]
        assert len(vendors) == len(set(vendors)), vendors


def test_sample_falls_back_to_round_robin_when_too_few_vendors():
    # Only 3 distinct vendors for 8 seats -- some repeats are unavoidable, but
    # should be spread evenly (each vendor at most ceil(8/3)=3 times) rather
    # than randomly stacked onto one vendor.
    roster = _roster({"a": 4, "b": 4, "c": 4})
    chosen = _sample_model_keys(roster, player_count=8)
    vendors = [roster[k][0].vendor for k in chosen]
    counts = Counter(vendors)
    assert max(counts.values()) <= 3
    assert set(counts.keys()) == {"a", "b", "c"}


def test_setup_game_uses_vendor_diverse_roster():
    vendor_counts = {"anthropic": 3, "openai": 2, "google": 2, **{f"vendor{i}": 1 for i in range(5)}}
    roster = _roster(vendor_counts)
    state, _agents = setup_game(roster, player_count=8, role_setups=ROLE_SETUPS, rules=RULES)
    vendors = [roster[p.model_key][0].vendor for p in state.players]
    assert len(vendors) == len(set(vendors))
