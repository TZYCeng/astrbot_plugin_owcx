"""
提供对 OverFast API (https://overfast-api.tekrop.fr) 的所有异步 HTTP 调用封装，
用于查询 Overwatch 玩家战绩、英雄信息等数据。
"""

import asyncio
import time
from typing import Any
from urllib.parse import quote

import aiohttp

try:  # 统一使用 AstrBot 日志；独立单测时回退标准 logging
    from astrbot.api import logger
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger(__name__)


class OverFastAPIError(ValueError):
    """OverFast API 请求错误。

    携带 HTTP 状态码、服务端返回的错误详情以及重试等待时间，
    继承 ValueError 以兼容既有的错误捕获逻辑。

    Attributes:
        status_code: HTTP 状态码。
        detail: 服务端返回的原始错误文本。
        retry_after: 服务端建议的重试等待秒数（可能为 None）。
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        detail: str = "",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.retry_after = retry_after


# 进程级 GET 缓存：key -> (expire_ts, data)，降低限流风险
_CACHE: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    item = _CACHE.get(key)
    if not item:
        return None
    expire, data = item
    if expire < time.monotonic():
        _CACHE.pop(key, None)
        return None
    return data


def _cache_set(key: str, data: Any, ttl: float) -> None:
    if ttl <= 0:
        return
    # 简单容量保护
    if len(_CACHE) > 512:
        _CACHE.clear()
    _CACHE[key] = (time.monotonic() + ttl, data)


def clear_cache() -> None:
    _CACHE.clear()


class OverFastAPIClient:
    """OverFast API 异步客户端。

    使用示例:
        async with OverFastAPIClient() as client:
            result = await client.search_players("TeKrop")
            summary = await client.get_player_summary("TeKrop-2217")
    """

    def __init__(
        self,
        base_url: str = "https://overfast-api.tekrop.fr",
        timeout: float = 15.0,
    ) -> None:
        """初始化 OverFast API 客户端。

        Args:
            base_url: API 基础 URL，官方实例或自建实例（如 Docker 自部署）。
                插件侧通过 `api_base_url` 配置项传入。
            timeout: 请求超时时间（秒），默认 15 秒（聊天场景不宜过长）。
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """获取当前 HTTP session。

        Returns:
            aiohttp.ClientSession 实例。

        Raises:
            RuntimeError: 如果 session 未初始化（未使用 async with）。
        """
        if self._session is None or self._session.closed:
            raise RuntimeError(
                "HTTP session 未初始化。请使用 `async with OverFastAPIClient() as client:`"
            )
        return self._session

    async def __aenter__(self) -> "OverFastAPIClient":
        """异步上下文管理器入口，创建 HTTP session。"""
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口，确保 session 被关闭。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @staticmethod
    def _quote_segment(seg: str) -> str:
        return quote(seg, safe="-")

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        *,
        use_cache: bool = False,
        cache_ttl: float = 300.0,
        max_retries: int = 2,
    ) -> dict | list:
        """发送 GET 请求到 OverFast API（含缓存/限流重试）。

        Args:
            endpoint: API 端点路径（不含 base_url），如 `/players`。
            params: 查询参数字典，值为 None 的键会被自动过滤。
            use_cache: 是否启用进程级 GET 缓存。
            cache_ttl: 缓存秒数。
            max_retries: 429/503 时的最大重试次数。

        Raises:
            OverFastAPIError: 当返回 HTTP 4xx/5xx 错误时。
        """
        filtered_params = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"OverFast API 请求: GET {url} params={filtered_params}")

        cache_key = ""
        if use_cache:
            sorted_items = sorted((k, str(v)) for k, v in filtered_params.items())
            cache_key = f"GET {url} {sorted_items}"
            cached = _cache_get(cache_key)
            if cached is not None:
                logger.debug(f"OverFast API 缓存命中: {url}")
                return cached

        last_err: OverFastAPIError | None = None
        for attempt in range(max_retries + 1):
            async with self.session.get(url, params=filtered_params) as response:
                if response.status >= 400:
                    error_text = ""
                    retry_after: int | None = None
                    try:
                        error_json = await response.json()
                        if isinstance(error_json, dict):
                            error_text = str(error_json.get("error", ""))
                            ra = error_json.get("retry_after")
                            if isinstance(ra, (int, float)):
                                retry_after = int(ra)
                            if not error_text and "detail" in error_json:
                                error_text = str(error_json["detail"])
                            if not error_text:
                                error_text = str(error_json)
                        else:
                            error_text = str(error_json)
                    except Exception:
                        error_text = await response.text() or f"HTTP {response.status}"

                    logger.debug(
                        f"OverFast API 错误: GET {url} params={filtered_params} "
                        f"-> HTTP {response.status}, error={error_text}, retry_after={retry_after}"
                    )

                    if response.status == 404:
                        raise OverFastAPIError(
                            f"未找到请求的资源: {error_text}",
                            status_code=404, detail=error_text, retry_after=retry_after,
                        )
                    if response.status in (429, 503) and attempt < max_retries:
                        wait = retry_after if retry_after else (2 ** attempt)
                        wait = min(max(wait, 1), 10)
                        logger.debug(f"OverFast API 限流，{wait}s 后重试 ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait)
                        last_err = OverFastAPIError(
                            f"请求过于频繁: {error_text}",
                            status_code=response.status, detail=error_text,
                            retry_after=retry_after,
                        )
                        continue
                    if response.status == 429:
                        raise OverFastAPIError(
                            f"请求过于频繁，请稍后重试: {error_text}",
                            status_code=429, detail=error_text, retry_after=retry_after,
                        )
                    if response.status == 503:
                        raise OverFastAPIError(
                            f"服务暂时不可用（可能被限流）: {error_text}",
                            status_code=503, detail=error_text, retry_after=retry_after,
                        )
                    raise OverFastAPIError(
                        f"API 错误 (HTTP {response.status}): {error_text}",
                        status_code=response.status, detail=error_text, retry_after=retry_after,
                    )

                try:
                    data = await response.json()
                except aiohttp.ContentTypeError as e:
                    raw_text = await response.text()
                    raise ValueError(
                        f"无法解析 API 响应为 JSON: {e}. 原始响应: {raw_text[:500]}"
                    ) from e

                logger.debug(f"OverFast API 响应: {type(data).__name__}")
                if use_cache:
                    _cache_set(cache_key, data, cache_ttl)
                return data

        assert last_err is not None
        raise last_err

    async def search_players(
        self,
        name: str,
        order_by: str = "name:asc",
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """搜索玩家。"""
        return await self._request(  # type: ignore[return-value]
            "/players",
            params={"name": name, "order_by": order_by, "offset": offset, "limit": limit},
            use_cache=True,
            cache_ttl=120,
        )

    async def get_player_summary(self, player_id: str) -> dict:
        """获取玩家摘要信息。"""
        pid = self._quote_segment(player_id)
        return await self._request(f"/players/{pid}/summary", use_cache=True, cache_ttl=120)  # type: ignore[return-value]

    async def get_player_full(self, player_id: str) -> dict:
        """获取玩家完整数据（摘要 + 统计数据）。"""
        pid = self._quote_segment(player_id)
        return await self._request(f"/players/{pid}", use_cache=True, cache_ttl=120)  # type: ignore[return-value]

    async def get_player_stats_summary(
        self,
        player_id: str,
        gamemode: str | None = None,
        platform: str | None = None,
    ) -> dict:
        """获取玩家统计摘要。"""
        pid = self._quote_segment(player_id)
        return await self._request(  # type: ignore[return-value]
            f"/players/{pid}/stats/summary",
            params={"gamemode": gamemode, "platform": platform},
            use_cache=True,
            cache_ttl=120,
        )

    async def get_player_career_stats(
        self,
        player_id: str,
        gamemode: str,
        platform: str | None = None,
        hero: str | None = None,
    ) -> dict:
        """获取玩家生涯统计（按英雄分类的详细数据）。"""
        pid = self._quote_segment(player_id)
        return await self._request(  # type: ignore[return-value]
            f"/players/{pid}/stats/career",
            params={"gamemode": gamemode, "platform": platform, "hero": hero},
            use_cache=True,
            cache_ttl=120,
        )

    async def get_heroes_stats(
        self,
        platform: str,
        gamemode: str,
        region: str,
        role: str | None = None,
        map_key: str | None = None,
        competitive_division: str | None = None,
        order_by: str = "hero:asc",
    ) -> list:
        """获取英雄统计数据（全服英雄选取率/胜率排行榜）。

        competitive_division 可选 bronze/silver/gold/platinum/emerald/diamond/master/grandmaster
        （API 4.13 段位；ultimate 为玩家段位新值，榜单筛选暂不支持）。
        """
        return await self._request(  # type: ignore[return-value]
            "/heroes/stats",
            params={
                "platform": platform,
                "gamemode": gamemode,
                "region": region,
                "role": role,
                "map": map_key,
                "competitive_division": competitive_division,
                "order_by": order_by,
            },
            use_cache=True,
            cache_ttl=600,
        )

    async def get_hero_info(self, hero_key: str) -> dict:
        """获取英雄详细信息。"""
        hk = self._quote_segment(hero_key.strip().lower())
        return await self._request(f"/heroes/{hk}", use_cache=True, cache_ttl=3600)  # type: ignore[return-value]

    async def list_heroes(
        self,
        role: str | None = None,
        gamemode: str | None = None,
    ) -> list:
        """获取英雄列表。"""
        return await self._request(  # type: ignore[return-value]
            "/heroes",
            params={"role": role, "gamemode": gamemode},
            use_cache=True,
            cache_ttl=3600,
        )

    async def list_roles(self) -> list:
        """获取所有角色类型。"""
        return await self._request("/roles", use_cache=True, cache_ttl=3600)  # type: ignore[return-value]

    async def list_gamemodes(self) -> list:
        """获取所有游戏模式。"""
        return await self._request("/gamemodes", use_cache=True, cache_ttl=3600)  # type: ignore[return-value]

    async def list_maps(self, gamemode: str | None = None) -> list:
        """获取所有地图。"""
        return await self._request(  # type: ignore[return-value]
            "/maps",
            params={"gamemode": gamemode},
            use_cache=True,
            cache_ttl=3600,
        )
