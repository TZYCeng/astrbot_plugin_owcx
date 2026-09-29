"""共享常量：段位/角色/模式/平台/地区/英雄映射。"""

RANK_MAPPING = {
    "bronze": ("青铜", ""),
    "silver": ("白银", ""),
    "gold": ("黄金", ""),
    "platinum": ("铂金", ""),
    "emerald": ("翡翠", ""),
    "diamond": ("钻石", ""),
    "master": ("大师", ""),
    "grandmaster": ("宗师", ""),
    # API 4.13 起最高段位改名为 ultimate；保留 champion 兼容旧数据/旧自建实例
    "champion": ("王者", ""),
    "ultimate": ("王者", ""),
    "top500": ("五百强", ""),
}

ROLE_MAPPING = {
    "tank": ("坦克", ""),
    "damage": ("输出", ""),
    "support": ("支援", ""),
}

GAMEMODE_MAPPING = {
    "quickplay": "快速游戏",
    "competitive": "竞技比赛",
}

GAMEMODE_REVERSE_MAPPING = {
    "快速": "quickplay",
    "快速游戏": "quickplay",
    "qp": "quickplay",
    "quick": "quickplay",
    "quickplay": "quickplay",
    "竞技": "competitive",
    "竞技模式": "competitive",
    "竞技比赛": "competitive",
    "排位": "competitive",
    "排位赛": "competitive",
    "comp": "competitive",
    "competitive": "competitive",
}

PLATFORM_MAPPING = {
    "pc": "PC端",
    "console": "主机端",
}

PLATFORM_REVERSE_MAPPING = {
    "pc": "pc",
    "电脑": "pc",
    "电脑端": "pc",
    "端游": "pc",
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

REGION_MAPPING = {
    "asia": "亚服",
    "americas": "美服",
    "europe": "欧服",
}

REGION_REVERSE_MAPPING = {
    "asia": "asia",
    "亚服": "asia",
    "亚洲": "asia",
    "亚太": "asia",
    "americas": "americas",
    "america": "americas",
    "美服": "americas",
    "美洲": "americas",
    "europe": "europe",
    "eu": "europe",
    "欧服": "europe",
    "欧洲": "europe",
}

HERO_NAME_MAPPING = {
    "doomfist": "末日铁拳",
    "dva": "D.Va",
    "dmon": "D.Mon",
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
    "ana": "安娜",
    "baptiste": "巴蒂斯特",
    "brigitte": "布丽吉塔",
    "doctrine": "血律",
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

HERO_NAME_REVERSE_MAPPING = {cn: en for en, cn in HERO_NAME_MAPPING.items()}

ROLE_CN_TO_EN = {
    "坦克": "tank", "tank": "tank", "重装": "tank",
    "输出": "damage", "damage": "damage",
    "支援": "support", "support": "support", "辅助": "support",
}
