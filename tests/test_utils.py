import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bindings import normalize_loaded  # noqa: E402
from utils import (  # noqa: E402
    build_rank_data,
    extract_top_heroes,
    format_number,
    format_time_played,
    get_rank_display,
    normalize_player_id,
    resolve_gamemode,
    resolve_hero_name,
    resolve_platform,
    resolve_region,
    validate_player_id,
)


def test_normalize():
    assert normalize_player_id("TeKrop#2217") == "TeKrop-2217"


def test_validate_ok():
    assert validate_player_id("TeKrop#2217") == "TeKrop-2217"


def test_validate_bad():
    for bad in ["a", "x" * 33, "a/b", "a..b"]:
        try:
            validate_player_id(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_rank_display():
    assert get_rank_display("diamond", 3) == "钻石 III"
    assert get_rank_display(None, None) == "未定位"
    assert get_rank_display("master", None) == "大师"


def test_build_rank_fallback():
    s = {"competitive": {"console": {"tank": {"division": "gold", "tier": 2}}}}
    plat, rows = build_rank_data(s, "pc")
    assert plat == "console"
    assert rows[0]["rank_text"] == "黄金 II"


def test_extract_top_heroes():
    stats = {"pc": {"quickplay": {"heroes_comparisons": {"time_played": {"values": [
        {"hero": "genji", "value": 100}, {"hero": "ana", "value": 50}]}}}, "competitive": {}}}
    assert extract_top_heroes(stats, "pc")[0][0] == "genji"


def test_resolve():
    assert resolve_gamemode("竞技") == "competitive"
    assert resolve_platform("主机") == "console"
    assert resolve_region("亚服") == "asia"
    assert resolve_hero_name("源氏") == "genji"
    assert resolve_hero_name("Genji") == "genji"


def test_format():
    assert format_time_played(3660) == "1小时1分钟"
    assert format_number(12345) == "12,345"


def test_bindings_migrate():
    assert normalize_loaded("Foo-123", "pc") == {
        "accounts": [{"player_id": "Foo-123", "platform": "pc"}], "default": "Foo-123"}
    old = {"player_id": "Foo-123", "platform": "bad"}
    out = normalize_loaded(old, "pc")
    assert out["accounts"][0]["platform"] == "pc"
