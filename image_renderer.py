"""
查询结果图片渲染模块。

所有渲染函数返回生成的 PNG 文件路径，调用方负责发送

"""

from __future__ import annotations

import io
import os
import re
import tempfile
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

# 常见中文字体不含彩色 emoji 字形，直接绘制会变成方框，
# 因此渲染前统一移除 emoji，改用配色区分内容。
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # 各类 emoji 区块
    "\U00002600-\U000027BF"  # 杂项符号与装饰符号
    "\U00002300-\U000023FF"  # 杂项技术符号（⏱ 等）
    "\U00002B00-\U00002BFF"  # 箭头与星形（⭐ 等）
    "\U0001F1E6-\U0001F1FF"  # 区域指示符
    "]\ufe0f?",
    flags=re.UNICODE,
)


def _clean_text(text: object) -> str:
    """移除文本中的 emoji 并规整空白，避免字体缺字形显示为方框。"""
    if text is None:
        return ""
    cleaned = _EMOJI_PATTERN.sub("", str(text))
    return re.sub(r"\s{2,}", " ", cleaned).strip()

# ===== 配色方案（OW 风格深色主题）=====
BG_COLOR = (24, 26, 33)          # 页面背景
CARD_COLOR = (34, 37, 46)        # 卡片背景
CARD_COLOR_ALT = (40, 44, 55)    # 次级卡片背景
ACCENT_COLOR = (255, 153, 51)    # OW 橙
TEXT_MAIN = (240, 240, 245)      # 主文本
TEXT_SUB = (205, 210, 224)       # 次级文本（提高对比度）
TEXT_DIM = (150, 156, 172)       # 弱文本
DIVIDER_COLOR = (60, 64, 78)     # 分隔线
ROLE_COLORS = {
    "坦克": (96, 165, 250),      # 蓝
    "输出": (248, 113, 113),     # 红
    "支援": (74, 222, 128),      # 绿
}
# 赞赏等级配色（仿游戏内勋章色调）
ENDORSEMENT_COLORS = {
    1: (150, 152, 158),
    2: (92, 184, 92),
    3: (70, 160, 220),
    4: (170, 105, 220),
    5: (240, 165, 45),
}

# ===== 字体查找 =====
# 按优先级列出常见的中文字体路径，覆盖 Linux / Windows / macOS
_FONT_CANDIDATES = [
    # 插件自带字体目录（用户可自行放置字体文件）
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "font.ttf"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "font.ttc"),
    # Linux 常见
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    # Windows 常见
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    # macOS 常见
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载支持中文的字体。

    Args:
        size: 字号。

    Returns:
        字体对象。找不到中文字体时返回 Pillow 默认字体。
    """
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """测量文本宽度。"""
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(font: ImageFont.FreeTypeFont) -> int:
    """获取字体行高。"""
    bbox = font.getbbox("国Ag")
    return bbox[3] - bbox[1]


def _fit_text(draw: ImageDraw.ImageDraw, text: object, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """清理文本并截断到指定宽度内（超出部分以省略号结尾）。"""
    text = _clean_text(text)
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "..."
    while text and _text_width(draw, text + ellipsis, font) > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def _paste_avatar(card: Image.Image, avatar_bytes: bytes, x: int, y: int, size: int) -> None:
    """将头像以圆形裁剪后粘贴到卡片上。

    Args:
        card: 目标卡片图像。
        avatar_bytes: 头像图片二进制数据。
        x, y: 粘贴位置左上角坐标。
        size: 头像边长（正方形）。
    """
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((size, size), Image.LANCZOS)
        # 圆形遮罩
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        card.paste(avatar, (x, y), mask)
        # 描边
        border = ImageDraw.Draw(card)
        border.ellipse((x, y, x + size, y + size), outline=ACCENT_COLOR, width=3)
    except Exception:
        # 头像处理失败时静默跳过，不影响整体渲染
        pass


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    """绘制圆角矩形。"""
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _save_image(img: Image.Image) -> str:
    """将图像保存到临时文件并返回路径。"""
    fd, path = tempfile.mkstemp(suffix=".png", prefix="ow_render_")
    os.close(fd)
    img.save(path, format="PNG")
    return path


# ===== 卡片渲染 =====

def _draw_endorsement_badge(
    img: Image.Image, x: int, y: int, level: int, size: int = 34
) -> int:
    """绘制游戏内风格的赞赏等级六边形勋章，返回勋章宽度。

    Args:
        img: 目标图像。
        x, y: 勋章左上角坐标。
        level: 赞赏等级（0-5）。
        size: 勋章外接尺寸。

    Returns:
        勋章占用宽度。
    """
    import math

    level = max(0, min(int(level or 0), 5))
    color = ENDORSEMENT_COLORS.get(level, ENDORSEMENT_COLORS[5])
    cx, cy = x + size // 2, y + size // 2
    r = size // 2

    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    points = [
        (cx + r * math.cos(math.radians(60 * i - 30)),
         cy + r * math.sin(math.radians(60 * i - 30)))
        for i in range(6)
    ]
    d.polygon(points, fill=color)
    # 内圈
    r2 = r - 4
    points2 = [
        (cx + r2 * math.cos(math.radians(60 * i - 30)),
         cy + r2 * math.sin(math.radians(60 * i - 30)))
        for i in range(6)
    ]
    d.polygon(points2, fill=(28, 30, 38))
    img.paste(badge, (x, y), badge)

    # 等级数字
    font = _load_font(int(size * 0.62))
    text = str(level)
    tw = _text_width(ImageDraw.Draw(img), text, font)
    bbox = font.getbbox(text)
    th = bbox[3] - bbox[1]
    ImageDraw.Draw(img).text(
        (cx - tw // 2, cy - th // 2 - bbox[1]), text, font=font, fill=TEXT_MAIN
    )
    return size


def _draw_rank_section(
    img: Image.Image,
    y: int,
    rank_rows: Sequence[dict],
    width: int,
    pad: int,
) -> int:
    """绘制竞技段位区（坦克/输出/支援三职责，含段位图标），返回结束 y 坐标。

    Args:
        img: 目标图像。
        y: 起始 y 坐标。
        rank_rows: [{"role_text", "rank_text", "rank_icon_bytes"}, ...]。
        width: 卡片宽度。
        pad: 卡片内边距。

    Returns:
        绘制结束后的 y 坐标。
    """
    font_body = _load_font(26)
    draw = ImageDraw.Draw(img)
    draw.text((pad + 6, y), "竞技段位", font=font_body, fill=ACCENT_COLOR)
    y += _text_height(font_body) + 12
    for row in rank_rows:
        role_text = _fit_text(draw, row.get("role_text", ""), font_body, 200)
        rank_text = _fit_text(draw, row.get("rank_text", ""), font_body, width - pad - 320)
        color = TEXT_MAIN
        for role_cn, c in ROLE_COLORS.items():
            if role_cn in role_text:
                color = c
                break
        draw.text((pad + 20, y + 4), role_text, font=font_body, fill=color)
        icon_x = pad + 230
        icon_bytes = row.get("rank_icon_bytes")
        if icon_bytes:
            _paste_square_icon(img, icon_bytes, icon_x, y, 36, radius=18)
        draw.text((icon_x + 46, y + 4), rank_text, font=font_body, fill=TEXT_MAIN)
        y += 44
    return y


def _draw_heroes_section(
    img: Image.Image,
    y: int,
    top_heroes: Sequence[tuple[str, str, Optional[bytes]]],
    width: int,
    pad: int,
) -> int:
    """绘制常玩英雄区（最多 3 个，含英雄头像、名称与场次），返回结束 y 坐标。

    Args:
        img: 目标图像。
        y: 起始 y 坐标。
        top_heroes: [(英雄名, 场次/时长文本, 英雄头像数据), ...]。
        width: 卡片宽度。
        pad: 卡片内边距。

    Returns:
        绘制结束后的 y 坐标。
    """
    font_body = _load_font(26)
    font_hero = _load_font(22)
    font_small = _load_font(20)
    draw = ImageDraw.Draw(img)

    draw.line((pad, y, width - pad, y), fill=DIVIDER_COLOR, width=1)
    y += 12
    draw.text((pad + 6, y), "常玩英雄", font=font_body, fill=ACCENT_COLOR)
    y += _text_height(font_body) + 12
    slot_w = (width - pad * 2) // 3
    portrait_size = 76
    for idx, (hero_name, info_text, portrait_bytes) in enumerate(top_heroes[:3]):
        cx = pad + idx * slot_w
        if portrait_bytes:
            _paste_square_icon(img, portrait_bytes, cx + 4, y, portrait_size, radius=14)
        tx = cx + 4 + portrait_size + 12
        name_text = _fit_text(draw, hero_name, font_hero, slot_w - portrait_size - 20)
        info_text_c = _fit_text(draw, info_text, font_small, slot_w - portrait_size - 20)
        draw.text((tx, y + 12), name_text, font=font_hero, fill=TEXT_MAIN)
        draw.text((tx, y + 12 + _text_height(font_hero) + 8), info_text_c, font=font_small, fill=TEXT_SUB)
    return y + portrait_size + 16


def _banner_mask(width: int, height: int, radius: int) -> Image.Image:
    """生成仅上两角圆润的矩形遮罩（用于名片横幅）。"""
    mask = Image.new("L", (width, height), 0)
    d = ImageDraw.Draw(mask)
    # 先画一个超出底部的圆角矩形，再补齐下半部分，使底部保持直角
    d.rounded_rectangle((0, 0, width, height + radius), radius=radius, fill=255)
    d.rectangle((0, height - radius, width, height), fill=255)
    return mask


def _paste_banner(card: Image.Image, banner_bytes: bytes, xy: tuple[int, int, int, int]) -> None:
    """将名片横幅按游戏内效果缩放裁剪后粘贴到卡片指定区域。

    名片为宽幅图片，按区域宽度等比缩放并居中裁剪，上两角保持与卡片一致的圆角。

    Args:
        card: 目标卡片图像。
        banner_bytes: 名片图片二进制数据。
        xy: 目标区域 (x1, y1, x2, y2)。
    """
    try:
        x1, y1, x2, y2 = xy
        w, h = x2 - x1, y2 - y1
        banner = Image.open(io.BytesIO(banner_bytes)).convert("RGBA")
        # 等比缩放至覆盖目标区域后居中裁剪
        scale = max(w / banner.width, h / banner.height)
        new_size = (int(banner.width * scale + 0.5), int(banner.height * scale + 0.5))
        banner = banner.resize(new_size, Image.LANCZOS)
        left = (banner.width - w) // 2
        top = (banner.height - h) // 2
        banner = banner.crop((left, top, left + w, top + h))
        # 底部压暗，保证横幅上的文字可读（alpha 混合而非替换）
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for i in range(h):
            alpha = int(110 * (i / h) ** 1.5)
            od.line((0, i, w, i), fill=(10, 12, 18, alpha))
        banner = Image.alpha_composite(banner, overlay)
        mask = _banner_mask(w, h, 18)
        card.paste(banner.convert("RGB"), (x1, y1), mask)
    except Exception:
        # 名片处理失败时静默跳过，不影响整体渲染
        pass


def _paste_square_icon(card: Image.Image, icon_bytes: bytes, x: int, y: int, size: int, radius: int = 8) -> None:
    """将方形图标（英雄头像/段位图标）圆角粘贴到卡片上。"""
    try:
        icon = Image.open(io.BytesIO(icon_bytes)).convert("RGBA")
        icon = icon.resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
        card.paste(icon, (x, y), mask)
    except Exception:
        pass


def render_summary_card(
    username: str,
    title: str,
    endorsement_level: int,
    rank_rows: Sequence[dict],
    platform_label: str,
    avatar_bytes: Optional[bytes] = None,
    namecard_bytes: Optional[bytes] = None,
    top_heroes: Sequence[tuple[str, str, Optional[bytes]]] = (),
    footer_note: Optional[str] = None,
) -> str:
    """渲染玩家摘要卡片（游戏内名片 + 头像组合效果）。

    名片作为顶部横幅，头像以圆形叠加在横幅左侧（还原游戏内个人资料页效果）；
    下方依次为竞技段位（含段位图标）与常玩英雄 TOP3（含英雄头像）。

    Args:
        username: 玩家名。
        title: 头衔（可为空）。
        endorsement_level: 赞赏等级。
        rank_rows: [{"role_text", "rank_text", "rank_icon_bytes"}, ...]。
        platform_label: 平台显示文本，如 "PC端"。
        avatar_bytes: 头像图片数据（可选）。
        namecard_bytes: 名片横幅图片数据（可选，纯文字模式不展示）。
        top_heroes: [(英雄名, 游戏时长文本, 英雄头像数据), ...]。
        footer_note: 底部备注（可选）。

    Returns:
        生成的 PNG 文件路径。
    """
    W = 680
    PAD = 28
    font_title = _load_font(36)
    font_sub = _load_font(23)
    font_body = _load_font(26)
    font_hero = _load_font(22)
    font_small = _load_font(20)

    username = _fit_text(ImageDraw.Draw(Image.new("RGB", (1, 1))), username, font_title, W - PAD * 2 - 150)
    title = _clean_text(title)
    platform_label = _clean_text(platform_label)
    footer_note = _clean_text(footer_note)

    banner_h = 150 if namecard_bytes else 0
    avatar_size = 108 if avatar_bytes else 0
    # 无名片时保留原有的文本头部高度
    header_h = banner_h if namecard_bytes else (max(avatar_size, 96) + 10)
    rank_block_h = len(rank_rows) * 44 + 58
    heroes_block_h = (150 if top_heroes else 0)
    footer_h = 34 if footer_note else 10
    H = PAD + header_h + rank_block_h + heroes_block_h + footer_h + 24

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _rounded_rect(draw, (10, 10, W - 10, H - 10), 18, CARD_COLOR)

    # ===== 头部：名片横幅 + 头像（游戏内效果）=====
    if namecard_bytes:
        _paste_banner(img, namecard_bytes, (10, 10, W - 10, 10 + banner_h))
    else:
        draw.rectangle((10, 10, W - 10, 16), fill=ACCENT_COLOR)

    text_x = PAD + 10
    text_y_center = 10 + (banner_h // 2 if namecard_bytes else header_h // 2)
    if avatar_bytes:
        av_x = PAD + 8
        av_y = text_y_center - avatar_size // 2
        _paste_avatar(img, avatar_bytes, av_x, av_y, avatar_size)
        text_x = av_x + avatar_size + 18

    # 用户名 / 头衔（垂直居中于头部区域）
    lines_h = _text_height(font_title) + 10
    if title:
        lines_h += _text_height(font_sub) + 6
    lines_h += 40  # 赞赏勋章行
    ty = text_y_center - lines_h // 2
    draw.text((text_x, ty), username, font=font_title, fill=TEXT_MAIN)
    ty += _text_height(font_title) + 10
    if title:
        draw.text((text_x, ty), title, font=font_sub, fill=ACCENT_COLOR)
        ty += _text_height(font_sub) + 6

    # 赞赏等级勋章 + 平台
    badge_size = 34
    _draw_endorsement_badge(img, text_x, ty, endorsement_level, badge_size)
    label = _fit_text(draw, f"赞赏 {endorsement_level} 级   {platform_label}", font_sub, W - text_x - badge_size - 24)
    draw.text((text_x + badge_size + 10, ty + (badge_size - _text_height(font_sub)) // 2), label, font=font_sub, fill=TEXT_SUB)

    y = 10 + header_h + 12
    draw.line((PAD, y, W - PAD, y), fill=DIVIDER_COLOR, width=2)
    y += 14

    # ===== 竞技段位（坦克/输出/支援三职责，含段位图标）=====
    y = _draw_rank_section(img, y, rank_rows, W, PAD)

    # ===== 常玩英雄（含英雄头像与场次/时长）=====
    if top_heroes:
        y += 4
        y = _draw_heroes_section(img, y, top_heroes, W, PAD)

    if footer_note:
        y += 2
        draw.line((PAD, y, W - PAD, y), fill=DIVIDER_COLOR, width=1)
        y += 10
        draw.text((PAD + 6, y), _fit_text(draw, footer_note, font_small, W - PAD * 2 - 12), font=font_small, fill=TEXT_DIM)

    return _save_image(img)


def render_stats_card(
    player_id: str,
    gamemode_label: str,
    platform_label: str,
    stat_rows: Sequence[tuple[str, str]],
    rank_rows: Sequence[dict] = (),
    top_heroes: Sequence[tuple[str, str, Optional[bytes]]] = (),
) -> str:
    """渲染玩家统计概览卡片。

    Args:
        player_id: 玩家 ID。
        gamemode_label: 游戏模式显示文本。
        platform_label: 平台显示文本。
        stat_rows: [(标签, 数值), ...]。
        rank_rows: 竞技模式时传入的三职责段位行（含段位图标），可为空。
        top_heroes: 常玩英雄 [(名称, 场次文本, 头像数据), ...]，可为空。

    Returns:
        生成的 PNG 文件路径。
    """
    W = 720
    PAD = 28
    font_title = _load_font(30)
    font_sub = _load_font(22)
    font_body = _load_font(24)

    rows = [(_clean_text(label), _clean_text(value)) for label, value in stat_rows]
    per_col = (len(rows) + 1) // 2
    grid_h = per_col * 54 + 10
    rank_h = (len(rank_rows) * 44 + 70) if rank_rows else 0
    heroes_h = 158 if top_heroes else 0
    H = PAD * 2 + 96 + rank_h + grid_h + heroes_h + 20

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _rounded_rect(draw, (10, 10, W - 10, H - 10), 18, CARD_COLOR)
    draw.rectangle((10, 10, W - 10, 16), fill=ACCENT_COLOR)

    y = PAD + 6
    draw.text((PAD + 6, y), "统计概览", font=font_title, fill=ACCENT_COLOR)
    y += _text_height(font_title) + 10
    sub = _fit_text(
        draw,
        f"{player_id}  |  {_clean_text(gamemode_label)}  |  {_clean_text(platform_label)}",
        font_sub,
        W - PAD * 2 - 12,
    )
    draw.text((PAD + 6, y), sub, font=font_sub, fill=TEXT_SUB)
    y += _text_height(font_sub) + 14
    draw.line((PAD, y, W - PAD, y), fill=DIVIDER_COLOR, width=2)
    y += 16

    # ===== 竞技段位区（仅竞技模式）=====
    if rank_rows:
        y = _draw_rank_section(img, y, rank_rows, W, PAD)
        draw.line((PAD, y, W - PAD, y), fill=DIVIDER_COLOR, width=1)
        y += 14

    # ===== 两列网格布局 =====
    col_w = (W - PAD * 2 - 20) // 2
    for idx, (label, value) in enumerate(rows):
        col = idx // per_col
        row = idx % per_col
        cx = PAD + 6 + col * (col_w + 20)
        cy = y + row * 54
        _rounded_rect(draw, (cx - 6, cy - 6, cx + col_w - 6, cy + 42), 10, CARD_COLOR_ALT)
        label_text = _fit_text(draw, label, font_body, col_w - 20)
        draw.text((cx + 8, cy), label_text, font=font_body, fill=TEXT_SUB)
        lw = _text_width(draw, label_text, font_body)
        value_text = _fit_text(draw, value, font_body, col_w - lw - 34)
        draw.text((cx + 8 + lw + 12, cy), value_text, font=font_body, fill=TEXT_MAIN)
    y += per_col * 54 + 6

    # ===== 常玩英雄（含头像与场次）=====
    if top_heroes:
        y = _draw_heroes_section(img, y, top_heroes, W, PAD)

    return _save_image(img)


def render_career_card(
    player_id: str,
    gamemode_label: str,
    platform_label: str,
    hero_filter: Optional[str],
    heroes: Sequence[tuple[str, Sequence[tuple[str, str]], Optional[bytes]]],
    remaining: int = 0,
) -> str:
    """渲染生涯统计卡片（每个英雄区块带英雄头像）。

    Args:
        player_id: 玩家 ID。
        gamemode_label: 游戏模式显示文本。
        platform_label: 平台显示文本。
        hero_filter: 英雄筛选显示文本（可选）。
        heroes: [(英雄名, [(标签, 数值), ...], 英雄头像数据), ...]。
        remaining: 未显示的剩余英雄数量。

    Returns:
        生成的 PNG 文件路径。
    """
    W = 720
    PAD = 28
    font_title = _load_font(30)
    font_sub = _load_font(22)
    font_hero = _load_font(26)
    font_body = _load_font(23)

    # 计算高度
    hero_blocks_h = 0
    for item in heroes:
        rows = item[1]
        hero_blocks_h += 44 + max(len(rows), 1) * 36 + 14
    extra_h = 40 if remaining > 0 else 0
    H = PAD * 2 + 96 + hero_blocks_h + extra_h + 16

    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _rounded_rect(draw, (10, 10, W - 10, H - 10), 18, CARD_COLOR)
    draw.rectangle((10, 10, W - 10, 16), fill=ACCENT_COLOR)

    y = PAD + 6
    draw.text((PAD + 6, y), "生涯统计", font=font_title, fill=ACCENT_COLOR)
    y += _text_height(font_title) + 10
    sub = f"{player_id}  |  {_clean_text(gamemode_label)}  |  {_clean_text(platform_label)}"
    if hero_filter:
        sub += f"  |  英雄: {_clean_text(hero_filter)}"
    draw.text((PAD + 6, y), _fit_text(draw, sub, font_sub, W - PAD * 2 - 12), font=font_sub, fill=TEXT_SUB)
    y += _text_height(font_sub) + 14
    draw.line((PAD, y, W - PAD, y), fill=DIVIDER_COLOR, width=2)
    y += 16

    for item in heroes:
        hero_name, rows = item[0], item[1]
        portrait_bytes = item[2] if len(item) > 2 else None
        _rounded_rect(draw, (PAD, y, W - PAD, y + 36 + max(len(rows), 1) * 36 + 8), 12, CARD_COLOR_ALT)
        # 英雄头像（若有）+ 英雄名
        text_x = PAD + 14
        if portrait_bytes:
            _paste_square_icon(img, portrait_bytes, PAD + 12, y + 2, 34, radius=10)
            text_x = PAD + 12 + 34 + 10
        draw.text((text_x, y + 6), _fit_text(draw, hero_name, font_hero, W - text_x - PAD - 12), font=font_hero, fill=ACCENT_COLOR)
        y += 44
        for label, value in rows:
            label_text = _fit_text(draw, label, font_body, 180)
            draw.text((PAD + 26, y), label_text, font=font_body, fill=TEXT_SUB)
            lw = _text_width(draw, label_text, font_body)
            value_text = _fit_text(draw, value, font_body, W - PAD * 2 - 26 - lw - 24)
            draw.text((PAD + 26 + lw + 12, y), value_text, font=font_body, fill=TEXT_MAIN)
            y += 36
        y += 14

    if remaining > 0:
        draw.text((PAD + 14, y), f"... 还有 {remaining} 个英雄的数据未显示", font=font_sub, fill=TEXT_DIM)

    return _save_image(img)
