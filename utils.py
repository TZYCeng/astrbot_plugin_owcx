"""纯函数工具：归一化/解析/格式化/数据提取，可单测。"""
from __future__ import annotations

import re
from urllib.parse import quote

try:
    from .constants import (
        GAMEMODE_REVERSE_MAPPING,
        HERO_NAME_MAPPING,
        HERO_NAME_REVERSE_MAPPING,
        PLATFORM_MAPPING,
        PLATFORM_REVERSE_MAPPING,
        RANK_MAPPING,
        REGION_MAPPING,
        REGION_REVERSE_MAPPING,
        ROLE_MAPPING,
    )
except ImportError:  # pytest 直接导入时回退
    from constants import (
        GAMEMODE_REVERSE_MAPPING,
        HERO_NAME_MAPPING,
        HERO_NAME_REVERSE_MAPPING,
        PLATFORM_MAPPING,
        PLATFORM_REVERSE_MAPPING,
        RANK_MAPPING,
        REGION_MAPPING,
        REGION_REVERSE_MAPPING,
        ROLE_MAPPING,
    )

_PLAYER_ID_RE = re.compile(r"^[A-Za-z0-9\u4e00-\u9fa5_\- ]{3,32}$")
_TIER_ROMAN = ["", "I", "II", "III", "IV", "V"]


def normalize_player_id(player_id: str) -> str:
    """# -> - 并 strip，不做合法性校验。"""
    return player_id.replace("#", "-").strip()


def validate_player_id(player_id: str) -> str:
    """归一化 + 合法性校验，非法时抛 ValueError。

    允许字母/数字/中文/_/-/空格，长度归一化后 3~32，且必须含 - 分隔符。
    返回可直接拼 URL path 的 quote 结果。
    """
    norm = normalize_player_id(player_id)
    if len(norm) < 3 or len(norm) > 32:
        raise ValueError(f"玩家 ID 长度非法: {player_id!r}")
    if "/" in player_id or "\\" in player_id or ".." in norm:
        raise ValueError(f"玩家 ID 非法: {player_id!r}")
    # BattleTag 归一化后应为 Name-XXXX 形式；宽松校验：至少含 - 或纯字母数字
    if not _PLAYER_ID_RE.match(norm):
        raise ValueError(f"玩家 ID 含非法字符: {player_id!r}")
    return norm


def quote_player_id(player_id: str) -> str:
    """返回 URL-safe 的玩家 ID（已归一化+quote）。"""
    return quote(validate_player_id(player_id), safe="-")


def get_rank_display(division: str | None, tier: int | None) -> str:
    if not division:
        return "未定位"
    rank_info = RANK_MAPPING.get(division.lower(), (division, ""))
    tier_str = _TIER_ROMAN[tier] if tier and 1 <= tier <= 5 else ""
    name = rank_info[0]
    return f"{name}{' ' + tier_str if tier_str else ''}".strip()


def build_rank_data(summary: dict, platform: str) -> tuple[str, list[dict]]:
    comp = summary.get("competitive")
    if not isinstance(comp, dict):
        comp = summary.get("competitive_ranks")
    comp = comp if isinstance(comp, dict) else {}

    shown_platform = platform
    container = comp.get(platform)
    if not isinstance(container, dict) or not container:
        other_platform = "console" if platform == "pc" else "pc"
        other = comp.get(other_platform)
        if isinstance(other, dict) and other:
            shown_platform = other_platform
            container = other
        else:
            container = None

    rows: list[dict] = []
    if container:
        for role_key in ["tank", "damage", "support"]:
            role_cn = ROLE_MAPPING.get(role_key, (role_key, ""))[0]
            role_text = f"{role_cn}"
            role_data = container.get(role_key)
            if isinstance(role_data, dict) and role_data.get("division"):
                rows.append({
                    "role_text": role_text,
                    "rank_text": get_rank_display(role_data.get("division"), role_data.get("tier")),
                    "rank_icon": role_data.get("rank_icon") or "",
                })
            else:
                rows.append({"role_text": role_text, "rank_text": "未定位", "rank_icon": ""})
    return shown_platform, rows


def extract_top_heroes(stats: dict, platform: str, count: int = 3) -> list[tuple[str, int]]:
    if not isinstance(stats, dict):
        return []
    for plat in (platform, "console" if platform == "pc" else "pc"):
        plat_stats = stats.get(plat)
        if not isinstance(plat_stats, dict):
            continue
        totals: dict[str, int] = {}
        for gamemode in ("quickplay", "competitive"):
            gm_stats = plat_stats.get(gamemode)
            if not isinstance(gm_stats, dict):
                continue
            comparisons = gm_stats.get("heroes_comparisons")
            if not isinstance(comparisons, dict):
                continue
            time_played = comparisons.get("time_played")
            if not isinstance(time_played, dict):
                continue
            for item in time_played.get("values") or []:
                if not isinstance(item, dict):
                    continue
                hero = item.get("hero")
                value = item.get("value") or 0
                if hero:
                    try:
                        totals[hero] = totals.get(hero, 0) + int(value)
                    except (TypeError, ValueError):
                        continue
        if totals:
            return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:count]
    return []


def get_role_display(role_key: str) -> str:
    return ROLE_MAPPING.get(role_key.lower(), (role_key, ""))[0]


def get_hero_name_cn(hero_key: str) -> str:
    return HERO_NAME_MAPPING.get(hero_key.lower(), hero_key)


def resolve_hero_name(hero_input: str) -> str:
    hero_input = hero_input.strip()
    lowered = hero_input.lower()
    if lowered in HERO_NAME_MAPPING:
        return lowered
    if hero_input in HERO_NAME_REVERSE_MAPPING:
        return HERO_NAME_REVERSE_MAPPING[hero_input]
    for cn_name, en_key in HERO_NAME_REVERSE_MAPPING.items():
        if lowered in cn_name.lower() or cn_name.lower() in lowered:
            return en_key
    return lowered


def resolve_platform(platform_input: str) -> str | None:
    if not platform_input:
        return None
    return PLATFORM_REVERSE_MAPPING.get(platform_input.strip().lower())


def get_platform_display(platform: str) -> str:
    return PLATFORM_MAPPING.get(platform, platform)


def resolve_region(region_input: str) -> str | None:
    if not region_input:
        return None
    return REGION_REVERSE_MAPPING.get(region_input.strip().lower())


def get_region_display(region: str) -> str:
    return REGION_MAPPING.get(region, region)


def resolve_gamemode(mode_input: str) -> str | None:
    if not mode_input:
        return None
    return GAMEMODE_REVERSE_MAPPING.get(mode_input.strip().lower())


def format_time_played(seconds: int | float | None) -> str:
    if not seconds:
        return "0小时"
    total_minutes = int(seconds) // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0 and minutes > 0:
        return f"{hours}小时{minutes}分钟"
    elif hours > 0:
        return f"{hours}小时"
    return f"{minutes}分钟"


def format_time_short(seconds: int | float | None) -> str:
    if not seconds:
        return "0分钟"
    total_minutes = int(seconds) // 60
    hours = total_minutes / 60
    if hours >= 1:
        return f"{hours:.1f}小时"
    return f"{total_minutes}分钟"


def format_number(num: int | float | None) -> str:
    if num is None:
        return "0"
    if isinstance(num, float):
        return f"{num:,.1f}" if num != int(num) else f"{int(num):,}"
    return f"{num:,}"
