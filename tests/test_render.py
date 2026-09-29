"""渲染冒烟测试：四种卡片均可生成非空 PNG（无网络，仅 Pillow）。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _assert_png(path: str) -> None:
    try:
        assert os.path.exists(path), path
        assert os.path.getsize(path) > 0, path
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def test_render_summary_card():
    from image_renderer import render_summary_card

    path = render_summary_card(
        username="TeKrop-2217",
        title="Bytefixer",
        endorsement_level=3,
        rank_rows=[
            {"role_text": "坦克", "rank_text": "钻石 III", "rank_icon_bytes": None},
            {"role_text": "输出", "rank_text": "翡翠 I", "rank_icon_bytes": None},
            {"role_text": "支援", "rank_text": "王者 I", "rank_icon_bytes": None},
        ],
        platform_label="PC端",
        top_heroes=[("源氏", "12.5小时", None)],
    )
    _assert_png(path)


def test_render_stats_card():
    from image_renderer import render_stats_card

    path = render_stats_card(
        player_id="TeKrop-2217",
        gamemode_label="竞技比赛",
        platform_label="PC端",
        stat_rows=[("场次", "100 (60胜/40负)"), ("胜率", "60%")],
        top_heroes=[("源氏", "20场", None)],
    )
    _assert_png(path)


def test_render_career_card():
    from image_renderer import render_career_card

    path = render_career_card(
        player_id="TeKrop-2217",
        gamemode_label="竞技比赛",
        platform_label="PC端",
        hero_filter="源氏",
        heroes=[("源氏", [("消灭", "100"), ("死亡", "50")], None)],
    )
    _assert_png(path)


def test_render_herostats_card():
    from image_renderer import render_herostats_card

    path = render_herostats_card(
        title="英雄胜率排行",
        subtitle="亚服 | 竞技比赛 | PC端",
        rows=[("1. 源氏", "胜率 52.0% | 选取率 8.0%")],
    )
    _assert_png(path)
