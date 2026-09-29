"""插件装配测试：主模块可导入、API 地址接线、段位/英雄映射覆盖。"""

import sys
from pathlib import Path

# main.py 使用包内相对导入，须以包路径加载
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from astrbot_plugin_owcx.main import (  # noqa: E402
    DEFAULT_API_BASE_URL,
    OverwatchStatsPlugin,
    normalize_api_base_url,
)

# OverFast API 4.13.0 openapi.json 中的 CompetitiveDivision / HeroKey 枚举快照
SPEC_DIVISIONS = {
    "bronze", "silver", "gold", "platinum", "emerald",
    "diamond", "master", "grandmaster", "ultimate",
}
SPEC_HEROES = {
    "ana", "anran", "ashe", "baptiste", "bastion", "brigitte", "cassidy",
    "dmon", "doctrine", "domina", "doomfist", "dva", "echo", "emre",
    "freja", "genji", "hazard", "hanzo", "illari", "jetpack-cat",
    "junker-queen", "junkrat", "juno", "kiriko", "lifeweaver", "lucio",
    "mauga", "mei", "mercy", "mizuki", "moira", "orisa", "pharah",
    "ramattra", "reaper", "reinhardt", "roadhog", "shion", "sigma",
    "sierra", "sojourn", "soldier-76", "sombra", "symmetra", "torbjorn",
    "tracer", "vendetta", "venture", "widowmaker", "winston",
    "wrecking-ball", "wuyang", "zarya", "zenyatta",
}


def test_main_imports_with_stub():
    assert hasattr(OverwatchStatsPlugin, "_api_client")
    assert normalize_api_base_url("https://x.example.com/") == "https://x.example.com"
    assert DEFAULT_API_BASE_URL == "https://overfast-api.tekrop.fr"


def test_rank_mapping_covers_spec():
    from constants import RANK_MAPPING
    from utils import get_rank_display

    missing = SPEC_DIVISIONS - set(RANK_MAPPING)
    assert not missing, f"段位映射缺失: {missing}"
    for div in SPEC_DIVISIONS:
        cn, _ = RANK_MAPPING[div]
        assert cn, div
        text = get_rank_display(div, 1)
        assert "未定位" not in text, div


def test_hero_mapping_covers_spec():
    from constants import HERO_NAME_MAPPING

    assert set(HERO_NAME_MAPPING) == SPEC_HEROES


def test_api_client_uses_configured_base_url():
    custom = "https://my-ow-api.example.com/"
    plugin = OverwatchStatsPlugin(context=None, config={"api_base_url": custom})
    assert plugin.api_base_url == "https://my-ow-api.example.com"
    assert plugin._api_client().base_url == "https://my-ow-api.example.com"

    default_plugin = OverwatchStatsPlugin(context=None, config={})
    assert default_plugin.api_base_url == "https://overfast-api.tekrop.fr"

    bad_plugin = OverwatchStatsPlugin(context=None, config={"api_base_url": "not-a-url"})
    assert bad_plugin.api_base_url == "https://overfast-api.tekrop.fr"
