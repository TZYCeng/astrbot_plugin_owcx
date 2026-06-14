"""
OW战绩查询插件 - AstrBot 插件主模块。

基于 OverFast API 提供 Overwatch 2 玩家战绩查询功能，
支持搜索玩家、查询摘要、统计概览、生涯统计、英雄信息等功能。
"""

from astrbot.api import logger
from astrbot.api.all import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .api_client import OverFastAPIClient

# ===== 常量定义 =====

# 段位中英文映射与图标
RANK_MAPPING = {
    "bronze": ("青铜", "🥉"),
    "silver": ("白银", "🥈"),
    "gold": ("黄金", "🥇"),
    "platinum": ("铂金", "🥈"),
    "diamond": ("钻石", "💎"),
    "master": ("大师", "🥇"),
    "grandmaster": ("宗师", "🏆"),
    "champion": ("冠军", "👑"),
    "top500": ("五百强", "🌟"),
}

# 角色中英文映射与图标
ROLE_MAPPING = {
    "tank": ("坦克", "🛡️"),
    "damage": ("输出", "⚔️"),
    "support": ("支援", "💚"),
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
    "support": "💚",
}

# 英雄英文名到中文名的映射（用于输出显示）
HERO_NAME_MAPPING = {
    # 坦克
    "doomfist": "末日铁拳",
    "dva": "D.Va",
    "orisa": "奥丽莎",
    "reinhardt": "莱因哈特",
    "roadhog": "路霸",
    "sigma": "西格玛",
    "winston": "温斯顿",
    "wrecking-ball": "破坏球",
    "zarya": "查莉娅",
    "junker-queen": "渣客女王",
    "ramattra": "拉玛刹",
    "mauga": "毛加",
    # 输出
    "ashe": "艾什",
    "bastion": "堡垒",
    "cassidy": "卡西迪",
    "echo": "回声",
    "genji": "源氏",
    "hanzo": "半藏",
    "junkrat": "狂鼠",
    "mei": "美",
    "pharah": "法老之鹰",
    "reaper": "死神",
    "soldier-76": "士兵:76",
    "sojourn": "索杰恩",
    "sombra": "黑影",
    "symmetra": "秩序之光",
    "torbjorn": "托比昂",
    "tracer": "猎空",
    "venture": "探奇",
    "widowmaker": "黑百合",
    # 支援
    "ana": "安娜",
    "baptiste": "巴蒂斯特",
    "brigitte": "布丽吉塔",
    "kiriko": "雾子",
    "lifeweaver": "生命之梭",
    "lucio": "卢西奥",
    "mercy": "天使",
    "moira": "莫伊拉",
    "zenyatta": "禅雅塔",
    "juno": "朱诺",
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
        /owsearch <玩家名>       - 搜索玩家
        /owsummary <玩家ID>      - 查询玩家摘要（头像、段位等）
        /owstats <玩家ID> [模式]  - 查询玩家统计概览
        /owcareer <玩家ID> <模式> [英雄] - 查询生涯统计
        /owhero <英雄名>         - 查询英雄信息
        /owheroes [角色]         - 列出所有英雄
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

    async def _get_bound_id(self, event: AstrMessageEvent) -> str | None:
        """获取用户绑定的 Overwatch ID。

        Args:
            event: 消息事件对象。

        Returns:
            绑定的玩家 ID，未绑定则返回 None。
        """
        qq_id = event.get_sender_id()
        if not qq_id:
            return None
        try:
            bound_id = await self.get_kv_data(self._get_bind_key(qq_id), None)
            return bound_id if bound_id else None
        except Exception as e:
            logger.debug(f"读取绑定信息失败: {e}")
            return None

    async def _set_bound_id(self, event: AstrMessageEvent, player_id: str) -> bool:
        """设置用户绑定的 Overwatch ID。

        Args:
            event: 消息事件对象。
            player_id: 要绑定的玩家 ID。

        Returns:
            是否绑定成功。
        """
        qq_id = event.get_sender_id()
        if not qq_id:
            return False
        try:
            await self.put_kv_data(self._get_bind_key(qq_id), player_id)
            return True
        except Exception as e:
            logger.error(f"保存绑定信息失败: {e}")
            return False

    async def _delete_bound_id(self, event: AstrMessageEvent) -> bool:
        """删除用户绑定的 Overwatch ID。

        Args:
            event: 消息事件对象。

        Returns:
            是否解绑成功。
        """
        qq_id = event.get_sender_id()
        if not qq_id:
            return False
        try:
            await self.delete_kv_data(self._get_bind_key(qq_id))
            return True
        except Exception as e:
            logger.error(f"删除绑定信息失败: {e}")
            return False

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
        self.default_platform: str = self.config.get("default_platform", "pc")
        logger.info("OW战绩查询插件已加载")

    @filter.command("owsearch")
    async def search_player(self, event: AstrMessageEvent, name: str = ""):
        """搜索 Overwatch 2 玩家。

        用法: /owsearch <玩家名>
        示例: /owsearch TeKrop
        """
        if not name or not name.strip():
            yield event.plain_result(
                "❌ 请输入要搜索的玩家名称。\n"
                "用法: /owsearch <玩家名>\n"
                "示例: /owsearch TeKrop"
            )
            return

        try:
            async with OverFastAPIClient() as client:
                result = await client.search_players(name.strip())
        except ValueError as e:
            logger.warning(f"搜索玩家失败: {e}")
            yield event.plain_result(f"❌ 搜索失败: {e}")
            return
        except Exception as e:
            logger.error(f"搜索玩家时发生错误: {e}")
            yield event.plain_result("❌ 搜索时发生网络错误，请稍后重试。")
            return

        total = result.get("total", 0)
        players = result.get("results", [])

        if total == 0 or not players:
            yield event.plain_result(
                f'🔍 未找到名称包含 "{name}" 的玩家。\n'
                f"💡 提示: 尝试使用完整的 BattleTag（如 TeKrop-2217）"
            )
            return

        lines = [f'🔍 搜索 "{name}" 找到 {total} 个结果:', ""]

        for idx, player in enumerate(players[:10], 1):
            player_id = player.get("player_id", "未知")
            player_name = player.get("name", "未知")
            privacy = player.get("privacy", "unknown")
            privacy_icon = "✅ 公开" if privacy == "public" else "🔒 私密"

            lines.append(f"{idx}. {player_name}")
            lines.append(f"   隐私: {privacy_icon}")
            lines.append("")

        if total > 10:
            lines.append(f"... 还有 {total - 10} 个结果未显示")
            lines.append("")

        lines.append("💡 使用 /owsummary <玩家ID> 查看详细信息")
        lines.append("   支持直接使用 #，如 /owsummary TeKrop#2217")

        yield event.plain_result("\n".join(lines))

    @filter.command("owsummary")
    async def player_summary(self, event: AstrMessageEvent, player_id: str = ""):
        """查询玩家摘要信息（头像、竞技段位等）。

        用法: /owsummary [玩家ID]
        示例: /owsummary TeKrop#2217
        说明: 支持直接使用 #，会自动替换；省略 ID 则查询绑定的账号
        """
        # 未传入 ID，尝试获取绑定的 ID
        if not player_id or not player_id.strip():
            bound_id = await self._get_bound_id(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owsummary <玩家ID>\n"
                    "示例: /owsummary TeKrop#2217\n"
                    "💡 或使用 /owbind <玩家ID> 绑定你的账号，之后可直接用 /owsummary 查询"
                )
                return
            player_id = bound_id

        player_id = _normalize_player_id(player_id)

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_summary(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "未找到" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}`。\n"
                    f"💡 请检查玩家 ID 是否正确，或将 # 替换为 -。\n"
                    f"   使用 /owsearch <玩家名> 来搜索玩家。"
                )
                return
            logger.warning(f"获取玩家摘要失败: {e}")
            yield event.plain_result(f"❌ 获取玩家信息失败: {e}")
            return
        except Exception as e:
            logger.error(f"获取玩家摘要时发生错误: {e}")
            yield event.plain_result("❌ 获取玩家信息时出错，请稍后重试。")
            return

        username = data.get("username", player_id)
        avatar_url = data.get("avatar", "")
        endorsement = data.get("endorsement", {})
        endorsement_level = endorsement.get("level", 0) if isinstance(endorsement, dict) else 0
        title = data.get("title", "")

        # 构建竞技段位信息
        rank_lines = []
        comp_ranks = data.get("competitive_ranks", {})
        pc_ranks = comp_ranks.get("pc", {}) if isinstance(comp_ranks, dict) else {}

        if pc_ranks:
            for role_key in ["tank", "damage", "support"]:
                role_data = pc_ranks.get(role_key)
                role_display = COMPETITIVE_ICONS.get(role_key, "") + " " + ROLE_MAPPING.get(role_key, (role_key, ""))[0]

                if role_data and isinstance(role_data, dict):
                    division = role_data.get("division")
                    tier = role_data.get("tier")
                    if division:
                        rank_display = _get_rank_display(division, tier)
                        rank_lines.append(f"   {role_display}: {rank_display}")
                    else:
                        rank_lines.append(f"   {role_display}: 未定位")
                else:
                    rank_lines.append(f"   {role_display}: 未定位")
        else:
            rank_lines.append("   暂无竞技段位数据")

        lines = [
            f"👤 {username}",
        ]
        if title:
            lines.append(f"🏷️ 头衔: {title}")
        lines.append(f"⭐ 赞赏等级: {endorsement_level}")
        lines.append("🏆 竞技段位:")
        lines.extend(rank_lines)

        result_text = "\n".join(lines)

        # 如果有头像，发送图片 + 文本
        if avatar_url:
            import astrbot.api.message_components as Comp

            chain = [
                Comp.Image.fromURL(avatar_url),
                Comp.Plain(result_text),
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result(result_text)

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
        说明: 省略 ID 则查询绑定的账号
        """
        # 未传入 ID，尝试获取绑定的 ID
        if not player_id or not player_id.strip():
            bound_id = await self._get_bound_id(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owstats <玩家ID> [游戏模式]\n"
                    "示例: /owstats TeKrop#2217 竞技\n"
                    "游戏模式: 快速(quickplay)、竞技(competitive，默认)\n"
                    "💡 或使用 /owbind <玩家ID> 绑定你的账号，之后可直接用 /owstats 查询"
                )
                return
            player_id = bound_id

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
                    player_id, gamemode=gamemode, platform=self.default_platform
                )
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}` 或其资料为私密状态。\n"
                    f"💡 请将 Overwatch 资料设为公开后重试。"
                )
                return
            yield event.plain_result(f"❌ 获取统计失败: {e}")
            return
        except Exception as e:
            logger.error(f"获取玩家统计时发生错误: {e}")
            yield event.plain_result("❌ 获取统计信息时出错，请稍后重试。")
            return

        general = data.get("general", {}) if isinstance(data, dict) else {}
        if not general:
            yield event.plain_result(
                f"📊 玩家 `{player_id}` | {GAMEMODE_MAPPING.get(gamemode, gamemode)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"暂无统计数据。"
            )
            return

        games_played = general.get("games_played", 0) or 0
        games_won = general.get("games_won", 0) or 0
        games_lost = general.get("games_lost", 0) or 0
        winrate = general.get("winrate", 0) or 0
        kda = general.get("kda", 0) or 0
        eliminations_avg = general.get("eliminations_avg", 0) or 0
        deaths_avg = general.get("deaths_avg", 0) or 0
        damage_avg = general.get("damage_avg", 0) or 0
        healing_avg = general.get("healing_avg", 0) or 0
        time_played = general.get("time_played", 0) or 0

        lines = [
            f"📊 {player_id} | {GAMEMODE_MAPPING.get(gamemode, gamemode)}",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🎮 场次: {_format_number(games_played)} ({_format_number(games_won)}胜/{_format_number(games_lost)}负)",
            f"📈 胜率: {winrate}%",
            f"⚔️ KDA: {kda:.2f}" if kda else "⚔️ KDA: N/A",
            f"💥 消灭: {_format_number(eliminations_avg)}/场" if eliminations_avg else "💥 消灭: N/A",
            f"💀 死亡: {_format_number(deaths_avg)}/场" if deaths_avg else "💀 死亡: N/A",
            f"🔥 伤害: {_format_number(damage_avg)}/场" if damage_avg else "🔥 伤害: N/A",
            f"💚 治疗: {_format_number(healing_avg)}/场" if healing_avg else "💚 治疗: N/A",
            f"⏱️ 游戏时间: {_format_time_played(time_played)}",
        ]

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
        # 未传入 ID，尝试获取绑定的 ID
        if not player_id or not player_id.strip():
            bound_id = await self._get_bound_id(event)
            if not bound_id:
                yield event.plain_result(
                    "❌ 你还没有绑定 Overwatch ID。\n"
                    "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                    "示例: /owcareer TeKrop#2217 竞技 源氏\n"
                    "💡 或使用 /owbind <玩家ID> 绑定你的账号，之后可直接用 /owcareer 竞技 源氏 查询"
                )
                return
            player_id = bound_id
        # player_id 传入但 gamemode 为空，说明只传了 gamemode（已绑定 ID 的快捷用法）
        elif not gamemode or not gamemode.strip():
            # 尝试将 player_id 当作 gamemode 解析
            resolved = _resolve_gamemode(player_id)
            if resolved in ("quickplay", "competitive"):
                bound_id = await self._get_bound_id(event)
                if bound_id:
                    gamemode = player_id
                    player_id = bound_id
                else:
                    yield event.plain_result(
                        "❌ 你还没有绑定 Overwatch ID。\n"
                        "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                        "💡 使用 /owbind <玩家ID> 绑定后可直接 /owcareer 竞技 源氏"
                    )
                    return

        resolved_mode = _resolve_gamemode(gamemode)
        if not resolved_mode or resolved_mode not in ("quickplay", "competitive"):
            yield event.plain_result(
                "❌ 请输入有效的游戏模式。\n"
                "用法: /owcareer <玩家ID> <游戏模式> [英雄名]\n"
                "游戏模式: 快速(quickplay)、竞技(competitive)"
            )
            return

        player_id = _normalize_player_id(player_id)
        gamemode = resolved_mode
        hero_key = _resolve_hero_name(hero) if hero else None

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_career_stats(
                    player_id,
                    gamemode=gamemode,
                    platform=self.default_platform,
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
            yield event.plain_result(f"❌ 获取生涯统计失败: {e}")
            return
        except Exception as e:
            logger.error(f"获取生涯统计时发生错误: {e}")
            yield event.plain_result("❌ 获取生涯统计时出错，请稍后重试。")
            return

        if not data or not isinstance(data, dict):
            yield event.plain_result(
                f"📈 玩家 `{player_id}` | {GAMEMODE_MAPPING.get(gamemode, gamemode)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"暂无生涯统计数据。"
            )
            return

        # 标题
        hero_filter = f" | 英雄: {_get_hero_name_cn(hero_key)}" if hero_key else ""
        lines = [
            f"📈 {player_id} | {GAMEMODE_MAPPING.get(gamemode, gamemode)}{hero_filter}",
            "━━━━━━━━━━━━━━━━━━━━",
        ]

        # 遍历每个英雄的数据
        hero_count = 0
        for hero_key_raw, categories in data.items():
            if not isinstance(categories, dict):
                continue

            hero_name = _get_hero_name_cn(hero_key_raw)
            hero_count += 1

            lines.append(f"\n🦸 {hero_name}")

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
                    lines.append(f"   💥 消灭: {_format_number(eliminations)}{kd}")
                if deaths is not None:
                    lines.append(f"   💀 死亡: {_format_number(deaths)}")
                damage_done = combat.get("damage_done")
                if damage_done is not None:
                    lines.append(f"   🔥 伤害: {_format_number(damage_done)}")
                healing_done = combat.get("healing_done")
                if healing_done is not None:
                    lines.append(f"   💚 治疗: {_format_number(healing_done)}")

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
                    lines.append(
                        f"   🎮 场次: {_format_number(games_played)} "
                        f"({_format_number(games_won)}胜/{_format_number(games_lost)}负, "
                        f"{winrate:.1f}%)"
                    )
                time_played = game_stats.get("time_played")
                if time_played:
                    lines.append(f"   ⏱️ 时间: {_format_time_played(time_played)}")

            # 只显示前 8 个英雄（避免消息过长）
            if hero_count >= 8:
                remaining = len(data) - 8
                if remaining > 0:
                    lines.append(f"\n... 还有 {remaining} 个英雄的数据未显示")
                break

        if hero_count == 0:
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
                "英雄名支持中文或英文，如: /owhero 源氏, /owhero genji\n"
                "使用 /owheroes 查看所有英雄列表。"
            )
            return

        hero_key = _resolve_hero_name(hero_name)

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_hero_info(hero_key)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到英雄 `{hero_key}`。\n"
                    f"💡 使用 /owheroes 查看所有可用的英雄名称。"
                )
                return
            yield event.plain_result(f"❌ 获取英雄信息失败: {e}")
            return
        except Exception as e:
            logger.error(f"获取英雄信息时发生错误: {e}")
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
            "━━━━━━━━━━━━━━━━━━━━",
        ]

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
            import astrbot.api.message_components as Comp

            chain = [
                Comp.Image.fromURL(portrait),
                Comp.Plain(result_text),
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result(result_text)

    @filter.command("owheroes")
    async def list_heroes_cmd(self, event: AstrMessageEvent, role: str = ""):
        """列出所有英雄，可按角色筛选。

        用法: /owheroes [角色]
        角色: 坦克(tank)、输出(damage)、支援(support)
        示例:
            /owheroes
            /owheroes 坦克
        """
        role_filter = role.lower().strip() if role else None

        # 支持中文角色名
        ROLE_CN_TO_EN = {
            "坦克": "tank",
            "tank": "tank",
            "输出": "damage",
            "damage": "damage",
            "支援": "support",
            "support": "support",
        }
        if role_filter:
            resolved_role = ROLE_CN_TO_EN.get(role_filter)
            if not resolved_role:
                yield event.plain_result(
                    "❌ 角色参数无效。可选: 坦克(tank)、输出(damage)、支援(support)\n"
                    "用法: /owheroes [坦克|输出|支援]"
                )
                return
            role_filter = resolved_role

        try:
            async with OverFastAPIClient() as client:
                heroes = await client.list_heroes(role=role_filter)
        except Exception as e:
            logger.error(f"获取英雄列表时发生错误: {e}")
            yield event.plain_result("❌ 获取英雄列表时出错，请稍后重试。")
            return

        if not heroes:
            yield event.plain_result("暂无英雄数据。")
            return

        # 按角色分组
        grouped: dict[str, list[str]] = {"tank": [], "damage": [], "support": []}
        for hero in heroes:
            if isinstance(hero, dict):
                h_key = hero.get("key", "")
                h_name = hero.get("name", h_key)
                h_role = hero.get("role", "")
                cn_name = _get_hero_name_cn(h_key)
                display = f"{cn_name} ({h_name})" if cn_name != h_key else h_name
                if h_role in grouped:
                    grouped[h_role].append(display)
                else:
                    grouped.setdefault("other", []).append(display)

        lines = ["🦸 Overwatch 英雄列表", "━━━━━━━━━━━━━━━━━━━━"]

        for role_key in ["tank", "damage", "support"]:
            role_heroes = grouped.get(role_key, [])
            if not role_heroes:
                continue
            role_display = _get_role_display(role_key)
            lines.append(f"\n{role_display} ({len(role_heroes)}):")
            # 每行显示 4 个英雄
            chunk_size = 4
            for i in range(0, len(role_heroes), chunk_size):
                chunk = role_heroes[i : i + chunk_size]
                lines.append("   " + "、".join(chunk))

        lines.append("")
        lines.append("💡 使用 /owhero <英雄key> 查看英雄详情")
        lines.append("   示例: /owhero genji, /owhero ana")

        yield event.plain_result("\n".join(lines))

    # ===== ID 绑定相关指令 =====

    @filter.command("owbind")
    async def bind_id(self, event: AstrMessageEvent, player_id: str = ""):
        """绑定你的 Overwatch ID 到当前 QQ 号。

        绑定后可直接使用 /owme、/owsummary、/owstats、/owcareer 等指令查询自己的数据。

        用法: /owbind <玩家ID>
        示例: /owbind TeKrop#2217
        """
        if not player_id or not player_id.strip():
            yield event.plain_result(
                "❌ 请输入要绑定的玩家 ID。\n"
                "用法: /owbind <玩家ID>\n"
                "示例: /owbind TeKrop#2217\n"
                "💡 你的 Overwatch ID 就是你的 BattleTag（如 玩家名#1234）"
            )
            return

        player_id = _normalize_player_id(player_id)
        qq_id = event.get_sender_id()
        user_name = event.get_sender_name()

        # 验证玩家 ID 是否有效（尝试查询一次）
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_summary(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到玩家 `{player_id}`，请检查 ID 是否正确。\n"
                    f"💡 提示: ID 区分大小写，确保你的 BattleTag 输入正确。\n"
                    f"   可使用 /owsearch <玩家名> 搜索确认。"
                )
                return
            logger.warning(f"验证玩家 ID 失败: {e}")
            # 网络问题时不阻止绑定，继续
        except Exception as e:
            logger.warning(f"验证玩家 ID 时网络错误: {e}")
            # 网络问题时不阻止绑定，继续

        # 保存绑定
        success = await self._set_bound_id(event, player_id)
        if success:
            yield event.plain_result(
                f"✅ {user_name} 已成功绑定 Overwatch ID: `{player_id}`\n"
                f"\n"
                f"现在你可以直接使用以下快捷指令:\n"
                f"  /owme          - 查看自己的摘要信息\n"
                f"  /owsummary     - 查看自己的摘要信息\n"
                f"  /owstats [模式] - 查看自己的统计概览\n"
                f"  /owcareer <模式> [英雄] - 查看自己的生涯统计\n"
                f"\n"
                f"如需更换绑定，直接再次使用 /owbind 即可。\n"
                f"如需解绑，使用 /owunbind 。"
            )
        else:
            yield event.plain_result("❌ 绑定失败，请稍后重试。")

    @filter.command("owunbind")
    async def unbind_id(self, event: AstrMessageEvent):
        """解绑当前 QQ 号绑定的 Overwatch ID。

        用法: /owunbind
        """
        qq_id = event.get_sender_id()
        user_name = event.get_sender_name()

        # 检查是否已绑定
        bound_id = await self._get_bound_id(event)
        if not bound_id:
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定任何 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> 来绑定你的账号。"
            )
            return

        success = await self._delete_bound_id(event)
        if success:
            yield event.plain_result(
                f"✅ {user_name} 已成功解绑 Overwatch ID: `{bound_id}`\n"
                f"💡 需要重新绑定时使用 /owbind <玩家ID>"
            )
        else:
            yield event.plain_result("❌ 解绑失败，请稍后重试。")

    @filter.command("owme")
    async def quick_summary(self, event: AstrMessageEvent):
        """快捷查询自己绑定的 Overwatch 账号摘要信息。

        用法: /owme
        说明: 需要先使用 /owbind 绑定账号
        """
        bound_id = await self._get_bound_id(event)
        user_name = event.get_sender_name()

        if not bound_id:
            yield event.plain_result(
                f"❌ {user_name} 你还没有绑定 Overwatch ID。\n"
                f"💡 使用 /owbind <玩家ID> 绑定你的账号\n"
                f"   示例: /owbind TeKrop#2217"
            )
            return

        # 复用 player_summary 的逻辑，但使用快捷查询的提示
        player_id = _normalize_player_id(bound_id)

        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_summary(player_id)
        except ValueError as e:
            err_str = str(e).lower()
            if "not found" in err_str or "未找到" in err_str or "404" in err_str:
                yield event.plain_result(
                    f"❌ 未找到绑定的玩家 `{player_id}`。\n"
                    f"💡 该账号可能已改名或资料已私密，请使用 /owbind 重新绑定。"
                )
                return
            logger.warning(f"获取玩家摘要失败: {e}")
            yield event.plain_result(f"❌ 获取玩家信息失败: {e}")
            return
        except Exception as e:
            logger.error(f"获取玩家摘要时发生错误: {e}")
            yield event.plain_result("❌ 获取玩家信息时出错，请稍后重试。")
            return

        username = data.get("username", player_id)
        avatar_url = data.get("avatar", "")
        endorsement = data.get("endorsement", {})
        endorsement_level = endorsement.get("level", 0) if isinstance(endorsement, dict) else 0
        title = data.get("title", "")

        # 构建竞技段位信息
        rank_lines = []
        comp_ranks = data.get("competitive_ranks", {})
        pc_ranks = comp_ranks.get("pc", {}) if isinstance(comp_ranks, dict) else {}

        if pc_ranks:
            for role_key in ["tank", "damage", "support"]:
                role_data = pc_ranks.get(role_key)
                role_display = COMPETITIVE_ICONS.get(role_key, "") + " " + ROLE_MAPPING.get(role_key, (role_key, ""))[0]

                if role_data and isinstance(role_data, dict):
                    division = role_data.get("division")
                    tier = role_data.get("tier")
                    if division:
                        rank_display = _get_rank_display(division, tier)
                        rank_lines.append(f"   {role_display}: {rank_display}")
                    else:
                        rank_lines.append(f"   {role_display}: 未定位")
                else:
                    rank_lines.append(f"   {role_display}: 未定位")
        else:
            rank_lines.append("   暂无竞技段位数据")

        lines = [
            f"👤 {username}",
            f"   (快捷查询 | 绑定ID: {bound_id})",
        ]
        if title:
            lines.append(f"🏷️ 头衔: {title}")
        lines.append(f"⭐ 赞赏等级: {endorsement_level}")
        lines.append("🏆 竞技段位:")
        lines.extend(rank_lines)
        lines.append("")
        lines.append("💡 其他快捷指令:")
        lines.append("   /owstats [模式]  - 统计概览")
        lines.append("   /owcareer <模式> [英雄] - 生涯统计")
        lines.append("   /owunbind       - 解绑账号")

        result_text = "\n".join(lines)

        # 如果有头像，发送图片 + 文本
        if avatar_url:
            import astrbot.api.message_components as Comp

            chain = [
                Comp.Image.fromURL(avatar_url),
                Comp.Plain(result_text),
            ]
            yield event.chain_result(chain)
        else:
            yield event.plain_result(result_text)
