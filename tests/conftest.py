"""pytest 本地桩：在没有 AstrBot 宿主的环境下提供最小 `astrbot` 接口。

插件根目录本身是一个包（AstrBot 要求 `__init__.py`），pytest 在收集
阶段会导入它，进而链式导入 `main.py` → `astrbot.*`。本文件在收集前
向 `sys.modules` 注入最小桩，使纯逻辑与插件模块可导入、可单测；
AstrBot 真实运行时桩不会生效（`astrbot` 已存在则直接返回）。
"""

import logging
import sys
import types


def _build_filter():
    mod = types.ModuleType("astrbot.api.event")

    class _Filter:
        @staticmethod
        def command(name):
            def deco(fn):
                fn._astrbot_command = name
                return fn

            return deco

    class AstrMessageEvent:
        pass

    mod.filter = _Filter()
    mod.AstrMessageEvent = AstrMessageEvent
    return mod


def _ensure_astrbot_stub() -> None:
    if "astrbot" in sys.modules:
        return
    log = logging.getLogger("astrbot-stub")

    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = log

    comp = types.ModuleType("astrbot.api.message_components")

    class _Image:
        def __init__(self, kind, payload):
            self.kind = kind
            self.payload = payload

        @classmethod
        def fromFileSystem(cls, path):
            return cls("file", path)

        @classmethod
        def fromURL(cls, url):
            return cls("url", url)

    class _Plain:
        def __init__(self, text):
            self.text = text

    comp.Image = _Image
    comp.Plain = _Plain

    all_mod = types.ModuleType("astrbot.api.all")

    class AstrBotConfig(dict):
        pass

    all_mod.AstrBotConfig = AstrBotConfig

    star = types.ModuleType("astrbot.api.star")

    class Context:
        pass

    class Star:
        def __init__(self, context=None):
            self.context = context

    star.Context = Context
    star.Star = Star

    event = _build_filter()

    api.message_components = comp
    api.all = all_mod
    api.event = event
    api.star = star
    astrbot.api = api

    for name, module in {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.message_components": comp,
        "astrbot.api.all": all_mod,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
    }.items():
        sys.modules[name] = module


_ensure_astrbot_stub()
