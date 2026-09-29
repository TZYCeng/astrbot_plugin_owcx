"""KV 多账号绑定存储，含旧版自动迁移。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

_BIND_KEY_PREFIX = "bind_"


def bind_key(qq_id: str) -> str:
    return f"{_BIND_KEY_PREFIX}{qq_id}"


def normalize_loaded(raw, default_platform: str) -> dict | None:
    """将 KV 原始值归一化为新版结构；无法识别返回 None；需迁移的旧版返回新结构。"""
    empty: dict = {"accounts": [], "default": None}
    if raw is None or raw == "":
        return empty
    if isinstance(raw, dict) and "accounts" in raw:
        accounts = []
        for item in raw.get("accounts") or []:
            if not isinstance(item, dict):
                continue
            pid = item.get("player_id")
            platform = item.get("platform")
            if platform not in ("pc", "console"):
                platform = default_platform
            if pid:
                accounts.append({"player_id": pid, "platform": platform})
        default = raw.get("default")
        if not any(a["player_id"] == default for a in accounts):
            default = accounts[0]["player_id"] if accounts else None
        return {"accounts": accounts, "default": default}
    if isinstance(raw, dict) and raw.get("player_id"):
        platform = raw.get("platform")
        if platform not in ("pc", "console"):
            platform = default_platform
        return {
            "accounts": [{"player_id": raw["player_id"], "platform": platform}],
            "default": raw["player_id"],
        }
    if isinstance(raw, str) and raw:
        return {
            "accounts": [{"player_id": raw, "platform": default_platform}],
            "default": raw,
        }
    return None


class BindingStore:
    """依赖 Star 的 get/put/delete_kv_data，需在插件类中混入使用。"""

    _default_platform_fallback = "pc"

    async def _load_bindings(self, event: "AstrMessageEvent") -> dict:
        from astrbot.api import logger as _logger

        empty: dict = {"accounts": [], "default": None}
        qq_id = event.get_sender_id()
        if not qq_id:
            return empty
        try:
            raw = await self.get_kv_data(bind_key(qq_id), None)  # type: ignore[attr-defined]
        except Exception as e:
            _logger.debug(f"读取绑定信息失败: {e}")
            return empty

        default_platform = getattr(self, "default_platform", self._default_platform_fallback)
        result = normalize_loaded(raw, default_platform)
        if result is None:
            return empty
        # 旧版结构需回写迁移
        if not (isinstance(raw, dict) and "accounts" in raw):
            try:
                await self.put_kv_data(bind_key(qq_id), result)  # type: ignore[attr-defined]
            except Exception as e:
                _logger.debug(f"迁移绑定数据失败: {e}")
        return result

    async def _save_bindings(self, event: "AstrMessageEvent", data: dict) -> bool:
        from astrbot.api import logger as _logger

        qq_id = event.get_sender_id()
        if not qq_id:
            return False
        try:
            await self.put_kv_data(bind_key(qq_id), data)  # type: ignore[attr-defined]
            return True
        except Exception as e:
            _logger.error(f"保存绑定信息失败: {e}")
            return False

    async def _get_binding(self, event: "AstrMessageEvent") -> tuple[str | None, str | None]:
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

    async def _add_binding(
        self, event: "AstrMessageEvent", player_id: str, platform: str = "pc"
    ) -> tuple[str, dict | None]:
        if platform not in ("pc", "console"):
            platform = getattr(self, "default_platform", "pc")
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
        self, event: "AstrMessageEvent", player_id: str | None = None
    ) -> tuple[str, str | None]:
        from astrbot.api import logger as _logger

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
                await self.delete_kv_data(bind_key(event.get_sender_id()))  # type: ignore[attr-defined]
            except Exception as e:
                _logger.error(f"删除绑定信息失败: {e}")
                return "error", None
            return "removed", removed["player_id"]
        if data.get("default") == removed["player_id"]:
            data["default"] = accounts[0]["player_id"]
        if await self._save_bindings(event, data):
            return "removed", removed["player_id"]
        return "error", None
