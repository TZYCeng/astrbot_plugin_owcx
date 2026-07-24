# AstrBOT 守望先锋国际服查询插件
作者其实是个小白来的，部分由ai创建，希望各位大神有兴趣可以改吧改吧
# 注意,部分使用steam启动的玩家无法被查询
# 缓存依照开发指南更改为KV之前绑定ID作废，请重新绑定

🎮 **守望先锋·归来国际服查询插件**

[![Version](https://img.shields.io/badge/version-v1.7.0-blue.svg)](https://github.com/TZYCeng/astrbot_plugin_owcx)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.9+-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


## 📦 安装方法
### 方法一：通过AstrBot插件市场
1. 打开AstrBot WebUI
2. 进入插件管理
3. 搜索 "astrbot_plugin_owcx"
4. 点击安装
### 方法二：手动安装
1. 下载插件文件到AstrBot的插件目录
```bash
cd AstrBot/data/plugins
git clone https://github.com/TZYCeng/astrbot_plugin.git
```
2. 安装依赖
```bash
pip install -r requirements.txt
```
3. 重启AstrBot

## 使用方法
### owsummary 
查询玩家摘要信息（头像、竞技段位等）。 用法: /owsummary [玩家ID] 示例: /owsummary TeKrop#2217 或 /owsummary 同志有程#3156 说明: 玩家ID支持直接输入 #，插件会自动处理；省略 ID 则查询绑定的账号（使用绑定平台）
### owstats 
查询玩家统计概览（胜率、KDA等）。 用法: /owstats [玩家ID] [游戏模式] 游戏模式: 快速、竞技（默认） 示例: /owstats TeKrop#2217 竞技 说明: 省略 ID 则查询绑定的账号
### owcareer 
查询玩家生涯统计（按英雄详细数据）。 用法: /owcareer [玩家ID] <游戏模式> [英雄名] 游戏模式: 快速、竞技 英雄名: 可选，支持中文（如 源氏、安娜）或英文（如 genji, ana） 示例: /owcareer TeKrop#2217 竞技 /owcareer TeKrop#2217 竞技 源氏 /owcareer 竞技 源氏 (已绑定ID后)
### owhero 
查询英雄详细信息（含该英雄在当前配置地区/平台/模式下的全服胜率与选取率）。 用法: /owhero <英雄名> 英雄名支持中文（如 源氏、安娜）或英文（如 genji, ana） 示例: /owhero 源氏, /owhero ana
### owherostats 
查询全服英雄胜率/选取率排行榜（按地区服务器统计，展示全部英雄）。 用法: /owherostats [角色] [地区] 角色: 坦克、输出、支援（可选） 地区: 亚服(asia)、美服(americas)、欧服(europe)，不填则使用配置中的默认地区 平台与游戏模式使用配置文件中的默认值 示例: /owherostats /owherostats 输出 /owherostats 支援 欧服
### owbind 
绑定 Overwatch ID 到当前 QQ 号，可选择平台（PC端/主机端），每个 QQ 号可绑定多个账号（数量上限见配置 max_binds_per_user，默认 3 个），新绑定的账号自动成为默认查询账号。 用法: /owbind <玩家ID> [平台] 平台: pc(电脑端)、console(主机端)，不填则使用配置中的默认平台 示例: /owbind TeKrop#2217 或 /owbind TeKrop#2217 主机 说明: 旧版本绑定数据自动迁移，无需手动处理
### owunbind 
解绑当前 QQ 号绑定的 Overwatch ID。 用法: /owunbind [玩家ID] 说明: 不填玩家ID时解绑当前默认查询账号；解绑默认账号后自动切换到剩余账号
### owbinds 
查看当前 QQ 号绑定的所有 Overwatch 账号（含平台与默认标记）。 用法: /owbinds
### owdefault 
设置默认查询的 Overwatch 账号，快捷指令省略 ID 时将查询该账号。 用法: /owdefault <玩家ID> 示例: /owdefault TeKrop#2217
### owme 
快捷查询默认绑定账号的摘要信息。 用法: /owme 说明: 需要先使用 /owbind 绑定，多账号时查询 /owdefault 设置的账号

## 🔧 故障排除
### 常见问题
1. **查询失败**
   - 检查战网标签格式是否正确
   - 部分使用steam启动的玩家无法被查询
   - 确保玩家资料是公开的
   - 检查网络连接
   - 是否设置为好友公开导致误判

2. **API错误**
   - 可能是API服务暂时不可用
   - 插件会自动重试，请稍后再试

3. **绑定失败**
   - 确认战网标签格式：玩家-数字
   - 检查是否包含特殊字符

## ⚙️ 配置说明
在 AstrBot WebUI 的插件配置中可设置以下选项：
- **默认查询的游戏模式**: 竞技比赛 / 快速游戏
- **默认查询的平台**: pc / console（未绑定平台或绑定时未选择平台时使用）
- **默认查询的地区服务器** (`default_region`): asia(亚服) / americas(美服) / europe(欧服)，用于 /owherostats 等按地区统计的查询
- **每QQ号绑定上限** (`max_binds_per_user`): 每个 QQ 号最多可绑定的 Overwatch 账号数量，默认 3
- **图片渲染开关** (`enable_image_render`): 开启后（默认开启），/owsummary、/owstats、/owcareer、/owme 的查询结果会渲染为守望先锋风格的卡片图片（摘要卡片含名片横幅+头像组合、段位图标、常玩英雄头像）；想用就开，不想用就关，关闭时保持原有纯文字输出。渲染失败或未安装 Pillow 时会自动回退为文字输出，不影响正常使用
- **报错展示开关** (`show_api_error`): 开启后，查询出错时机器人会把 API 返回的具体报错（含建议重试等待时间）回复给查询者；无论开关与否，完整报错与堆栈都会记录在控制台 debug 日志中
- 图片渲染依赖 Pillow：`pip install Pillow>=9.0.0`（已在 requirements.txt 中）
- 如系统缺少中文字体导致渲染文字异常，可在插件目录下新建 `fonts` 文件夹并放入任意中文字体文件（命名为 `font.ttf` 或 `font.ttc`）

## 💡 关于玩家ID中的 #
- 指令中直接输入 `玩家名#1234` 即可（如 /owsummary 同志有程#3156），插件会自动将 # 替换为 - 再查询
- 绑定时同样支持直接输入 #，KV 存储中统一保留 `玩家名-1234` 的规范化形式，查询绑定账号时直接使用存储值

## 版本历史

### v1.7.0(当前版本)
- 删除 /owsearch 与 /owheroes 指令（功能被 /owsummary 与 /owhero 覆盖）
- 修复 /owstats 数据缺失：场均消灭/死亡/伤害/治疗按 API 规范从 general.average 读取（此前读取不存在的顶层字段导致 N/A）
- /owstats 竞技模式新增三职责晋级段位展示（坦克/输出/支援，含段位图标），并新增常玩英雄（按场次前三，渲染头像）
- /owsummary 摘要卡渲染赞赏等级勋章（游戏内六边形风格），提高次级文字对比度；常玩英雄区去除"TOP3"字样并展示场次
- /owcareer 图片渲染时每个英雄区块前添加英雄头像
- /owherostats 展示全部英雄胜率（不再截断前 15）；/owhero 同步查询并展示该英雄的全服胜率与选取率
- 多账号绑定：每个 QQ 号可绑定多个 OW 账号（配置 max_binds_per_user，默认 3），KV 结构升级并自动迁移旧数据
- 新增 /owbinds 查看绑定列表、/owdefault 设置默认查询账号；/owunbind 支持指定账号解绑

### v1.6.0
- 修复竞技段位解析：段位字段按 API 实际结构 competitive → 平台 → 坦克/输出/支援 读取，三个职责全部展示（此前字段名不匹配导致只显示"暂无数据"）
- 摘要卡片新增名片渲染：头像与名片（namecard）按游戏内个人资料页效果组合（名片横幅 + 圆形头像叠加），纯文字输出不展示名片
- 段位区展示官方段位图标，卡片下方新增常玩英雄 TOP3（含英雄头像与游戏时长）
- 英雄头像取自 API /heroes 返回的官方战网 CDN 肖像（与 wiki 头像同源），无需额外图床
- 图片渲染开关（enable_image_render）默认改为开启
- 摘要查询改用 /players/{id} 完整数据接口，一次请求获取段位与常玩英雄数据

### v1.5.0
- 玩家ID全面支持直接输入 #（绑定与查询均自动处理），帮助文案补充说明
- 英雄中文映射补全至 52 名英雄（与 API HeroKey 枚举对齐），新增骇灾、弗蕾娅、无漾、斩仇、安燃、金驭、埃姆雷、瑞稀、飞天猫、西拉、紫苑、伊拉锐等国服官方译名
- 新增 /owherostats 指令：按地区服务器（亚服/美服/欧服）查询全服英雄胜率/选取率排行
- 配置新增默认地区服务器（default_region）
- API 报错结构化解析（含状态码、错误详情、retry_after），完整报错记录到控制台 debug 日志
- 配置新增报错展示开关（show_api_error）：开启后查询出错时向查询者回复 API 具体报错

### v1.4.0
- 绑定账号时支持选择平台（PC端/主机端）：/owbind <玩家ID> [pc|主机]
- 查询指令（owsummary/owstats/owcareer/owme）默认使用绑定平台查询数据
- 旧版绑定数据自动兼容（沿用配置默认平台），可 /owunbind 后重新绑定以选择平台
- 新增查询结果图片渲染功能（owsummary/owstats/owcareer/owme），渲染为 OW 风格卡片
- 图片渲染带配置开关（enable_image_render），默认关闭；渲染失败自动回退文字输出

### v1.3.0
- 重构插件
- 重构命令
- 缓存更改为KV缓存
- 添加简单配置界面
- 计划下一版本进行战绩图片渲染
  
### v1.2.1
- 缓存降级增强
- 更改描述页
- 增加英雄查询（独立查询）
- 可以查询单个英雄战绩，可以查询休闲和竞技两个模式
- 绑定提示优化
- 添加主机平台战绩查询
- resp 异常修复
- 错误提示细化

### v1.1.1
- 找不到方法解决常玩英雄的两百报错问题，直接删去常玩英雄项目查询
- 职责显示更改为中文
- 竞技段位未定级也显示

### v1.1.0 
- 修复API域名失效问题
- 增强错误处理
- 添加详细统计信息
- 将API请求分为五段整合后再发出减少超时可能
- 增加申请管控防止过量请求
  
### v1.0.0 
- 修复API域名失效问题
- 添加自动重�