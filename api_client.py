"""
提供对 OverFast API (https://overfast-api.tekrop.fr) 的所有异步 HTTP 调用封装，
用于查询 Overwatch 玩家战绩、英雄信息等数据。
"""

import logging
from typing import Any

import aiohttp

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
        timeout: float = 30.0,
    ) -> None:
        """初始化 OverFast API 客户端。

        Args:
            base_url: API 基础 URL，默认使用官方实例。
            timeout: 请求超时时间（秒），默认 30 秒。
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

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict | list:
        """发送 GET 请求到 OverFast API。

        Args:
            endpoint: API 端点路径（不含 base_url），如 `/players`。
            params: 查询参数字典，值为 None 的键会被自动过滤。

        Returns:
            解析后的 JSON 响应数据（dict 或 list）。

        Raises:
            OverFastAPIError: 当返回 HTTP 4xx/5xx 错误时，包含状态码与服务端错误详情。
            aiohttp.ClientError: 网络连接错误。
            asyncio.TimeoutError: 请求超时。
        """
        # 过滤值为 None 的参数
        filtered_params = {k: v for k, v in (params or {}).items() if v is not None}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"OverFast API 请求: GET {url} params={filtered_params}")

        async with self.session.get(url, params=filtered_params) as response:
            # 处理 HTTP 错误
            if response.status >= 400:
                error_text = ""
                retry_after: int | None = None
                try:
                    error_json = await response.json()
                    if isinstance(error_json, dict):
                        # 标准错误结构: {"error": "...", "retry_after": N}
                        error_text = str(error_json.get("error", ""))
                        ra = error_json.get("retry_after")
                        if isinstance(ra, (int, float)):
                            retry_after = int(ra)
                        # FastAPI 参数校验错误结构: {"detail": [...]}
                        if not error_text and "detail" in error_json:
                            error_text = str(error_json["detail"])
                        if not error_text:
                            error_text = str(error_json)
                    else:
                        error_text = str(error_json)
                except Exception:
                    error_text = await response.text() or f"HTTP {response.status}"

                # 完整错误暴露在控制台 debug 日志中，便于排查
                logger.debug(
                    f"OverFast API 错误: GET {url} params={filtered_params} "
                    f"-> HTTP {response.status}, error={error_text}, retry_after={retry_after}"
                )

                if response.status == 404:
                    raise OverFastAPIError(
                        f"未找到请求的资源: {error_text}",
                        status_code=404, detail=error_text, retry_after=retry_after,
                    )
                elif response.status == 429:
                    raise OverFastAPIError(
                        f"请求过于频繁，请稍后重试: {error_text}",
                        status_code=429, detail=error_text, retry_after=retry_after,
                    )
                elif response.status == 503:
                    raise OverFastAPIError(
                        f"服务暂时不可用（可能被限流）: {error_text}",
                        status_code=503, detail=error_text, retry_after=retry_after,
                    )
                else:
                    raise OverFastAPIError(
                        f"API 错误 (HTTP {response.status}): {error_text}",
                        status_code=response.status, detail=error_text, retry_after=retry_after,
                    )

            # 解析 JSON 响应
            try:
                data = await response.json()
            except aiohttp.ContentTypeError as e:
                raw_text = await response.text()
                raise ValueError(
                    f"无法解析 API 响应为 JSON: {e}. 原始响应: {raw_text[:500]}"
                ) from e

            logger.debug(f"OverFast API 响应: {type(data).__name__}")
            return data

    async def search_players(
        self,
        name: str,
        order_by: str = "name:asc",
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """搜索玩家。

        Args:
            name: 玩家昵称或 BattleTag（# 替换为 -）。
            order_by: 排序方式，格式为 `field:asc|desc`，默认 `name:asc`。
            offset: 结果偏移量，用于分页，默认 0。
            limit: 每页结果数量，默认 20。

        Returns:
            搜索结果字典，包含 `total` 和 `results` 字段。

        Raises:
            ValueError: API 返回错误。
        """
        return await self._request(  # type: ignore[return-value]
            "/players",
            params={
                "name": name,
                "order_by": order_by,
                "offset": offset,
                "limit": limit,
            },
        )

    async def get_player_summary(self, player_id: str) -> dict:
        """获取玩家摘要信息。

        Args:
            player_id: 玩家 ID，将 BattleTag 中的 `#` 替换为 `-`。

        Returns:
            玩家摘要字典，包含 username, avatar, namecard, title,
            endorsement, competitive 等字段。

        Raises:
            ValueError: 玩家不存在或资料私密。
        """
        return await self._request(f"/players/{player_id}/summary")  # type: ignore[return-value]

    async def get_player_full(self, player_id: str) -> dict:
        """获取玩家完整数据（摘要 + 统计数据）。

        响应包含 summary（头像、名片、竞技段位等）与 stats
        （各平台/模式下的英雄对比数据，可提取常玩英雄）。

        Args:
            player_id: 玩家 ID，将 BattleTag 中的 `#` 替换为 `-`。

        Returns:
            玩家完整数据字典，包含 summary 和 stats 字段。

        Raises:
            ValueError: 玩家不存在或资料私密。
        """
        return await self._request(f"/players/{player_id}")  # type: ignore[return-value]

    async def get_player_stats_summary(
        self,
        player_id: str,
        gamemode: str | None = None,
        platform: str | None = None,
    ) -> dict:
        """获取玩家统计摘要。

        Args:
            player_id: 玩家 ID。
            gamemode: 游戏模式，`quickplay` 或 `competitive`，默认 None。
                插件层面支持中文输入（如"快速"、"竞技"），但传入本方法的应为英文。
            platform: 平台，`pc`, `console` 或 `all`，默认 None。

        Returns:
            玩家统计摘要字典，包含 general 和 heroes 统计。

        Raises:
            ValueError: 玩家不存在或资料私密。
        """
        return await self._request(  # type: ignore[return-value]
            f"/players/{player_id}/stats/summary",
            params={"gamemode": gamemode, "platform": platform},
        )

    async def get_player_career_stats(
        self,
        player_id: str,
        gamemode: str,
        platform: str | None = None,
        hero: str | None = None,
    ) -> dict:
        """获取玩家生涯统计（按英雄分类的详细数据）。

        Args:
            player_id: 玩家 ID。
            gamemode: 游戏模式，`quickplay` 或 `competitive`（必填）。
                插件层面支持中文输入（如"快速"、"竞技"），但传入本方法的应为英文。
            platform: 平台，`pc`, `console` 或 `all`，默认 None。
            hero: 英雄英文 key（如 `genji`, `ana`），默认 None 返回所有英雄。
                插件层面支持中文英雄名，但传入本方法的应为英文 key。

        Returns:
            玩家生涯统计字典，按英雄 key 分组。

        Raises:
            ValueError: 玩家不存在、资料私密或参数错误。
        """
        return await self._request(  # type: ignore[return-value]
            f"/players/{player_id}/stats/career",
            params={"gamemode": gamemode, "platform": platform, "hero": hero},
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

        Args:
            platform: 平台，`pc` 或 `console`（必填）。
            gamemode: 游戏模式，`quickplay` 或 `competitive`（必填）。
            region: 地区服务器，`europe`, `americas` 或 `asia`（必填）。
            role: 按角色筛选，`tank`, `damage`, `support`，默认 None。
            map_key: 按地图筛选（如 `kings-row`），默认 None。
            competitive_division: 按竞技段位筛选（如 `diamond`），默认 None。
            order_by: 排序方式，格式为 `field:asc|desc`，
                field 可选 hero, pickrate, winrate，默认 `hero:asc`。

        Returns:
            英雄统计列表，每项包含 hero, pickrate, winrate。

        Raises:
            OverFastAPIError: 参数错误或 API 异常。
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
        )

    async def get_hero_info(self, hero_key: str) -> dict:
        """获取英雄详细信息。

        Args:
            hero_key: 英雄 key，如 `genji`, `ana`, `reinhardt`。

        Returns:
            英雄详情字典，包含 name, description, role, abilities 等。

        Raises:
            ValueError: 英雄不存在。
        """
        return await self._request(f"/heroes/{hero_key}")  # type: ignore[return-value]

    async def list_heroes(
        self,
        role: str | None = None,
        gamemode: str | None = None,
    ) -> list:
        """获取英雄列表。

        Args:
            role: 按角色筛选，`tank`, `damage`, `support`，默认 None。
            gamemode: 按游戏模式筛选，默认 None。

        Returns:
            英雄列表，每项包含 key, name, role, portrait 等。
        """
        return await self._request(  # type: ignore[return-value]
            "/heroes",
            params={"role": role, "gamemode": gamemode},
        )

    async def list_roles(self) -> list:
        """获取所有角色类型。

        Returns:
            角色列表，每项包含 key, name, icon, description。
        """
        return await self._request("/roles")  # type: ignore[return-value]

    async def list_gamemodes(self) -> list:
        """获取所有游戏模式。

        Returns:
            游戏模式列表，每项包含 key, name, description, icon。
        """
        return await self._request("/gamemodes")  # type: ignore[return-value]

    async def list_maps(self, gamemode: str | None = None) -> list:
        """获取所有地图。

        Args:
            gamemode: 按游戏模式筛选，默认 None。

        Returns:
            地图列表，每项包含 name, gamemodes, location, country_code。
        """
        return await self._request(  # type: ignore[return-value]
            "/maps",
            params={"gamemode": gamemode},
        )
