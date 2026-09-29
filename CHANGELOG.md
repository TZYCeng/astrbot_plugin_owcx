# 更新日志 (CHANGELOG)

## [v2.2.0]（当前版本）

- 重构：`main.py` 拆分为 `constants.py`/`utils.py`/`bindings.py`，旧导入路径保留兼容
- 性能：API 客户端默认超时 30s→15s，进程级 GET 缓存（玩家 120s/榜单 600s/英雄 3600s），429/503 按 `retry_after` 自动重试
- 并发：图片/头像下载复用单 session + 6 并发上限，不再每图新建 session
- 泄漏：`image_renderer` 新增 `cleanup_old_images()`（每小时，`_save_image` 自动触发），`owherostats` 图片模式避免 54 行超长文本
- 健壮：玩家 ID 归一化+长度/字符校验+URL quote；图片开关默认与 schema 一致为开启；移除 `COMPETITIVE_ICONS` 重复；日志统一 AstrBot logger
- 可测：新增 `tests/test_utils.py`（纯函数+绑定迁移），新增 `requirements-dev.txt`
- 杂项：修正 README 仓库地址，删除重复 `logo.png.png`

## [v2.1.0]

- 英雄映射新增第 53 位英雄 D.Mon（重装，第 4 赛季）与第 54 位英雄血律 Doctrine（支援，第 5 赛季），现可通过 /owhero D.Mon、/owhero 血律 等查询
- 英雄中文映射补全至 54 名英雄（与 OverFast API HeroKey 枚举对齐）

## [v2.0.0]

- 删除 /owsearch 与 /owheroes 指令（功能被 /owsummary 与 /owhero 覆盖）
- /owherostats 展示全部英雄胜率（不再截断前 15）；/owhero 同步查询并展示该英雄的全服胜率与选取率
- 多账号绑定：每个 QQ 号可绑定多个 OW 账号（配置 max_binds_per_user，默认 3），KV 结构升级并自动迁移旧数据
- 新增 /owbinds 查看绑定列表、/owdefault 设置默认查询账号；/owunbind 支持指定账号解绑
- 新增查询结果图片渲染功能（owsummary/owstats/owcareer/owme），渲染为 OW 风格卡片
- 绑定账号时支持选择平台（PC端/主机端）：/owbind <玩家ID> [pc|主机]
- 英雄中文映射补全至 52 名英雄（与 API HeroKey 枚举对齐），新增骇灾、弗蕾娅、无漾、斩仇、安燃、金驭、埃姆雷、瑞稀、飞天猫、西拉
- API 报错结构化解析（含状态码、错误详情、retry_after），完整报错记录到控制台 debug 日志
- 插件会自动将 # 替换为 - 再查询

## [v1.3.0]

- 重构插件
- 重构命令
- 缓存更改为KV缓存
- 添加简单配置界面
- 计划下一版本进行战绩图片渲染

## [v1.2.1]

- 缓存降级增强
- 更改描述页
- 增加英雄查询（独立查询）
- 可以查询单个英雄战绩，可以查询休闲和竞技两个模式
- 绑定提示优化
- 添加主机平台战绩查询
- resp 异常修复
- 错误提示细化

## [v1.1.1]

- 找不到方法解决常玩英雄的两百报错问题，直接删去常玩英雄项目查询
- 职责显示更改为中文
- 竞技段位未定级也显示

## [v1.1.0]

- 修复API域名失效问题
- 增强错误处理
- 添加详细统计信息
- 将API请求分为五段整合后再发出减少超时可能
- 增加申请管控防止过量请求

## [v1.0.0]

- 修复API域名失效问题
- 添加自动重试机制
