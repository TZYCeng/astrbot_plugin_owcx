"""
OW战绩查询插件
"""

import asyncio

import aiohttp

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.all import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .api_client import OverFastAPIClient

# 图片渲染依赖 Pillow，未安装时插件仍可正常使用（自动回退文字输出）
try:
    from . import image_renderer

    _RENDERER_AVAILABLE = True
except Exception as _render_import_err:  # pragma: no cover
    image_renderer = None  # type: ignore[assignment]
    _RENDERER_AVAILABLE = False

# ===== 常量定义 =====

# 段位中英文映射与图标
RANK_MAPPING = {
    "bronze": ("青铜", "🥉"),
    "silver": ("白银", "🥈"),
    "gold": ("黄金", "🥇"),
    "platinum": ("铂金", "🏅️"),
    "diamond": ("钻石", "💎"),
    "master": ("大师", "🎖"),
    "grandmaster": ("宗师", "🏆"),
    "champion": ("冠军", "👑"),
    "top500": ("五百强", "🌟"),
}

# 角色中英文映射与图标
ROLE_MAPPING = {
    "tank": ("坦克", "🛡️"),
    "damage": ("输出", "⚔️"),
    "support": ("支援", "💖"),
}

# 游戏模式英文→中文映射（用于输出显示）
GAMEMODE_MAPPING = {
    "quickplay": "快速游戏",
    "competitive": "竞技比赛",
}

# 游戏模式中文→英文映射（用于解析用户输入，支持多种中文说法）
GAMEMODE_REVERSE_MAPPING = {
    # 快速游戏
    "快速": "quickplay",
    "快速游戏": "quickplay",
    "qp": "quickplay",
    "quick": "quickplay",
    "quickplay": "quickplay",
    # 竞技比赛
    "竞技": "competitive",
    "竞技模式": "competitive",
    "竞技比赛": "competitive",
    "排位": "competitive",
    "排位赛": "competitive",
    "comp": "competitive",
    "competitive": "competitive",
}

# 竞技模式对应图标
COMPETITIVE_ICONS = {
    "tank": "🛡️",
    "damage": "⚔️",
    "support": "💖",
}

# 平台英文→中文显示映射
PLATFORM_MAPPING = {
    "pc": "💻 PC端",
    "console": "🎮 主机端",
}

# 平台用户输入→英文 key 映射（绑定时可选择 PC 端或主机端）
PLATFORM_REVERSE_MAPPING = {
    # PC 端
    "pc": "pc",
    "电脑": "pc",
    "电脑端": "pc",
    "端游": "pc",
    # 主机端
    "console": "console",
    "主机": "console",
    "主机端": "console",
    "ps": "console",
    "ps4": "console",
    "ps5": "console",
    "xbox": "console",
    "switch": "console",
    "ns": "console",
}

# 地区服务器英文→中文显示映射
REGION_MAPPING = {
    "asia": "亚服",
    "americas": "美服",
    "europe": "欧服",
}

# 地区服务器用户输入→英文 key 映射
REGION_REVERSE_MAPPING = {
    # 亚服
    "asia": "asia",
    "亚服": "asia",
    "亚洲": "asia",
    "亚太": "asia",
    # 美服
    "americas": "americas",
    "america": "americas",
    "美服": "americas",
    "美洲": "americas",
    # 欧服
    "europe": "europe",
    "eu": "europe",
    "欧服": "europe",
    "欧洲": "europe",
}

# 英雄英文名到中文名的映射（用于输出显示）
# 与 OverFast API HeroKey 枚举（52 名英雄）对齐，中文名为国服官方译名
HERO_NAME_MAPPING = {
    # 坦克
    "doomfist": "末日铁拳",
    "dva": "D.Va",
    "domina": "金驭",
    "hazard": "骇灾",
    "junker-queen": "渣客女王",
    "mauga": "毛加",
    "orisa": "奥丽莎",
    "ramattra": "拉玛刹",
    "reinhardt": "莱因哈特",
    "roadhog": "路霸",
    "sigma": "西格玛",
    "winston": "温斯顿",
    "wrecking-ball": "破坏球",
    "zarya": "查莉娅",
    # 输出
    "anran": "安燃",
    "ashe": "艾什",
    "bastion": "堡垒",
    "cassidy": "卡西迪",
    "echo": "回声",
    "emre": "埃姆雷",
    "freja": "弗蕾娅",
    "genji": "源氏",
    "hanzo": "半藏",
    "junkrat": "狂鼠",
    "mei": "美",
    "pharah": "法老之鹰",
    "reaper": "死神",
    "shion": "紫苑",
    "sierra": "西拉",
    "sojourn": "索杰恩",
    "soldier-76": "士兵:76",
    "sombra": "黑影",
    "symmetra": "秩序之光",
    "torbjorn": "托比昂",
    "tracer": "猎空",
    "vendetta": "斩仇",
    "venture": "探奇",
    "widowmaker": "黑百合",
    # 支援
    "ana": "安娜",
    "baptiste": "巴蒂斯特",
    "brigitte": "布丽吉塔",
    "illari": "伊拉锐",
    "jetpack-cat": "飞天猫",
    "juno": "朱诺",
    "kiriko": "雾子",
    "lifeweaver": "生命之梭",
    "lucio": "卢西奥",
    "mercy": "天使",
    "mizuki": "瑞稀",
    "moira": "莫伊拉",
    "wuyang": "无漾",
    "zenyatta": "禅雅塔",
}

# 英雄中文名到英文 key 的反向映射（用于解析用户输入）
HERO_NAME_REVERSE_MAPPING = {cn: en for en, cn in HERO_NAME_MAPPING.items()}


def _normalize_player_id(player_id: str) -> str:
    """规范化玩家 ID，将 # 替换为 -。

    Args:
        player_id: 原始玩家 ID。

    Returns:
        规范化后的玩家 ID。
    """
    return player_id.replace("#", "-").strip()


def _get_rank_display(division: str | None, tier: int | None) -> str:
    """获取段位显示文本。

    Args:
        division: 段位英文 key。
        tier:  tier 等级（1-5）。

    Returns:
        格式化的段位文本，如 "💎 钻石 III"。
    """
    if not division:
        return "未定位"
    rank_info = RANK_MAPPING.get(division.lower(), (division, ""))
    tier_roman = ["", "I", "II", "III", "IV", "V"]
    tier_str = tier_roman[tier] if tier and 1 <= tier <= 5 else ""
    return f"{rank_info[1]} {rank_info[0]}{' ' + tier_str if tier_str else ''}"


def _build_rank_data(summary: dict, platform: str) -> tuple[str, list[dict]]:
    """从玩家摘要中构建竞技段位数据（坦克/输出/支援三职责）。

    API 摘要的段位结构为 competitive → pc/console → tank/damage/support，
    每项包含 division、tier、rank_icon 等字段。

    Args:
        summary: 玩家摘要字典。
        platform: 期望平台（pc/console）。

    Returns:
        (实际显示平台, 段位行列表) 元组；段位行包含
        role_text（角色显示文本）、rank_text（段位显示文本）、rank_icon（段位图标 URL）。
        期望平台无数据时自动回退到另一平台。
    """
    comp = summary.get("competitive")
    if not isinstance(comp, dict):
        # 兼容旧字段名
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
            role_text = COMPETITIVE_ICONS.get(role_key, "") + " " + ROLE_MAPPING.get(role_key, (role_key, ""))[0]
            role_data = container.get(role_key)
            if isinstance(role_data, dict) and role_data.get("division"):
                rows.append({
                    "role_text": role_text,
                    "rank_text": _get_rank_display(role_data.get("division"), role_data.get("tier")),
                    "rank_icon": role_data.get("rank_icon") or "",
                })
            else:
                rows.append({"role_text": role_text, "rank_text": "未定位", "rank_icon": ""})
    return shown_platform, rows


def _extract_top_heroes(stats: dict, platform: str, count: int = 3) -> list[tuple[str, int]]:
    """从玩家统计数据中提取常玩英雄（按游戏时长排序）。

    汇总该平台快速与竞技模式下 heroes_comparisons.time_played 的时长；
    期望平台无数据时自动回退到另一平台。

    Args:
        stats: 玩家 stats 字典（pc/console → quickplay/competitive）。
        platform: 期望平台（pc/console）。
        count: 返回的英雄数量，默认 3。

    Returns:
        [(英雄 key, 总时长秒数), ...]，按时长降序。
    """
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
                    totals[hero] = totals.get(hero, 0) + int(value)
        if totals:
            return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:count]
    return []


def _get_role_display(role_key: str) -> str:
    """获取角色显示文本。

    Args:
        role_key: 角色英文 key。

    Returns:
        格式化的角色文本，如 "🛡️ 坦克"。
    """
    role_info = ROLE_MAPPING.get(role_key.lower(), (role_key, ""))
    return f"{role_info[1]} {role_info[0]}"


def _get_hero_name_cn(hero_key: str) -> str:
    """获取英雄中文名（用于输出显示）。

    Args:
        hero_key: 英雄英文 key。

    Returns:
        中文名或原始的 key。
    """
    return HERO_NAME_MAPPING.get(hero_key.lower(), hero_key)


def _resolve_hero_name(hero_input: str) -> str:
    """解析用户输入的英雄名称，支持中英文。

    用户可输入中文名（如"源氏"）、英文名（如"genji"）或部分匹配。
    返回对应的英文 hero_key。

    Args:
        hero_input: 用户输入的英雄名称。

    Returns:
        英雄英文 key（小写）。
    """
    hero_input = hero_input.strip()

    # 1. 直接匹配英文 key（不区分大小写）
    lowered = hero_input.lower()
    if lowered in HERO_NAME_MAPPING:
        return lowered

    # 2. 匹配中文名
    if hero_input in HERO_NAME_REVERSE_MAPPING:
        return HERO_NAME_REVERSE_MAPPING[hero_input]

    # 3. 尝试部分匹配中文名
    for cn_name, en_key in HERO_NAME_REVERSE_MAPPING.items():
        if lowered in cn_name.lower() or cn_name.lower() in lowered:
            return en_key

    # 4. 原样返回，让 API 去尝试
    return lowered


def _resolve_platform(platform_input: str) -> str | None:
    """解析用户输入的平台，支持中英文。

    Args:
        platform_input: 用户输入的平台（如 pc、电脑、console、主机）。

    Returns:
        标准化后的英文平台（pc/console），无法解析则返回 None。
    """
    if not platform_input:
        return None
    return PLATFORM_REVERSE_MAPPING.get(platform_input.strip().lower())


def _get_platform_display(platform: str) -> str:
    """获取平台显示文本。

    Args:
        platform: 平台英文 key。

    Returns:
        格式化的平台文本，如 "💻 PC端"。
    """
    return PLATFORM_MAPPING.get(platform, platform)


def _resolve_region(region_input: str) -> str | None:
    """解析用户输入的地区服务器，支持中英文。

    Args:
        region_input: 用户输入的地区（如 asia、亚服、americas、美服、europe、欧服）。

    Returns:
        标准化后的英文地区（asia/americas/europe），无法解析则返回 None。
    """
    if not region_input:
        return None
    return REGION_REVERSE_MAPPING.get(region_input.strip().lower())


def _get_region_display(region: str) -> str:
    """获取地区服务器显示文本。

    Args:
        region: 地区英文 key。

    Returns:
        中文地区文本，如 "亚服"。
    """
    return REGION_MAPPING.get(region, region)


def _resolve_gamemode(mode_input: str) -> str | None:
    """解析用户输入的游戏模式，支持中英文。

    Args:
        mode_input: 用户输入的游戏模式。

    Returns:
        标准化后的英文游戏模式（quickplay/competitive），
        如果无法解析则返回 None。
    """
    if not mode_input:
        return None
    return GAMEMODE_REVERSE_MAPPING.get(mode_input.strip().lower())


def _format_time_played(seconds: int | float | None) -> str:
    """格式化游戏时间。

    Args:
        seconds: 游戏时间（秒）。

    Returns:
        格式化的时间文本，如 "123小时30分钟"。
    """
    if not seconds:
        return "0小时"
    total_minutes = int(seconds) // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0 and minutes > 0:
        return f"{hours}小时{minutes}分钟"
    elif hours > 0:
        return f"{hours}小时"
    else:
        return f"{minutes}分钟"


def _format_time_short(seconds: int | float | None) -> str:
    """格式化游戏时间为紧凑形式（用于图片渲染中的狭窄空间）。

    Args:
        seconds: 游戏时间（秒）。

    Returns:
        紧凑时间文本，如 "46.5小时"、"30分钟"。
    """
    if not seconds:
        return "0分钟"
    total_minutes = int(seconds) // 60
    hours = total_minutes / 60
    if hours >= 1:
        return f"{hours:.1f}小时"
    return f"{total_minutes}分钟"


def _format_number(num: int | float | None) -> str:
    """格式化数字，添加千分位分隔符。

    Args:
        num: 数字。

    Returns:
        格式化后的字符串，如 "12,345"。
    """
    if num is None:
        return "0"
    if isinstance(num, float):
        return f"{num:,.1f}" if num != int(num) else f"{int(num):,}"
    return f"{num:,}"


class OverwatchStatsPlugin(Star):
    """OW战绩查询插件主类。

    基于 OverFast API 提供 Overwatch 2 玩家战绩查询功能。

    指令列表:
        /owsummary [玩家ID]      - 查询玩家摘要（头像、段位等）
        /owstats [玩家ID] [模式]  - 查询玩家统计概览
        /owcareer [玩家ID] <模式> [英雄] - 查询生涯统计
        /owhero <英雄名>         - 查询英雄信息
        /owherostats [角色] [地区] - 全服英雄胜率/选取率排行（按地区）
        /owbind <玩家ID> [平台]  - 绑定账号（平台: pc/console，可多绑）
        /owunbind [玩家ID]       - 解绑账号（不填则解绑默认账号）
        /owbinds                 - 查看绑定的账号列表
        /owdefault <玩家ID>      - 设置默认查询账号
        /owme                    - 快捷查询默认账号的摘要
    """

    # ===== KV 存储键前缀 =====
    _BIND_KEY_PREFIX = "bind_"

    def _get_bind_key(self, qq_id: str) -> str:
        """生成绑定存储的 KV key。

        Args:
            qq_id: QQ 号（发送者 ID）。

        Returns:
            KV 存储 key。
        """
        return f"{self._BIND_KEY_PREFIX}{qq_id}"

    async def _load_bindings(self, event: AstrMessageEvent) -> dict:
        """加载用户的绑定数据，并自动迁移旧版结构。

        新版结构: {"accounts": [{"player_id": ..., "platform": ...}], "default": 玩家ID}
        兼容以下旧版结构（读取后自动迁移保存）:
          - 纯字符串: "玩家ID"（最早版本）
          - 单账号字典: {"player_id": ..., "platform": ...}

        Args:
            event: 消息事件对象。

        Returns:
            绑定数据字典，无绑定时返回 {"accounts": [], "default": None}。
        """
        empty: dict = {"accounts": [], "default": None}
        qq_id = event.get_sender_id()
        if not qq_id:
            return empty
        try:
            raw = await self.get_kv_data(self._get_bind_key(qq_id), None)
        except Exception as e:
            logger.debug(f"读取绑定信息失败: {e}")
            return empty

        migrated: dict | None = None
        if isinstance(raw, dict) and "accounts" in raw:
            accounts = []
            for item in raw.get("accounts") or []:
                if not isinstance(item, dict):
                    continue
                pid = item.get("player_id")
                platform = item.get("platform")
                if platform not in ("pc", "console"):
                    platform = self.default_platform
                if pid:
                    accounts.append({"player_id": pid, "platform": platform})
            default = raw.get("default")
            if not any(a["player_id"] == default for a in accounts):
                default = accounts[0]["player_id"] if accounts else None
            return {"accounts": accounts, "default": default}
        elif isinstance(raw, dict) and raw.get("player_id"):
            # 旧版单账号字典
            platform = raw.get("platform")
            if platform not in ("pc", "console"):
                platform = self.default_platform
            migrated = {
                "accounts": [{"player_id": raw["player_id"], "platform": platform}],
                "default": raw["player_id"],
            }
        elif isinstance(raw, str) and raw:
            # 最早版本：仅有玩家 ID 字符串
            migrated = {
                "accounts": [{"player_id": raw, "platform": self.default_platform}],
                "default": raw,
            }

        if migrated:
            try:
                await self.put_kv_data(self._get_bind_key(qq_id), migrated)
            except Exception as e:
                logger.debug(f"迁移绑定数据失败: {e}")
            return migrated
        return empty

    async def _save_bindings(self, event: AstrMessageEvent, data: dict) -> bool:
        """保存用户绑定数据。"""
        qq_id = event.get_sender_id()
        if not qq_id:
            return False
        try:
            await self.put_kv_data(self._get_bind_key(qq_id), data)
            return True
        except Exception as e:
            logger.error(f"保存绑定信息失败: {e}")
            return False

    async def _get_binding(self, event: AstrMessageEvent) -> tuple[str | None, str | None]:
        """获取用户默认绑定账号的 ID 与平台（查询时使用）。

        Args:
            event: 消息事件对象。

        Returns:
            (玩家 ID, 平台) 元组；未绑定时两者均为 None。
        """
        data = await self._load_bindings(event)
        accounts = data.get("accounts", [])
        if not accounts:
            return None, None
        default = data.get("default")
        for acc in accounts:
            if acc.get("player_id") == default:
                return acc["player_id"], acc.get("platform")
        first = accounts[0]
        return first.get("player_id"), first.get("platform")

    async def _get_bound_id(self, event: AstrMessageEvent) -> str | None:
        """获取用户绑定的 Overwatch ID。

        Args:
            event: 消息事件对象。

        Returns:
            绑定的玩家 ID，未绑定则返回 None。
        """
        player_id, _ = await self._get_binding(event)
        return player_id

    async def _add_binding(
        self, event: AstrMessageEvent, player_id: str, platform: str = "pc"
    ) -> tuple[str, dict | None]:
        """添加一个绑定账号。

        同 ID 重复绑定时更新其平台并设为默认；
        达到绑定数量上限时不做改动。

        Args:
            event: 消息事件对象。
            player_id: 要绑定的玩家 ID。
            platform: 要绑定的平台（pc/console）。

        Returns:
            (结果码, 绑定数据) 元组。结果码:
            "added" 新增成功, "updated" 更新成功, "limit" 已达上限, "error" 保存失败。
        """
        if platform not in ("pc", "console"):
            platform = self.default_platform
        data = await self._load_bindings(event)
        accounts = data["accounts"]

        for acc in accounts:
            if acc["player_id"].lower() == player_id.lower():
                acc["player_id"] = player_id
                acc["platform"] = platform
                data["default"] = player_id
                if await self._save_bindings(event, data):
                    return "updated", data
                return "error", None

        max_binds = max(int(getattr(self, "max_binds_per_user", 3) or 3), 1)
        if len(accounts) >= max_binds:
            return "limit", None

        accounts.append({"player_id": player_id, "platform": platform})
        data["default"] = player_id
        if await self._save_bindings(event, data):
            return "added", data
        return "error", None

    async def _remove_binding(
        self, event: AstrMessageEvent, player_id: str | None = None
    ) -> tuple[str, str | None]:
        """移除绑定账号。

        Args:
            event: 消息事件对象。
            player_id: 要解绑的玩家 ID；为 None 时解绑当前默认账号。

        Returns:
            (结果码, 被解绑的玩家ID) 元组。结果码:
            "removed" 解绑成功, "empty" 无绑定, "not_found" 未找到该账号, "error" 保存失败。
        """
        data = await self._load_bindings(event)
        accounts = data["accounts"]
        if not accounts:
            return "empty", None

        target = player_id or data.get("default") or accounts[0]["player_id"]
        idx = next(
            (i for i, a in enumerate(accounts) if a["player_id"].lower() == target.lower()),
            None,
        )
        if idx is None:
            return "not_found", None

        removed = accounts.pop(idx)
        if not accounts:
            try:
                await self.delete_kv_data(self._get_bind_key(event.get_sender_id()))
            except Exception as e:
                logger.error(f"删除绑定信息失败: {e}")
                return "error", None
            return "removed", removed["player_id"]

        if data.get("default") == removed["player_id"]:
            data["default"] = accounts[0]["player_id"]
        if await self._save_bindings(event, data):
            return "removed", removed["player_id"]
        return "error", None

    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        """初始化插件。

        Args:
            context: AstrBot 上下文对象。
            config: 插件配置对象。
        """
        super().__init__(context)
        self.config = config or {}
        # 配置中的游戏模式可能是中文，需要解析为英文
        raw_gamemode = self.config.get("default_gamemode", "competitive")
        resolved = _resolve_gamemode(raw_gamemode)
        self.default_gamemode: str = resolved if resolved in ("quickplay", "competitive") else "competitive"
        # 配置中的平台可能是中文（pc/console/电脑/主机），需要解析为英文
        raw_platform = self.config.get("default_platform", "pc")
        resolved_platform = _resolve_platform(str(raw_platform))
        self.default_platform: str = resolved_platform if resolved_platform in ("pc", "console") else "pc"
        # 配置中的地区服务器可能是中文（asia/americas/europe/亚服/美服/欧服），需要解析为英文
        raw_region = self.config.get("default_region", "asia")
        resolved_region = _resolve_region(str(raw_region))
        self.default_region: str = resolved_region if resolved_region in ("asia", "americas", "europe") else "asia"
        # 图片渲染开关：开启后查询结果渲染为卡片图片，失败时自动回退为文字
        self.enable_image_render: bool = bool(self.config.get("enable_image_render", False))
        # 报错展示开关：开启后查询出错时把 API 具体报错回复给查询者
        self.show_api_error: bool = bool(self.config.get("show_api_error", False))
        # 每个 QQ 号可绑定的 Overwatch 账号数量上限
        try:
            self.max_binds_per_user: int = max(int(self.config.get("max_binds_per_user", 3) or 3), 1)
        except (TypeError, ValueError):
            self.max_binds_per_user = 3
        if self.enable_image_render and not _RENDERER_AVAILABLE:
            logger.warning(
                "已开启图片渲染，但渲染模块加载失败（可能未安装 Pillow），"
                "查询结果将回退为文字输出。请执行: pip install Pillow"
            )
        logger.info(f"OW战绩查询插件已加载（图片渲染: {'开启' if self.enable_image_render else '关闭'}）")

    def _effective_platform(self, bound_platform: str | None = None) -> str:
        """获取查询实际使用的平台。

        已绑定平台的用户使用其绑定平台；未绑定平台（含旧版绑定）时
        回退到配置文件中的默认平台。

        Args:
            bound_platform: 用户绑定的平台，可为 None。

        Returns:
            实际查询平台（pc/console）。
        """
        if bound_platform in ("pc", "console"):
            return bound_platform
        return self.default_platform

    def _api_error_reply(self, e: Exception, friendly: str) -> str:
        """生成 API 错误的用户回复文本。

        无论开关状态如何，完整报错都会写入控制台 debug 日志；
        show_api_error 开启时，回复中附带 API 返回的具体报错。

        Args:
            e: 捕获到的异常。
            friendly: 开关关闭时展示的友好提示。

        Returns:
            回复给查询者的文本。
        """
        logger.debug(f"API 错误详情: {type(e).__name__}: {e}", exc_info=True)
        if self.show_api_error:
            detail = getattr(e, "detail", "") or str(e)
            retry_after = getattr(e, "retry_after", None)
            reply = f"❌ 查询出错: {detail}"
            if retry_after:
                reply += f"\n⏱️ 建议等待 {retry_after} 秒后重试"
            return reply
        return friendly

    @staticmethod
    async def _download_image(url: str) -> bytes | None:
        """下载图片二进制数据（用于渲染头像），失败时返回 None。

        Args:
            url: 图片 URL。

        Returns:
            图片二进制数据或 None。
        """
        if not url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.debug(f"下载图片失败: {e}")
        return None

    async def _fetch_hero_portraits(self, hero_keys: list[str]) -> dict[str, bytes]:
        """获取英雄头像（肖像）图片数据。

        头像 URL 取自 OverFast API /heroes 返回的官方战网 CDN 肖像
        （与 wiki 使用的英雄头像同源）。获取失败时返回空字典，
        不影响后续渲染。

        Args:
            hero_keys: 需要头像的英雄 key 列表。

        Returns:
            {英雄 key: 头像二进制数据} 字典。
        """
        if not hero_keys:
            return {}
        portrait_map: dict[str, str] = {}
        try:
            async with OverFastAPIClient() as client:
                heroes_list = await client.list_heroes()
            for h in heroes_list or []:
                if isinstance(h, dict) and h.get("key") and h.get("portrait"):
                    portrait_map[h["key"]] = h["portrait"]
        except Exception as e:
            logger.debug(f"获取英雄头像列表失败: {e}")
            return {}

        urls = {k: portrait_map.get(k, "") for k in hero_keys}
        results = await asyncio.gather(*(self._download_image(u) for u in urls.values()))
        return {k: b for k, b in zip(urls.keys(), results) if b}

    async def _send_summary_result(
        self,
        event: AstrMessageEvent,
        full: dict,
        player_id: str,
        platform: str,
        footer_note: str | None = None,
        extra_lines: list[str] | None = None,
    ):
        """根据玩家完整数据生成摘要回复（图片渲染或文字）。

        图片模式：名片横幅 + 头像按游戏内效果组合渲染，段位区展示
        坦克/输出/支援三职责（含段位图标），下方附常玩英雄 TOP3（含英雄头像）。
        文字模式：不展示名片，段位与常玩英雄以文字呈现。

        Args:
            event: 消息事件对象。
            full: /players/{id} 返回的完整数据（含 summary 和 stats）。
            player_id: 玩家 ID（用于兜底显示）。
            platform: 查询平台。
            footer_note: 图片底部备注（可选）。
            extra_lines: 文字模式追加的额外行（可选）。
        """
        summary = full.get("summary") if isinstance(full.get("summary"), dict) else full
        stats = full.get("stats") if isinstance(full.get("stats"), dict) else {}

        username = summary.get("username", player_id)
        avatar_url = summary.get("avatar") or ""
        namecard_url = summary.get("namecard") or ""
        endorsement = summary.get("endorsement", {})
        endorsement_level = endorsement.get("level", 0) if isinstance(endorsement, dict) else 0
        title = summary.get("title") or ""

        shown_platform, rank_rows = _build_rank_data(summary, platform)
        top_heroes = _extract_top_heroes(stats, platform)

        # ===== 图片渲染模式（开启时优先，失败自动回退文字）=====
        if self.enable_image_render and _RENDERER_AVAILABLE:
            try:
                # 并发下载头像、名片、各职责段位图标
                download_tasks = [
                    self._download_image(avatar_url),
                    self._download_image(namecard_url),
                ] + [self._download_image(row.get("rank_icon", "")) for row in rank_rows]
                results = await asyncio.gather(*download_tasks)
                avatar_bytes, namecard_bytes = results[0], results[1]

                render_rows = []
                for row, icon_bytes in zip(rank_rows, results[2:]):
                    render_rows.append({
                        "role_text": row["role_text"],
                        "rank_text": row["rank_text"],
                        "rank_icon_bytes": icon_bytes,
                    })
                if not render_rows:
                    render_rows = [{"role_text": "段位", "rank_text": "暂无竞技段位数据", "rank_icon_bytes": None}]

                # 常玩英雄头像（时长使用紧凑格式适配卡片空间）
                portraits = await self._fetch_hero_portraits([k for k, _ in top_heroes])
                render_heroes = [
                    (_get_hero_name_cn(k), _format_time_short(v), portraits.get(k))
                    for k, v in top_heroes
                ]

                img_path = image_renderer.render_summary_card(
                    username=username,
                    title=title,
                    endorsement_level=endorsement_level,
                    rank_rows=render_rows,
                    platform_label=_get_platform_display(shown_platform),
                    avatar_bytes=avatar_bytes,
                    namecard_bytes=namecard_bytes,
                    top_heroes=render_heroes,
                    footer_note=footer_note,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"摘要图片渲染失败，回退为文字输出: {e}")
                logger.debug("摘要图片渲染错误堆栈:", exc_info=True)

        # ===== 文字输出（不展示名片）=====
        rank_lines = (
            [f"   {r['role_text']}: {r['rank_text']}" for r in rank_rows]
            if rank_rows else ["   暂无竞技段位数据"]
        )
        lines = [f"👤 {username}"]
        if title:
            lines.append(f"🏷️ 头衔: {title}")
        lines.append(f"⭐ 赞赏等级: {endorsement_level}")
        lines.append(f"🏆 竞技段位 ({_get_platform_display(shown_platform)}):")
        lines.extend(rank_lines)
        if top_heroes:
            heroes_text = "、".join(
                f"{_get_hero_name_cn(k)}({_format_time_played(v)})" for k, v in top_heroes
            )
            lines.append(f"🎮 常玩英雄: {heroes_text}")
        if extra_lines:
            lines.extend(extra_lines)

        result_text = "\n".join(lines)
        if avatar_url:
            chain = [
                Comp.Image.fromURL(avatar_url),
                Comp.Plain(result_text),
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result(result_text)

    @filter.command("owsummary")
    async def player_summary(self, event: AstrMessageEvent, player_id: str = ""):
        """查询玩家摘要信息（头像、竞技段位等）。

        用法: /owsummary [玩家ID]
        示例: /owsummary TeKrop#2217
        说明: 支持直接使用 #，会自动替换；省略 ID 则查询绑定的账号（使用绑定平台）
        """
        # 未传入 ID，尝试获取绑定的 ID 与平台
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owsummary <玩家ID>\n"
                    "示例: /owsummary TeKrop#2217（支持直接输入 #）\n"
                    "💡 或使用 /owbind <玩家ID> [平台] 绑定你的账号，之后可直接用 /owsummary 查询"
                )
                return
            player_id = bound_id
            from_binding = True

        platform = self._effective_platform(bound_platform)
        # 绑定存储中的 ID 已是规范化形式（- 分隔），直接使用；
        # 外部指令输入的 ID 自动将 # 替换为 -
        if not from_binding:
            player_id = _normalize_player_id(player_id)

        try:
            async with OverFastAPIClient() as client:
                full = await client.get_player_full(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "未找到" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}`。\n"
                    f"💡 请检查玩家 ID 是否正确（支持直接输入 #，会自动处理）。"
                )
                return
            logger.warning(f"获取玩家摘要失败: {e}")
            yield event.plain_result(self._api_error_reply(e, "❌ 获取玩家信息失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取玩家摘要时发生错误: {e}")
            logger.debug("获取玩家摘要错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取玩家信息时出错，请稍后重试。")
            return

        async for res in self._send_summary_result(event, full, player_id, platform):
            yield res

    @filter.command("owstats")
    async def player_stats(
        self,
        event: AstrMessageEvent,
        player_id: str = "",
        gamemode: str = "",
    ):
        """查询玩家统计概览（胜率、KDA等）。

        用法: /owstats [玩家ID] [游戏模式]
        游戏模式: 快速、竞技（默认）
        示例: /owstats TeKrop#2217 竞技
        说明: 省略 ID 则查询绑定的账号（使用绑定平台）
        """
        # 未传入 ID，尝试获取绑定的 ID 与平台
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owstats <玩家ID> [游戏模式]\n"
                    "示例: /owstats TeKrop#2217 竞技（支持直接输入 #）\n"
                    "游戏模式: 快速(quickplay)、竞技(competitive，默认)\n"
                    "💡 或使用 /owbind <玩家ID> [平台] 绑定你的账号，之后可直接用 /owstats 查询"
                )
                return
            player_id = bound_id
            from_binding = True

        platform = self._effective_platform(bound_platform)
        # 绑定存储中的 ID 直接使用；外部输入自动将 # 替换为 -
        if not from_binding:
            player_id = _normalize_player_id(player_id)
        gamemode = _resolve_gamemode(gamemode or self.default_gamemode)

        if gamemode not in ("quickplay", "competitive"):
            yield event.plain_result(
                "❌ 游戏模式无效。可选: 快速(quickplay)、竞技(competitive)\n"
                "用法: /owstats <玩家ID> [快速|竞技]"
            )
            return

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_stats_summary(
                    player_id, gamemode=gamemode, platform=platform
                )
                # 竞技模式额外获取段位数据（三职责晋级段位）
                # 所有模式额外获取常玩英雄数据（从英雄统计中按场次取前三）
                full: dict = {}
                try:
                    full = await client.get_player_full(player_id)
                except Exception as fe:
                    logger.debug(f"获取玩家完整数据失败（段位/常玩英雄将不展示）: {fe}")
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}` 或其资料为私密状态。\n"
                    f"💡 请将 Overwatch 资料设为公开后重试。"
                )
                return
            yield event.plain_result(self._api_error_reply(e, "❌ 获取统计失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取玩家统计时发生错误: {e}")
            logger.debug("获取玩家统计错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取统计信息时出错，请稍后重试。")
            return

        general = data.get("general", {}) if isinstance(data, dict) else {}
        if not general:
            yield event.plain_result(
                f"📊 玩家 `{player_id}` | {GAMEMODE_MAPPING.get(gamemode, gamemode)} | {_get_platform_display(platform)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"暂无统计数据。"
            )
            return

        # 场均数据位于 general.average，总量位于 general.total（按 API 规范）
        average = general.get("average", {}) if isinstance(general.get("average"), dict) else {}
        games_played = general.get("games_played", 0) or 0
        games_won = general.get("games_won", 0) or 0
        games_lost = general.get("games_lost", 0) or 0
        winrate = general.get("winrate", 0) or 0
        kda = general.get("kda", 0) or 0
        eliminations_avg = average.get("eliminations", 0) or 0
        deaths_avg = average.get("deaths", 0) or 0
        damage_avg = average.get("damage", 0) or 0
        healing_avg = average.get("healing", 0) or 0
        time_played = general.get("time_played", 0) or 0

        # 段位与常玩英雄（来自完整数据，获取失败时为空则跳过展示）
        summary = full.get("summary") if isinstance(full.get("summary"), dict) else {}
        stats_full = full.get("stats") if isinstance(full.get("stats"), dict) else {}
        shown_platform, rank_data = _build_rank_data(summary, platform) if summary else (platform, [])
        comp_rank_rows = rank_data if gamemode == "competitive" else []

        # 常玩英雄：按当前模式的英雄统计 games_played 取前三
        heroes_stats = data.get("heroes", {}) if isinstance(data.get("heroes"), dict) else {}
        top_hero_rows = sorted(
            (
                (k, int(v.get("games_played") or 0))
                for k, v in heroes_stats.items()
                if isinstance(v, dict) and (v.get("games_played") or 0) > 0
            ),
            key=lambda kv: kv[1],
            reverse=True,
        )[:3]
        # 回退：当前模式无英雄数据时，从完整数据的时长对比中取
        if not top_hero_rows and stats_full:
            top_hero_rows = [
                (k, 0) for k, _ in _extract_top_heroes(stats_full, platform)
            ]

        gamemode_label = GAMEMODE_MAPPING.get(gamemode, gamemode)

        # ===== 图片渲染模式（开启时优先，失败自动回退文字）=====
        if self.enable_image_render and _RENDERER_AVAILABLE:
            try:
                # 段位图标（竞技模式）
                render_rank_rows = []
                if comp_rank_rows:
                    icon_results = await asyncio.gather(
                        *(self._download_image(r.get("rank_icon", "")) for r in comp_rank_rows)
                    )
                    for r, icon_bytes in zip(comp_rank_rows, icon_results):
                        render_rank_rows.append({
                            "role_text": r["role_text"],
                            "rank_text": r["rank_text"],
                            "rank_icon_bytes": icon_bytes,
                        })

                # 常玩英雄头像与场次
                portraits = await self._fetch_hero_portraits([k for k, _ in top_hero_rows])
                games_map = {k: v for k, v in top_hero_rows}
                render_heroes = []
                for k, g in top_hero_rows:
                    info = f"{_format_number(g)}场" if g else "常用英雄"
                    render_heroes.append((_get_hero_name_cn(k), info, portraits.get(k)))

                stat_rows: list[tuple[str, str]] = [
                    ("🎮 场次", f"{_format_number(games_played)} ({_format_number(games_won)}胜/{_format_number(games_lost)}负)"),
                    ("📈 胜率", f"{winrate}%"),
                    ("⚔️ KDA", f"{kda:.2f}" if kda else "N/A"),
                    ("💥 消灭", f"{_format_number(eliminations_avg)}/场" if eliminations_avg else "N/A"),
                    ("💀 死亡", f"{_format_number(deaths_avg)}/场" if deaths_avg else "N/A"),
                    ("🔥 伤害", f"{_format_number(damage_avg)}/场" if damage_avg else "N/A"),
                    ("💚 治疗", f"{_format_number(healing_avg)}/场" if healing_avg else "N/A"),
                    ("⏱ 游戏时间", _format_time_played(time_played)),
                ]
                img_path = image_renderer.render_stats_card(
                    player_id=player_id,
                    gamemode_label=gamemode_label,
                    platform_label=_get_platform_display(shown_platform),
                    stat_rows=stat_rows,
                    rank_rows=render_rank_rows,
                    top_heroes=render_heroes,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"统计图片渲染失败，回退为文字输出: {e}")
                logger.debug("统计图片渲染错误堆栈:", exc_info=True)

        # ===== 文字输出 =====
        lines = [
            f"📊 {player_id} | {gamemode_label} | {_get_platform_display(shown_platform)}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        if comp_rank_rows:
            lines.append(f"🏆 竞技段位 ({_get_platform_display(shown_platform)}):")
            for r in comp_rank_rows:
                lines.append(f"   {r['role_text']}: {r['rank_text']}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.extend([
            f"🎮 场次: {_format_number(games_played)} ({_format_number(games_won)}胜/{_format_number(games_lost)}负)",
            f"📈 胜率: {winrate}%",
            f"⚔️ KDA: {kda:.2f}" if kda else "⚔️ KDA: N/A",
            f"💥 消灭: {_format_number(eliminations_avg)}/场" if eliminations_avg else "💥 消灭: N/A",
            f"💀 死亡: {_format_number(deaths_avg)}/场" if deaths_avg else "💀 死亡: N/A",
            f"🔥 伤害: {_format_number(damage_avg)}/场" if damage_avg else "🔥 伤害: N/A",
            f"💚 治疗: {_format_number(healing_avg)}/场" if healing_avg else "💚 治疗: N/A",
            f"⏱️ 游戏时间: {_format_time_played(time_played)}",
        ])
        if top_hero_rows:
            heroes_text = "、".join(
                f"{_get_hero_name_cn(k)}({_format_number(g)}场)" if g else _get_hero_name_cn(k)
                for k, g in top_hero_rows
            )
            lines.append(f"🎮 常玩英雄: {heroes_text}")

        yield event.plain_result("\n".join(lines))

    @filter.command("owcareer")
    async def player_career(
        self,
        event: AstrMessageEvent,
        player_id: str = "",
        gamemode: str = "",
        hero: str = "",
    ):
        """查询玩家生涯统计（按英雄详细数据）。

        用法: /owcareer [玩家ID] <游戏模式> [英雄名]
        游戏模式: 快速、竞技
        英雄名: 可选，支持中文（如 源氏、安娜）或英文（如 genji, ana）
        示例:
            /owcareer TeKrop#2217 竞技
            /owcareer TeKrop#2217 竞技 源氏
            /owcareer 竞技 源氏        (已绑定ID后)
        """
        # 未传入 ID，尝试获取绑定的 ID 与平台
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                    "示例: /owcareer TeKrop#2217 竞技 源氏（支持直接输入 #）\n"
                    "💡 或使用 /owbind <玩家ID> [平台] 绑定你的账号，之后可直接用 /owcareer 竞技 源氏 查询"
                )
                return
            player_id = bound_id
            from_binding = True
        # player_id 传入但 gamemode 为空，说明只传了 gamemode（已绑定 ID 的快捷用法）
        elif not gamemode or not gamemode.strip():
            # 尝试将 player_id 当作 gamemode 解析
            resolved = _resolve_gamemode(player_id)
            if resolved in ("quickplay", "competitive"):
                bound_id, bound_platform = await self._get_binding(event)
                if bound_id:
                    gamemode = player_id
                    player_id = bound_id
                    from_binding = True
                else:
                    yield event.plain_result(
                        "❌ 你还没有绑定 Overwatch ID。\n"
                        "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                        "💡 使用 /owbind <玩家ID> [平台] 绑定后可直接 /owcareer 竞技 源氏"
                    )
                    return

        platform = self._effective_platform(bound_platform)

        resolved_mode = _resolve_gamemode(gamemode)
        if not resolved_mode or resolved_mode not in ("quickplay", "competitive"):
            yield event.plain_result(
                "❌ 请输入有效的游戏模式。\n"
                "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                "游戏模式: 快速(quickplay)、竞技(competitive)"
            )
            return

        # 绑定存储中的 ID 直接使用；外部输入自动将 # 替换为 -
        if not from_binding:
            player_id = _normalize_player_id(player_id)
        gamemode = resolved_mode
        hero_key = _resolve_hero_name(hero) if hero else None

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_career_stats(
                    player_id,
                    gamemode=gamemode,
                    platform=platform,
                    hero=hero_key,
                )
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}` 或其资料为私密状态。\n"
                    f"💡 请将 Overwatch 资料设为公开后重试。"
                )
                return
            yield event.plain_result(self._api_error_reply(e, "❌ 获取生涯统计失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取生涯统计时发生错误: {e}")
            logger.debug("获取生涯统计错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取生涯统计时出错，请稍后重试。")
            return

        if not data or not isinstance(data, dict):
            yield event.plain_result(
                f"📈 玩家 `{player_id}` | {GAMEMODE_MAPPING.get(gamemode, gamemode)} | {_get_platform_display(platform)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"暂无生涯统计数据。"
            )
            return

        # 整理为结构化数据（同时供图片渲染与文本输出使用）
        hero_cards: list[tuple[str, str, list[tuple[str, str]]]] = []
        remaining = 0
        for hero_key_raw, categories in data.items():
            if not isinstance(categories, dict):
                continue

            hero_name = _get_hero_name_cn(hero_key_raw)
            rows: list[tuple[str, str]] = []

            # 显示 combat 和 game 类别的关键数据
            combat = categories.get("combat", {})
            if combat:
                eliminations = combat.get("eliminations")
                deaths = combat.get("deaths")
                kd = ""
                if eliminations and deaths and int(deaths) > 0:
                    kd_ratio = float(eliminations) / float(deaths)
                    kd = f" (K/D: {kd_ratio:.2f})"
                elif eliminations:
                    kd = f" (K/D: ∞)"

                if eliminations is not None:
                    rows.append(("💥 消灭", f"{_format_number(eliminations)}{kd}"))
                if deaths is not None:
                    rows.append(("💀 死亡", _format_number(deaths)))
                damage_done = combat.get("damage_done")
                if damage_done is not None:
                    rows.append(("🔥 伤害", _format_number(damage_done)))
                healing_done = combat.get("healing_done")
                if healing_done is not None:
                    rows.append(("💚 治疗", _format_number(healing_done)))

            game_stats = categories.get("game", {})
            if game_stats:
                games_played = game_stats.get("games_played")
                games_won = game_stats.get("games_won")
                if games_played is not None and games_won is not None:
                    games_lost = (games_played or 0) - (games_won or 0)
                    winrate = (
                        (games_won / games_played * 100)
                        if games_played > 0
                        else 0
                    )
                    rows.append((
                        "🎮 场次",
                        f"{_format_number(games_played)} "
                        f"({_format_number(games_won)}胜/{_format_number(games_lost)}负, "
                        f"{winrate:.1f}%)",
                    ))
                time_played = game_stats.get("time_played")
                if time_played:
                    rows.append(("⏱ 时间", _format_time_played(time_played)))

            hero_cards.append((hero_key_raw, hero_name, rows))

            # 只显示前 8 个英雄（避免消息过长）
            if len(hero_cards) >= 8:
                remaining = len(data) - 8
                if remaining < 0:
                    remaining = 0
                break

        gamemode_label = GAMEMODE_MAPPING.get(gamemode, gamemode)
        hero_filter_name = _get_hero_name_cn(hero_key) if hero_key else None

        # ===== 图片渲染模式（开启时优先，失败自动回退文字）=====
        if self.enable_image_render and _RENDERER_AVAILABLE and hero_cards:
            try:
                # 每个英雄区块前渲染英雄头像
                portraits = await self._fetch_hero_portraits([k for k, _, _ in hero_cards])
                render_heroes = [
                    (name, rows, portraits.get(key))
                    for key, name, rows in hero_cards
                ]
                img_path = image_renderer.render_career_card(
                    player_id=player_id,
                    gamemode_label=gamemode_label,
                    platform_label=_get_platform_display(platform),
                    hero_filter=hero_filter_name,
                    heroes=render_heroes,
                    remaining=remaining,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"生涯统计图片渲染失败，回退为文字输出: {e}")
                logger.debug("生涯统计图片渲染错误堆栈:", exc_info=True)

        # 标题
        hero_filter = f" | 英雄: {hero_filter_name}" if hero_filter_name else ""
        lines = [
            f"📈 {player_id} | {gamemode_label} | {_get_platform_display(platform)}{hero_filter}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

        for _, hero_name, rows in hero_cards:
            lines.append(f"\n🦸 {hero_name}")
            for label, value in rows:
                lines.append(f"   {label}: {value}")

        if remaining > 0:
            lines.append(f"\n... 还有 {remaining} 个英雄的数据未显示")

        if not hero_cards:
            lines.append("暂无生涯统计数据。")

        yield event.plain_result("\n".join(lines))

    @filter.command("owhero")
    async def hero_info(self, event: AstrMessageEvent, hero_name: str = ""):
        """查询英雄详细信息。

        用法: /owhero <英雄名>
        英雄名支持中文（如 源氏、安娜）或英文（如 genji, ana）
        示例: /owhero 源氏, /owhero ana
        """
        if not hero_name or not hero_name.strip():
            yield event.plain_result(
                "❌ 请输入英雄名称。\n"
                "用法: /owhero <英雄名>\n"
                "英雄名支持中文或英文，如: /owhero 源氏, /owhero genji"
            )
            return

        hero_key = _resolve_hero_name(hero_name)

        hero_stat: dict | None = None
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_hero_info(hero_key)
                # 同步查询该英雄在当前配置地区/平台/模式下的胜率与选取率
                try:
                    all_stats = await client.get_heroes_stats(
                        platform=self.default_platform,
                        gamemode=self.default_gamemode,
                        region=self.default_region,
                    )
                    for item in all_stats or []:
                        if isinstance(item, dict) and item.get("hero") == hero_key:
                            hero_stat = item
                            break
                except Exception as se:
                    logger.debug(f"获取英雄胜率失败（不影响英雄信息展示）: {se}")
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到英雄 `{hero_key}`。\n"
                    f"💡 请检查英雄名拼写，支持中文（如 源氏）或英文（如 genji）。"
                )
                return
            yield event.plain_result(self._api_error_reply(e, "❌ 获取英雄信息失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取英雄信息时发生错误: {e}")
            logger.debug("获取英雄信息错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取英雄信息时出错，请稍后重试。")
            return

        name = data.get("name", hero_key)
        description = data.get("description", "")
        role = data.get("role", "")
        health = data.get("hitpoints", {}).get("health", 0) if isinstance(data.get("hitpoints"), dict) else 0
        armor = data.get("hitpoints", {}).get("armor", 0) if isinstance(data.get("hitpoints"), dict) else 0
        shields = data.get("hitpoints", {}).get("shields", 0) if isinstance(data.get("hitpoints"), dict) else 0
        portrait = data.get("portrait", "")
        abilities = data.get("abilities", [])
        story_summary = ""
        if isinstance(data.get("story"), dict):
            story_summary = data["story"].get("summary", "")

        lines = [
            f"🦸 {name}",
            f"角色: {_get_role_display(role) if role else '未知'}",
            f"生命: {health}{' | 护甲: ' + str(armor) if armor else ''}{' | 护盾: ' + str(shields) if shields else ''}",
        ]
        # 全服胜率/选取率（当前配置的地区/平台/模式）
        if hero_stat:
            winrate = hero_stat.get("winrate", 0) or 0
            pickrate = hero_stat.get("pickrate", 0) or 0
            lines.append(
                f"📊 全服数据 ({_get_region_display(self.default_region)} | "
                f"{GAMEMODE_MAPPING.get(self.default_gamemode, self.default_gamemode)} | "
                f"{_get_platform_display(self.default_platform)}): "
                f"胜率 {winrate:.1f}% | 选取率 {pickrate:.1f}%"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━")

        # 技能列表
        if abilities:
            lines.append("📋 技能:")
            for ability in abilities[:8]:
                if isinstance(ability, dict):
                    ability_name = ability.get("name", "")
                    ability_desc = ability.get("description", "")
                    # 截断过长的描述
                    if len(ability_desc) > 80:
                        ability_desc = ability_desc[:77] + "..."
                    lines.append(f"   • {ability_name}: {ability_desc}")

        # 背景故事
        if story_summary:
            story_text = story_summary
            if len(story_text) > 200:
                story_text = story_text[:197] + "..."
            lines.append("")
            lines.append("📖 背景故事:")
            lines.append(f"   {story_text}")

        result_text = "\n".join(lines)

        # 如果有头像图片，发送图片 + 文本
        if portrait:
            chain = [
                Comp.Image.fromURL(portrait),
                Comp.Plain(result_text),
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result(result_text)

    @filter.command("owherostats")
    async def heroes_stats(self, event: AstrMessageEvent, role: str = "", region: str = ""):
        """查询全服英雄胜率/选取率排行榜（按地区服务器统计）。

        用法: /owherostats [角色] [地区]
        角色: 坦克(tank)、输出(damage)、支援(support)，不填则显示全部
        地区: 亚服(asia)、美服(americas)、欧服(europe)，不填则使用配置中的默认地区
        平台与游戏模式使用配置文件中的默认值
        示例:
            /owherostats
            /owherostats 输出
            /owherostats 支援 欧服
        """
        # 解析角色与地区参数（两个参数都可选，且顺序可交换）
        role_filter: str | None = None
        resolved_region: str | None = None
        ROLE_CN_TO_EN = {
            "坦克": "tank", "tank": "tank", "重装": "tank",
            "输出": "damage", "damage": "damage",
            "支援": "support", "support": "support", "辅助": "support",
        }
        for arg in (role, region):
            arg = (arg or "").strip()
            if not arg:
                continue
            lowered = arg.lower()
            if lowered in ROLE_CN_TO_EN or arg in ROLE_CN_TO_EN:
                if role_filter is not None:
                    yield event.plain_result("❌ 角色参数重复。可选: 坦克、输出、支援")
                    return
                role_filter = ROLE_CN_TO_EN.get(lowered) or ROLE_CN_TO_EN.get(arg)
            elif _resolve_region(arg):
                if resolved_region is not None:
                    yield event.plain_result("❌ 地区参数重复。可选: 亚服、美服、欧服")
                    return
                resolved_region = _resolve_region(arg)
            else:
                yield event.plain_result(
                    f"❌ 无法识别的参数 `{arg}`。\n"
                    "用法: /owherostats [角色] [地区]\n"
                    "角色: 坦克、输出、支援；地区: 亚服、美服、欧服"
                )
                return

        region = resolved_region or self.default_region
        platform = self.default_platform
        gamemode = self.default_gamemode

        try:
            async with OverFastAPIClient() as client:
                stats = await client.get_heroes_stats(
                    platform=platform,
                    gamemode=gamemode,
                    region=region,
                    role=role_filter,
                    order_by="winrate:desc",
                )
        except ValueError as e:
            yield event.plain_result(self._api_error_reply(e, "❌ 获取英雄统计失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取英雄统计时发生错误: {e}")
            logger.debug("获取英雄统计错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取英雄统计时出错，请稍后重试。")
            return

        if not stats or not isinstance(stats, list):
            yield event.plain_result(
                f"📊 英雄统计 | {_get_region_display(region)} | "
                f"{GAMEMODE_MAPPING.get(gamemode, gamemode)} | {_get_platform_display(platform)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n暂无数据。"
            )
            return

        role_text = f" | {ROLE_MAPPING.get(role_filter, (role_filter,))[0]}" if role_filter else ""
        lines = [
            f"📊 英雄胜率排行 | {_get_region_display(region)}{role_text}",
            f"{GAMEMODE_MAPPING.get(gamemode, gamemode)} | {_get_platform_display(platform)}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

        # 展示全部英雄胜率（按胜率降序）
        for idx, item in enumerate(stats, 1):
            if not isinstance(item, dict):
                continue
            hero_key = item.get("hero", "")
            hero_name = _get_hero_name_cn(hero_key)
            winrate = item.get("winrate", 0) or 0
            pickrate = item.get("pickrate", 0) or 0
            lines.append(
                f"{idx:>2}. {hero_name:<6} 胜率 {winrate:.1f}% | 选取率 {pickrate:.1f}%"
            )
        lines.append("")
        lines.append("💡 可加参数筛选: /owherostats 输出 欧服")

        yield event.plain_result("\n".join(lines))

    # ===== ID 绑定相关指令 =====

    @filter.command("owbind")
    async def bind_id(self, event: AstrMessageEvent, player_id: str = "", platform: str = ""):
        """绑定 Overwatch ID 到当前 QQ 号，可选择平台（PC端/主机端）。

        每个 QQ 号可绑定多个账号（数量上限见配置 max_binds_per_user，默认 3 个），
        新绑定的账号自动成为默认查询账号，可用 /owdefault 切换。

        用法: /owbind <玩家ID> [平台]
        平台: pc(电脑端，默认)、console(主机端)
        示例: /owbind TeKrop#2217
              /owbind TeKrop#2217 主机
        """
        if not player_id or not player_id.strip():
            yield event.plain_result(
                "❌ 请输入要绑定的玩家 ID。\n"
                "用法: /owbind <玩家ID> [平台]\n"
                "平台: pc(电脑端)、console(主机端)，不填则使用默认平台\n"
                "示例: /owbind TeKrop#2217\n"
                "      /owbind TeKrop#2217 主机\n"
                "💡 你的 Overwatch ID 就是你的 BattleTag（如 玩家名#1234）\n"
                f"   每个 QQ 号最多绑定 {self.max_binds_per_user} 个账号，使用 /owbinds 查看绑定列表"
            )
            return

        # 解析平台参数
        if platform and platform.strip():
            resolved_platform = _resolve_platform(platform)
            if not resolved_platform:
                yield event.plain_result(
                    f"❌ 平台参数 `{platform}` 无效。\n"
                    "可选平台: pc(电脑端)、console(主机端)\n"
                    "示例: /owbind TeKrop#2217 主机"
                )
                return
            platform = resolved_platform
        else:
            # 未指定平台时使用配置中的默认平台
            platform = self.default_platform

        # 外部输入的 ID 自动将 # 替换为 - 后存储（KV 中保留规范化形式）
        player_id = _normalize_player_id(player_id)
        user_name = event.get_sender_name()

        # 绑定数量预检（给更友好的提示，实际以 _add_binding 为准）
        current = await self._load_bindings(event)
        is_existing = any(
            a["player_id"].lower() == player_id.lower() for a in current["accounts"]
        )
        if not is_existing and len(current["accounts"]) >= self.max_binds_per_user:
            yield event.plain_result(
                f"❌ {user_name} 你最多只能绑定 {self.max_binds_per_user} 个 Overwatch 账号。\n"
                f"💡 使用 /owbinds 查看已绑定账号，/owunbind [玩家ID] 解绑后再绑定。"
            )
            return

        # 验证玩家 ID 是否有效（尝试查询一次）
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_summary(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}`，请检查 ID 是否正确。\n"
                    f"💡 提示: ID 区分大小写，确保你的 BattleTag 输入正确（支持直接输入 #）。"
                )
                return
            logger.warning(f"验证玩家 ID 失败: {e}")
            logger.debug("验证玩家 ID 错误堆栈:", exc_info=True)
            # 网络问题时不阻止绑定，继续
        except Exception as e:
            logger.warning(f"验证玩家 ID 时网络错误: {e}")
            logger.debug("验证玩家 ID 网络错误堆栈:", exc_info=True)
            # 网络问题时不阻止绑定，继续

        # 保存绑定
        result, data = await self._add_binding(event, player_id, platform)
        if result == "limit":
            yield event.plain_result(
                f"❌ {user_name} 你最多只能绑定 {self.max_binds_per_user} 个 Overwatch 账号。\n"
                f"💡 使用 /owbinds 查看已绑定账号，/owunbind [玩家ID] 解绑后再绑定。"
            )
        elif result in ("added", "updated"):
            action = "绑定" if result == "added" else "更新绑定"
            count = len(data["accounts"]) if data else 1
            yield event.plain_result(
                f"✅ {user_name} 已成功{action} Overwatch ID: `{player_id}`\n"
                f"   绑定平台: {_get_platform_display(platform)}（已设为默认查询账号）\n"
                f"   当前已绑定 {count}/{self.max_binds_per_user} 个账号\n"
                f"\n"
                f"现在你可以直接使用以下快捷指令（默认查询该账号）:\n"
                f"  /owme          - 查看自己的摘要信息\n"
                f"  /owsummary     - 查看自己的摘要信息\n"
                f"  /owstats [模式] - 查看自己的统计概览\n"
                f"  /owcareer <模式> [英雄] - 查看自己的生涯统计\n"
                f"\n"
                f"💡 /owbinds 查看绑定列表，/owdefault <玩家ID> 切换默认账号\n"
                f"   /owunbind [玩家ID] 解绑账号（不填则解绑当前默认账号）"
            )
        else:
            yield event.plain_result("❌ 绑定失败，请稍后重试。")

    @filter.command("owunbind")
    async def unbind_id(self, event: AstrMessageEvent, player_id: str = ""):
        """解绑当前 QQ 号绑定的 Overwatch ID。

        用法: /owunbind [玩家ID]
        说明: 不填玩家ID时解绑当前默认查询账号
        """
        user_name = event.get_sender_name()
        target = _normalize_player_id(player_id) if player_id and player_id.strip() else None

        result, removed_id = await self._remove_binding(event, target)
        if result == "empty":
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定任何 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> [平台] 来绑定你的账号。"
            )
        elif result == "not_found":
            yield event.plain_result(
                f"❌ 你没有绑定账号 `{target}`。\n"
                f"💡 使用 /owbinds 查看你已绑定的账号列表。"
            )
        elif result == "removed":
            remaining = await self._load_bindings(event)
            count = len(remaining["accounts"])
            tip = (
                f"💡 剩余 {count} 个绑定账号，默认账号已切换为 `{remaining['default']}`"
                if count
                else "💡 需要重新绑定时使用 /owbind <玩家ID> [平台]"
            )
            yield event.plain_result(
                f"✅ {user_name} 已成功解绑 Overwatch ID: `{removed_id}`\n{tip}"
            )
        else:
            yield event.plain_result("❌ 解绑失败，请稍后重试。")

    @filter.command("owbinds")
    async def list_bindings(self, event: AstrMessageEvent):
        """查看当前 QQ 号绑定的所有 Overwatch 账号。

        用法: /owbinds
        """
        user_name = event.get_sender_name()
        data = await self._load_bindings(event)
        accounts = data["accounts"]

        if not accounts:
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定任何 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> [平台] 来绑定你的账号。"
            )
            return

        default = data.get("default")
        lines = [
            f"📋 {user_name} 的绑定列表 ({len(accounts)}/{self.max_binds_per_user}):",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for idx, acc in enumerate(accounts, 1):
            pid = acc["player_id"]
            platform_display = _get_platform_display(acc.get("platform", self.default_platform))
            mark = " ⭐默认" if pid == default else ""
            lines.append(f"{idx}. `{pid}` | {platform_display}{mark}")
        lines.append("")
        lines.append("💡 /owdefault <玩家ID> 切换默认查询账号")
        lines.append("   /owunbind [玩家ID] 解绑（不填则解绑默认账号）")
        yield event.plain_result("\n".join(lines))

    @filter.command("owdefault")
    async def set_default_binding(self, event: AstrMessageEvent, player_id: str = ""):
        """设置默认查询的 Overwatch 账号。

        快捷指令（/owme、/owsummary、/owstats、/owcareer 省略 ID 时）
        将查询默认账号的数据。

        用法: /owdefault <玩家ID>
        示例: /owdefault TeKrop#2217
        """
        user_name = event.get_sender_name()
        if not player_id or not player_id.strip():
            yield event.plain_result(
                "❌ 请输入要设为默认的玩家 ID。\n"
                "用法: /owdefault <玩家ID>\n"
                "💡 使用 /owbinds 查看你已绑定的账号列表。"
            )
            return

        target = _normalize_player_id(player_id)
        data = await self._load_bindings(event)
        accounts = data["accounts"]

        if not accounts:
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定任何 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> [平台] 来绑定你的账号。"
            )
            return

        matched = next(
            (a for a in accounts if a["player_id"].lower() == target.lower()), None
        )
        if not matched:
            yield event.plain_result(
                f"❌ 你没有绑定账号 `{target}`。\n"
                f"💡 先使用 /owbind {target} 绑定，或使用 /owbinds 查看已绑定账号。"
            )
            return

        data["default"] = matched["player_id"]
        if await self._save_bindings(event, data):
            yield event.plain_result(
                f"✅ 已将默认查询账号设为: `{matched['player_id']}` "
                f"({_get_platform_display(matched.get('platform', self.default_platform))})\n"
                f"💡 之后 /owme、/owstats 等快捷指令将查询该账号"
            )
        else:
            yield event.plain_result("❌ 设置失败，请稍后重试。")

    @filter.command("owme")
    async def quick_summary(self, event: AstrMessageEvent):
        """快捷查询自己绑定的 Overwatch 账号摘要信息。

        用法: /owme
        说明: 需要先使用 /owbind 绑定账号（查询时使用绑定平台）
        """
        bound_id, bound_platform = await self._get_binding(event)
        user_name = event.get_sender_name()

        if not bound_id:
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> [平台] 绑定你的账号\n"
                f"   示例: /owbind TeKrop#2217 主机"
            )
            return

        platform = self._effective_platform(bound_platform)

        # 绑定存储中的 ID 已是规范化形式（- 分隔），直接使用，不做替换
        player_id = bound_id

        try:
            async with OverFastAPIClient() as client:
                full = await client.get_player_full(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "未找到" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到绑定的玩家 `{player_id}`。\n"
                    f"💡 该账号可能已改名或资料已私密，请使用 /owbind 重新绑定。"
                )
                return
            logger.warning(f"获取玩家摘要失败: {e}")
            yield event.plain_result(self._api_error_reply(e, "❌ 获取玩家信息失败，请稍后重试。"))
            return
        except Exception as e:
            logger.error(f"获取玩家摘要时发生错误: {e}")
            logger.debug("获取玩家摘要错误堆栈:", exc_info=True)
            yield event.plain_result("❌ 获取玩家信息时出错，请稍后重试。")
            return

        async for res in self._send_summary_result(
            event,
            full,
            player_id,
            platform,
            footer_note=f"快捷查询 | 绑定ID: {bound_id} | {_get_platform_display(platform)}",
            extra_lines=[
                "",
                "💡 其他快捷指令:",
                "   /owstats [模式]  - 统计概览",
                "   /owcareer <模式> [英雄] - 生涯统计",
                "   /owunbind       - 解绑账号",
            ],
        ):
            yield res
