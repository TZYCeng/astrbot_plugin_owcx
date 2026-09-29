"""OW战绩查询插件（重构版：常量/工具/绑定已拆分）。"""

import asyncio

import aiohttp

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.all import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .api_client import OverFastAPIClient
from .bindings import BindingStore
from .constants import (
    GAMEMODE_MAPPING,
    GAMEMODE_REVERSE_MAPPING,
    HERO_NAME_MAPPING,
    HERO_NAME_REVERSE_MAPPING,
    PLATFORM_MAPPING,
    PLATFORM_REVERSE_MAPPING,
    RANK_MAPPING,
    REGION_MAPPING,
    REGION_REVERSE_MAPPING,
    ROLE_CN_TO_EN,
    ROLE_MAPPING,
)
from .utils import (
    build_rank_data as _build_rank_data,
    extract_top_heroes as _extract_top_heroes,
    format_number as _format_number,
    format_time_played as _format_time_played,
    format_time_short as _format_time_short,
    get_hero_name_cn as _get_hero_name_cn,
    get_platform_display as _get_platform_display,
    get_rank_display as _get_rank_display,
    get_region_display as _get_region_display,
    get_role_display as _get_role_display,
    normalize_player_id as _normalize_player_id,
    resolve_gamemode as _resolve_gamemode,
    resolve_hero_name as _resolve_hero_name,
    resolve_platform as _resolve_platform,
    resolve_region as _resolve_region,
    validate_player_id as _validate_player_id,
)

# 向后兼容：保留旧导入路径
__all__ = [
    "OverwatchStatsPlugin",
    "RANK_MAPPING",
    "ROLE_MAPPING",
    "GAMEMODE_MAPPING",
    "PLATFORM_MAPPING",
    "REGION_MAPPING",
    "HERO_NAME_MAPPING",
]

try:
    from . import image_renderer

    _RENDERER_AVAILABLE = True
    try:
        image_renderer.cleanup_old_images()
    except Exception:
        pass
except Exception:  # pragma: no cover
    image_renderer = None  # type: ignore[assignment]
    _RENDERER_AVAILABLE = False

_DOWNLOAD_SEM = asyncio.Semaphore(6)


class OverwatchStatsPlugin(BindingStore, Star):
    """OW战绩查询插件主类（基于 OverFast API）。"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        raw_gamemode = self.config.get("default_gamemode", "competitive")
        resolved = _resolve_gamemode(str(raw_gamemode))
        self.default_gamemode: str = resolved if resolved in ("quickplay", "competitive") else "competitive"
        raw_platform = self.config.get("default_platform", "pc")
        resolved_platform = _resolve_platform(str(raw_platform))
        self.default_platform: str = resolved_platform if resolved_platform in ("pc", "console") else "pc"
        raw_region = self.config.get("default_region", "asia")
        resolved_region = _resolve_region(str(raw_region))
        self.default_region: str = resolved_region if resolved_region in ("asia", "americas", "europe") else "asia"
        # 与 _conf_schema.json 保持一致，默认开启图片渲染
        self.enable_image_render: bool = bool(self.config.get("enable_image_render", True))
        self.show_api_error: bool = bool(self.config.get("show_api_error", False))
        try:
            self.max_binds_per_user: int = max(int(self.config.get("max_binds_per_user", 3) or 3), 1)
        except (TypeError, ValueError):
            self.max_binds_per_user = 3
        if self.enable_image_render and not _RENDERER_AVAILABLE:
            logger.warning("已开启图片渲染，但渲染模块加载失败（可能未安装 Pillow），将回退文字输出。pip install Pillow")
        logger.info(f"OW战绩查询插件已加载（图片渲染: {'开启' if self.enable_image_render else '关闭'}）")

    def _effective_platform(self, bound_platform: str | None = None) -> str:
        if bound_platform in ("pc", "console"):
            return bound_platform
        return self.default_platform

    def _api_error_reply(self, e: Exception, friendly: str) -> str:
        logger.debug(f"API 错误详情: {type(e).__name__}: {e}", exc_info=True)
        if self.show_api_error:
            detail = getattr(e, "detail", "") or str(e)
            retry_after = getattr(e, "retry_after", None)
            reply = f"查询出错: {detail}"
            if retry_after:
                reply += f"\n建议等待 {retry_after} 秒后重试"
            return reply
        return friendly

    @staticmethod
    async def _download_with_session(session: aiohttp.ClientSession, url: str) -> bytes | None:
        if not url:
            return None
        try:
            async with _DOWNLOAD_SEM:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.debug(f"下载图片失败: {e}")
        return None

    @classmethod
    async def _download_many(cls, urls: list[str]) -> list[bytes | None]:
        if not urls:
            return []
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return await asyncio.gather(*(cls._download_with_session(session, u) for u in urls))

    async def _fetch_hero_portraits(self, hero_keys: list[str]) -> dict[str, bytes]:
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
        urls = [portrait_map.get(k, "") for k in hero_keys]
        results = await self._download_many(urls)
        return {k: b for k, b in zip(hero_keys, results) if b}

    def _prepare_player_id(self, raw: str, from_binding: bool) -> str:
        """绑定存储已是规范化形式直接用；外部输入归一化+校验。"""
        if from_binding:
            return raw
        norm = _normalize_player_id(raw)
        try:
            _validate_player_id(norm)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return norm

    async def _send_summary_result(
        self, event: AstrMessageEvent, full: dict, player_id: str, platform: str,
        footer_note: str | None = None, extra_lines: list[str] | None = None,
    ):
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

        if self.enable_image_render and _RENDERER_AVAILABLE:
            try:
                urls = [avatar_url, namecard_url] + [r.get("rank_icon", "") for r in rank_rows]
                results = await self._download_many(urls)
                avatar_bytes, namecard_bytes = results[0], results[1]
                render_rows = [
                    {"role_text": r["role_text"], "rank_text": r["rank_text"], "rank_icon_bytes": b}
                    for r, b in zip(rank_rows, results[2:])
                ] or [{"role_text": "段位", "rank_text": "暂无竞技段位数据", "rank_icon_bytes": None}]
                portraits = await self._fetch_hero_portraits([k for k, _ in top_heroes])
                render_heroes = [(_get_hero_name_cn(k), _format_time_short(v), portraits.get(k)) for k, v in top_heroes]
                img_path = image_renderer.render_summary_card(
                    username=username, title=title, endorsement_level=endorsement_level,
                    rank_rows=render_rows, platform_label=_get_platform_display(shown_platform),
                    avatar_bytes=avatar_bytes, namecard_bytes=namecard_bytes,
                    top_heroes=render_heroes, footer_note=footer_note,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"摘要图片渲染失败，回退文字: {e}")
                logger.debug("堆栈:", exc_info=True)

        rank_lines = [f"   {r['role_text']}: {r['rank_text']}" for r in rank_rows] or ["   暂无竞技段位数据"]
        lines = [f"👤 {username}"]
        if title:
            lines.append(f"头衔: {title}")
        lines.append(f"赞赏等级: {endorsement_level}")
        lines.append(f"竞技段位 ({_get_platform_display(shown_platform)}):")
        lines.extend(rank_lines)
        if top_heroes:
            lines.append("常玩英雄: " + "、".join(f"{_get_hero_name_cn(k)}({_format_time_played(v)})" for k, v in top_heroes))
        if extra_lines:
            lines.extend(extra_lines)
        result_text = "\n".join(lines)
        if avatar_url:
            yield event.chain_result([Comp.Image.fromURL(avatar_url), Comp.Plain(result_text)])
        else:
            yield event.plain_result(result_text)

    @filter.command("owsummary")
    async def player_summary(self, event: AstrMessageEvent, player_id: str = ""):
        """查询玩家摘要信息。用法: /owsummary [玩家ID]"""
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result("你还没有绑定 Overwatch ID。\n用法: /owsummary <玩家ID>\n或 /owbind <玩家ID> [平台] 后直接查询")
                return
            player_id = bound_id
            from_binding = True
        platform = self._effective_platform(bound_platform)
        try:
            player_id = self._prepare_player_id(player_id, from_binding)
        except ValueError as e:
            yield event.plain_result(f"玩家 ID 非法: {e}")
            return
        try:
            async with OverFastAPIClient() as client:
                full = await client.get_player_full(player_id)
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "未找到" in err or "404" in err:
                yield event.plain_result(f"未找到玩家 `{player_id}`，请检查 ID。")
                return
            yield event.plain_result(self._api_error_reply(e, "获取玩家信息失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("获取玩家摘要错误堆栈:", exc_info=True)
            yield event.plain_result("获取玩家信息时出错，请稍后重试。")
            return
        async for res in self._send_summary_result(event, full, player_id, platform):
            yield res

    @filter.command("owstats")
    async def player_stats(self, event: AstrMessageEvent, player_id: str = "", gamemode: str = ""):
        """查询玩家统计概览。用法: /owstats [玩家ID] [快速|竞技]"""
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result("你还没有绑定 Overwatch ID。用法: /owstats <玩家ID> [快速|竞技]")
                return
            player_id = bound_id
            from_binding = True
        platform = self._effective_platform(bound_platform)
        try:
            player_id = self._prepare_player_id(player_id, from_binding)
        except ValueError as e:
            yield event.plain_result(f"玩家 ID 非法: {e}")
            return
        gamemode = _resolve_gamemode(gamemode or self.default_gamemode) or ""
        if gamemode not in ("quickplay", "competitive"):
            yield event.plain_result("游戏模式无效。可选: 快速(quickplay)、竞技(competitive)")
            return
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_stats_summary(player_id, gamemode=gamemode, platform=platform)
                full: dict = {}
                try:
                    full = await client.get_player_full(player_id)
                except Exception as fe:
                    logger.debug(f"完整数据获取失败: {fe}")
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "404" in err:
                yield event.plain_result(f"未找到玩家 `{player_id}` 或资料私密。")
                return
            yield event.plain_result(self._api_error_reply(e, "获取统计失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("获取统计错误堆栈:", exc_info=True)
            yield event.plain_result("获取统计信息时出错，请稍后重试。")
            return

        general = data.get("general", {}) if isinstance(data, dict) else {}
        if not general:
            yield event.plain_result(f"玩家 `{player_id}` | {GAMEMODE_MAPPING.get(gamemode, gamemode)}暂无统计数据。")
            return
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

        summary = full.get("summary") if isinstance(full.get("summary"), dict) else {}
        stats_full = full.get("stats") if isinstance(full.get("stats"), dict) else {}
        shown_platform, rank_data = _build_rank_data(summary, platform) if summary else (platform, [])
        comp_rank_rows = rank_data if gamemode == "competitive" else []
        heroes_stats = data.get("heroes", {}) if isinstance(data.get("heroes"), dict) else {}
        top_hero_rows = sorted(
            ((k, int(v.get("games_played") or 0)) for k, v in heroes_stats.items()
             if isinstance(v, dict) and (v.get("games_played") or 0) > 0),
            key=lambda kv: kv[1], reverse=True,
        )[:3]
        if not top_hero_rows and stats_full:
            top_hero_rows = [(k, 0) for k, _ in _extract_top_heroes(stats_full, platform)]
        gamemode_label = GAMEMODE_MAPPING.get(gamemode, gamemode)

        if self.enable_image_render and _RENDERER_AVAILABLE:
            try:
                render_rank_rows = []
                if comp_rank_rows:
                    icons = await self._download_many([r.get("rank_icon", "") for r in comp_rank_rows])
                    for r, b in zip(comp_rank_rows, icons):
                        render_rank_rows.append({"role_text": r["role_text"], "rank_text": r["rank_text"], "rank_icon_bytes": b})
                portraits = await self._fetch_hero_portraits([k for k, _ in top_hero_rows])
                render_heroes = [(_get_hero_name_cn(k), f"{_format_number(g)}场" if g else "常用英雄", portraits.get(k)) for k, g in top_hero_rows]
                stat_rows = [
                    ("场次", f"{_format_number(games_played)} ({_format_number(games_won)}胜/{_format_number(games_lost)}负)"),
                    ("胜率", f"{winrate}%"),
                    ("KDA", f"{kda:.2f}" if kda else "N/A"),
                    ("消灭", f"{_format_number(eliminations_avg)}/场" if eliminations_avg else "N/A"),
                    ("死亡", f"{_format_number(deaths_avg)}/场" if deaths_avg else "N/A"),
                    ("伤害", f"{_format_number(damage_avg)}/场" if damage_avg else "N/A"),
                    ("治疗", f"{_format_number(healing_avg)}/场" if healing_avg else "N/A"),
                    ("游戏时间", _format_time_played(time_played)),
                ]
                img_path = image_renderer.render_stats_card(
                    player_id=player_id, gamemode_label=gamemode_label,
                    platform_label=_get_platform_display(shown_platform),
                    stat_rows=stat_rows, rank_rows=render_rank_rows, top_heroes=render_heroes,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"统计图片渲染失败，回退文字: {e}")

        lines = [f"{player_id} | {gamemode_label} | {_get_platform_display(shown_platform)}", "━━━━━━━━━━━━"]
        if comp_rank_rows:
            lines.append(f"竞技段位 ({_get_platform_display(shown_platform)}):")
            lines.extend(f"   {r['role_text']}: {r['rank_text']}" for r in comp_rank_rows)
        lines.extend([
            f"场次: {_format_number(games_played)} ({_format_number(games_won)}胜/{_format_number(games_lost)}负)",
            f"胜率: {winrate}%",
            f"KDA: {kda:.2f}" if kda else "KDA: N/A",
            f"消灭: {_format_number(eliminations_avg)}/场" if eliminations_avg else "消灭: N/A",
            f"死亡: {_format_number(deaths_avg)}/场" if deaths_avg else "死亡: N/A",
            f"伤害: {_format_number(damage_avg)}/场" if damage_avg else "伤害: N/A",
            f"治疗: {_format_number(healing_avg)}/场" if healing_avg else "治疗: N/A",
            f"游戏时间: {_format_time_played(time_played)}",
        ])
        if top_hero_rows:
            lines.append("常玩英雄: " + "、".join(f"{_get_hero_name_cn(k)}({_format_number(g)}场)" if g else _get_hero_name_cn(k) for k, g in top_hero_rows))
        yield event.plain_result("\n".join(lines))

    @filter.command("owcareer")
    async def player_career(self, event: AstrMessageEvent, player_id: str = "", gamemode: str = "", hero: str = ""):
        """用法: /owcareer [玩家ID] <快速|竞技> [英雄]"""
        bound_platform: str | None = None
        from_binding = False
        if not player_id or not player_id.strip():
            bound_id, bound_platform = await self._get_binding(event)
            if not bound_id:
                yield event.plain_result("用法: /owcareer <玩家ID> <游戏模式> [英雄名]")
                return
            player_id = bound_id
            from_binding = True
        elif not gamemode or not gamemode.strip():
            resolved = _resolve_gamemode(player_id)
            if resolved in ("quickplay", "competitive"):
                bound_id, bound_platform = await self._get_binding(event)
                if bound_id:
                    gamemode = player_id
                    player_id = bound_id
                    from_binding = True
                else:
                    yield event.plain_result("你还没有绑定 ID。/owbind <玩家ID> 后可 /owcareer 竞技 源氏")
                    return
        platform = self._effective_platform(bound_platform)
        resolved_mode = _resolve_gamemode(gamemode)
        if not resolved_mode or resolved_mode not in ("quickplay", "competitive"):
            yield event.plain_result("请输入有效模式。用法: /owcareer <玩家ID> <快速|竞技> [英雄]")
            return
        try:
            player_id = self._prepare_player_id(player_id, from_binding)
        except ValueError as e:
            yield event.plain_result(f"玩家 ID 非法: {e}")
            return
        gamemode = resolved_mode
        hero_key = _resolve_hero_name(hero) if hero else None
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_player_career_stats(player_id, gamemode=gamemode, platform=platform, hero=hero_key)
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "404" in err:
                yield event.plain_result(f"未找到玩家 `{player_id}` 或资料私密。")
                return
            yield event.plain_result(self._api_error_reply(e, "获取生涯统计失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("生涯统计错误堆栈:", exc_info=True)
            yield event.plain_result("获取生涯统计时出错，请稍后重试。")
            return
        if not data or not isinstance(data, dict):
            yield event.plain_result(f"玩家 `{player_id}` 暂无生涯统计数据。")
            return
        hero_cards: list[tuple[str, str, list[tuple[str, str]]]] = []
        remaining = 0
        for hero_key_raw, categories in data.items():
            if not isinstance(categories, dict):
                continue
            hero_name = _get_hero_name_cn(hero_key_raw)
            rows: list[tuple[str, str]] = []
            combat = categories.get("combat", {})
            if combat:
                eliminations = combat.get("eliminations")
                deaths = combat.get("deaths")
                kd = ""
                if eliminations and deaths and int(deaths) > 0:
                    kd = f" (K/D: {float(eliminations) / float(deaths):.2f})"
                elif eliminations:
                    kd = " (K/D: ∞)"
                if eliminations is not None:
                    rows.append(("消灭", f"{_format_number(eliminations)}{kd}"))
                if deaths is not None:
                    rows.append(("死亡", _format_number(deaths)))
                if combat.get("damage_done") is not None:
                    rows.append(("伤害", _format_number(combat.get("damage_done"))))
                if combat.get("healing_done") is not None:
                    rows.append(("治疗", _format_number(combat.get("healing_done"))))
            game_stats = categories.get("game", {})
            if game_stats:
                gp, gw = game_stats.get("games_played"), game_stats.get("games_won")
                if gp is not None and gw is not None:
                    gl = (gp or 0) - (gw or 0)
                    wr = (gw / gp * 100) if gp > 0 else 0
                    rows.append(("场次", f"{_format_number(gp)} ({_format_number(gw)}胜/{_format_number(gl)}负, {wr:.1f}%)"))
                if game_stats.get("time_played"):
                    rows.append(("时间", _format_time_played(game_stats.get("time_played"))))
            hero_cards.append((hero_key_raw, hero_name, rows))
            if len(hero_cards) >= 8:
                remaining = max(len(data) - 8, 0)
                break
        gamemode_label = GAMEMODE_MAPPING.get(gamemode, gamemode)
        hero_filter_name = _get_hero_name_cn(hero_key) if hero_key else None
        if self.enable_image_render and _RENDERER_AVAILABLE and hero_cards:
            try:
                portraits = await self._fetch_hero_portraits([k for k, _, _ in hero_cards])
                render_heroes = [(name, rows, portraits.get(key)) for key, name, rows in hero_cards]
                img_path = image_renderer.render_career_card(
                    player_id=player_id, gamemode_label=gamemode_label,
                    platform_label=_get_platform_display(platform),
                    hero_filter=hero_filter_name, heroes=render_heroes, remaining=remaining,
                )
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"生涯图片渲染失败，回退文字: {e}")
        hero_filter = f" | 英雄: {hero_filter_name}" if hero_filter_name else ""
        lines = [f"{player_id} | {gamemode_label} | {_get_platform_display(platform)}{hero_filter}", "━━━━━━━━━━━━"]
        for _, hero_name, rows in hero_cards:
            lines.append(f"\n{hero_name}")
            lines.extend(f"   {label}: {value}" for label, value in rows)
        if remaining > 0:
            lines.append(f"\n... 还有 {remaining} 个英雄未显示")
        if not hero_cards:
            lines.append("暂无生涯统计数据。")
        yield event.plain_result("\n".join(lines))

    @filter.command("owhero")
    async def hero_info(self, event: AstrMessageEvent, hero_name: str = ""):
        """用法: /owhero <英雄名>"""
        if not hero_name or not hero_name.strip():
            yield event.plain_result("请输入英雄名称。用法: /owhero <英雄名>")
            return
        hero_key = _resolve_hero_name(hero_name)
        hero_stat: dict | None = None
        try:
            async with OverFastAPIClient() as client:
                data = await client.get_hero_info(hero_key)
                try:
                    all_stats = await client.get_heroes_stats(
                        platform=self.default_platform, gamemode=self.default_gamemode, region=self.default_region)
                    for item in all_stats or []:
                        if isinstance(item, dict) and item.get("hero") == hero_key:
                            hero_stat = item
                            break
                except Exception as se:
                    logger.debug(f"英雄胜率获取失败: {se}")
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "404" in err:
                yield event.plain_result(f"未找到英雄 `{hero_key}`。")
                return
            yield event.plain_result(self._api_error_reply(e, "获取英雄信息失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("英雄信息错误堆栈:", exc_info=True)
            yield event.plain_result("获取英雄信息时出错，请稍后重试。")
            return
        name = data.get("name", hero_key)
        description = data.get("description", "")
        role = data.get("role", "")
        hp = data.get("hitpoints", {}) if isinstance(data.get("hitpoints"), dict) else {}
        portrait = data.get("portrait", "")
        abilities = data.get("abilities", [])
        story_summary = data.get("story", {}).get("summary", "") if isinstance(data.get("story"), dict) else ""
        lines = [f"{name}", f"角色: {_get_role_display(role) if role else '未知'}",
                 f"生命: {hp.get('health', 0)}{' | 护甲: ' + str(hp.get('armor')) if hp.get('armor') else ''}{' | 护盾: ' + str(hp.get('shields')) if hp.get('shields') else ''}"]
        if hero_stat:
            lines.append(f"全服({_get_region_display(self.default_region)}|{GAMEMODE_MAPPING.get(self.default_gamemode, self.default_gamemode)}): 胜率 {(hero_stat.get('winrate') or 0):.1f}% | 选取率 {(hero_stat.get('pickrate') or 0):.1f}%")
        lines.append("━━━━━━━━━━━━")
        if abilities:
            lines.append("技能:")
            for ability in abilities[:8]:
                if isinstance(ability, dict):
                    desc = ability.get("description", "")
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    lines.append(f"   • {ability.get('name', '')}: {desc}")
        if story_summary:
            s = story_summary[:197] + "..." if len(story_summary) > 200 else story_summary
            lines += ["", "背景故事:", f"   {s}"]
        result_text = "\n".join(lines)
        if portrait:
            yield event.chain_result([Comp.Image.fromURL(portrait), Comp.Plain(result_text)])
        else:
            yield event.plain_result(result_text)

    @filter.command("owherostats")
    async def heroes_stats(self, event: AstrMessageEvent, role: str = "", region: str = ""):
        """用法: /owherostats [坦克|输出|支援] [亚服|美服|欧服]"""
        role_filter: str | None = None
        resolved_region: str | None = None
        for arg in (role, region):
            arg = (arg or "").strip()
            if not arg:
                continue
            lowered = arg.lower()
            if lowered in ROLE_CN_TO_EN or arg in ROLE_CN_TO_EN:
                if role_filter is not None:
                    yield event.plain_result("角色参数重复。可选: 坦克、输出、支援")
                    return
                role_filter = ROLE_CN_TO_EN.get(lowered) or ROLE_CN_TO_EN.get(arg)
            elif _resolve_region(arg):
                if resolved_region is not None:
                    yield event.plain_result("地区参数重复。可选: 亚服、美服、欧服")
                    return
                resolved_region = _resolve_region(arg)
            else:
                yield event.plain_result(f"无法识别 `{arg}`。用法: /owherostats [角色] [地区]")
                return
        region_v = resolved_region or self.default_region
        try:
            async with OverFastAPIClient() as client:
                stats = await client.get_heroes_stats(
                    platform=self.default_platform, gamemode=self.default_gamemode,
                    region=region_v, role=role_filter, order_by="winrate:desc")
        except ValueError as e:
            yield event.plain_result(self._api_error_reply(e, "获取英雄统计失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("英雄统计错误堆栈:", exc_info=True)
            yield event.plain_result("获取英雄统计时出错，请稍后重试。")
            return
        if not stats or not isinstance(stats, list):
            yield event.plain_result("暂无英雄统计数据。")
            return
        role_cn = ROLE_MAPPING.get(role_filter, (role_filter,))[0] if role_filter else ""
        title = "英雄胜率排行"
        subtitle = f"{_get_region_display(region_v)}{' | ' + role_cn if role_cn else ''} | {GAMEMODE_MAPPING.get(self.default_gamemode, self.default_gamemode)} | {_get_platform_display(self.default_platform)}"
        rows: list[tuple[str, str]] = []
        text_lines = [f"{title} | {subtitle}", "━━━━━━━━━━━━"]
        for idx, item in enumerate(stats, 1):
            if not isinstance(item, dict):
                continue
            hn = _get_hero_name_cn(item.get("hero", ""))
            wr = item.get("winrate", 0) or 0
            pr = item.get("pickrate", 0) or 0
            rows.append((f"{idx:>2}. {hn}", f"胜率 {wr:.1f}% | 选取率 {pr:.1f}%"))
            text_lines.append(f"{idx:>2}. {hn:<6} 胜率 {wr:.1f}% | 选取率 {pr:.1f}%")
        text_lines += ["", "可加参数筛选: /owherostats 输出 欧服"]
        if self.enable_image_render and _RENDERER_AVAILABLE:
            try:
                img_path = image_renderer.render_herostats_card(title, subtitle, rows, "可加参数筛选: /owherostats 输出 欧服")
                yield event.chain_result([Comp.Image.fromFileSystem(img_path)])
                return
            except Exception as e:
                logger.warning(f"榜单图片渲染失败，回退文字: {e}")
        yield event.plain_result("\n".join(text_lines))

    @filter.command("owbind")
    async def bind_id(self, event: AstrMessageEvent, player_id: str = "", platform: str = ""):
        """用法: /owbind <玩家ID> [pc|主机]"""
        if not player_id or not player_id.strip():
            yield event.plain_result(f"请输入玩家 ID。用法: /owbind <玩家ID> [平台]\n最多绑定 {self.max_binds_per_user} 个，用 /owbinds 查看")
            return
        if platform and platform.strip():
            rp = _resolve_platform(platform)
            if not rp:
                yield event.plain_result("平台无效。可选: pc(电脑端)、console(主机端)")
                return
            platform_v = rp
        else:
            platform_v = self.default_platform
        try:
            player_id = self._prepare_player_id(player_id, False)
        except ValueError as e:
            yield event.plain_result(f"玩家 ID 非法: {e}")
            return
        user_name = event.get_sender_name()
        current = await self._load_bindings(event)
        if not any(a["player_id"].lower() == player_id.lower() for a in current["accounts"]) and len(current["accounts"]) >= self.max_binds_per_user:
            yield event.plain_result(f"{user_name} 最多绑定 {self.max_binds_per_user} 个账号。/owunbind 解绑后再试。")
            return
        try:
            async with OverFastAPIClient() as client:
                await client.get_player_summary(player_id)
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "404" in err:
                yield event.plain_result(f"未找到玩家 `{player_id}`，请检查 ID。")
                return
        except Exception:
            pass
        result, data = await self._add_binding(event, player_id, platform_v)
        if result == "limit":
            yield event.plain_result(f"最多绑定 {self.max_binds_per_user} 个账号。")
        elif result in ("added", "updated"):
            action = "绑定" if result == "added" else "更新绑定"
            count = len(data["accounts"]) if data else 1
            yield event.plain_result(
                f"{user_name} 已{action}: `{player_id}`\n平台: {_get_platform_display(platform_v)}（已设默认）\n"
                f"已绑定 {count}/{self.max_binds_per_user}\n/owme 快捷查询，/owbinds 查看列表")
        else:
            yield event.plain_result("绑定失败，请稍后重试。")

    @filter.command("owunbind")
    async def unbind_id(self, event: AstrMessageEvent, player_id: str = ""):
        user_name = event.get_sender_name()
        target = _normalize_player_id(player_id) if player_id and player_id.strip() else None
        result, removed_id = await self._remove_binding(event, target)
        if result == "empty":
            yield event.plain_result(f"{user_name} 还没有绑定任何 ID。/owbind <玩家ID> 绑定。")
        elif result == "not_found":
            yield event.plain_result(f"你没有绑定 `{target}`。/owbinds 查看列表。")
        elif result == "removed":
            remaining = await self._load_bindings(event)
            tip = f"剩余 {len(remaining['accounts'])} 个，默认 `{remaining['default']}`" if remaining["accounts"] else "需重新 /owbind 绑定"
            yield event.plain_result(f"已解绑: `{removed_id}`\n{tip}")
        else:
            yield event.plain_result("解绑失败，请稍后重试。")

    @filter.command("owbinds")
    async def list_bindings(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        data = await self._load_bindings(event)
        accounts = data["accounts"]
        if not accounts:
            yield event.plain_result(f"{user_name} 还没有绑定 ID。/owbind <玩家ID> 绑定。")
            return
        default = data.get("default")
        lines = [f"{user_name} 的绑定列表 ({len(accounts)}/{self.max_binds_per_user}):", "━━━━━━━━━━━━"]
        for idx, acc in enumerate(accounts, 1):
            mark = " 默认" if acc["player_id"] == default else ""
            lines.append(f"{idx}. `{acc['player_id']}` | {_get_platform_display(acc.get('platform', self.default_platform))}{mark}")
        lines += ["", "/owdefault <玩家ID> 切换默认，/owunbind [玩家ID] 解绑"]
        yield event.plain_result("\n".join(lines))

    @filter.command("owdefault")
    async def set_default_binding(self, event: AstrMessageEvent, player_id: str = ""):
        user_name = event.get_sender_name()
        if not player_id or not player_id.strip():
            yield event.plain_result("用法: /owdefault <玩家ID>")
            return
        target = _normalize_player_id(player_id)
        data = await self._load_bindings(event)
        if not data["accounts"]:
            yield event.plain_result(f"{user_name} 还没有绑定 ID。")
            return
        matched = next((a for a in data["accounts"] if a["player_id"].lower() == target.lower()), None)
        if not matched:
            yield event.plain_result(f"你没有绑定 `{target}`。/owbinds 查看列表。")
            return
        data["default"] = matched["player_id"]
        if await self._save_bindings(event, data):
            yield event.plain_result(f"已设默认: `{matched['player_id']}`")
        else:
            yield event.plain_result("设置失败，请稍后重试。")

    @filter.command("owme")
    async def quick_summary(self, event: AstrMessageEvent):
        bound_id, bound_platform = await self._get_binding(event)
        user_name = event.get_sender_name()
        if not bound_id:
            yield event.plain_result(f"{user_name} 还没有绑定 ID。/owbind <玩家ID> 绑定。")
            return
        platform = self._effective_platform(bound_platform)
        try:
            async with OverFastAPIClient() as client:
                full = await client.get_player_full(bound_id)
        except ValueError as e:
            err = str(e).lower()
            if "not found" in err or "未找到" in err or "404" in err:
                yield event.plain_result(f"未找到绑定玩家 `{bound_id}`，可能改名/私密，请重绑。")
                return
            yield event.plain_result(self._api_error_reply(e, "获取玩家信息失败，请稍后重试。"))
            return
        except Exception:
            logger.debug("owme 错误堆栈:", exc_info=True)
            yield event.plain_result("获取玩家信息时出错，请稍后重试。")
            return
        async for res in self._send_summary_result(
            event, full, bound_id, platform,
            footer_note=f"快捷查询 | {bound_id} | {_get_platform_display(platform)}",
            extra_lines=["", "/owstats [模式] 统计，/owcareer <模式> [英雄] 生涯，/owunbind 解绑"],
        ):
            yield res
