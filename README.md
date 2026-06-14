# AstrBOT 守望先锋国际服查询插件
作者其实是个小白来的，部分由ai创建，希望各位大神有兴趣可以改吧改吧
# 注意,部分使用steam启动的玩家无法被查询
# 缓存依照开发指南更改为KV之前绑定ID作废，请重新绑定

🎮 **守望先锋·归来国际服查询插件**

[![Version](https://img.shields.io/badge/version-v1.3.0-blue.svg)](https://github.com/TZYCeng/astrbot_plugin_owcx)
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
### owsearch搜索 Overwatch 2 玩家。 用法: /owsearch <玩家名> 示例: /owsearch TeKrop
### owsummary查询玩家摘要信息（头像、竞技段位等）。 用法: /owsummary [玩家ID] 示例: /owsummary TeKrop#2217 说明: 支持直接使用 #，会自动替换；省略 ID 则查询绑定的账号
### owstats查询玩家统计概览（胜率、KDA等）。 用法: /owstats [玩家ID] [游戏模式] 游戏模式: 快速、竞技（默认） 示例: /owstats TeKrop#2217 竞技 说明: 省略 ID 则查询绑定的账号
### owcareer查询玩家生涯统计（按英雄详细数据）。 用法: /owcareer [玩家ID] <游戏模式> [英雄名] 游戏模式: 快速、竞技 英雄名: 可选，支持中文（如 源氏、安娜）或英文（如 genji, ana） 示例: /owcareer TeKrop#2217 竞技 /owcareer TeKrop#2217 竞技 源氏 /owcareer 竞技 源氏 (已绑定ID后)
### owhero查询英雄详细信息。 用法: /owhero <英雄名> 英雄名支持中文（如 源氏、安娜）或英文（如 genji, ana） 示例: /owhero 源氏, /owhero ana
### owheroes列出所有英雄，可按角色筛选。 用法: /owheroes [角色] 角色: 坦克(tank)、输出(damage)、支援(support) 示例: /owheroes /owheroes 坦克
### owbind绑定你的 Overwatch ID 到当前 QQ 号。 绑定后可直接使用 /owme、/owsummary、/owstats、/owcareer 等指令查询自己的数据。 用法: /owbind <玩家ID> 示例: /owbind TeKrop#2217
### owunbind解绑当前 QQ 号绑定的 Overwatch ID。 用法: /owunbind
### owme快捷查询自己绑定的 Overwatch 账号摘要信息。 用法: /owme 说明: 需要先使用 /owbind 绑定

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

## 版本历史

### v1.3.0(当前版本)
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
- 添加自动重试机制
- 实现智能缓存
- 增强错误处理
- 详细统计信息
- 性能优化

### v0.0.2 
- 基础战绩查询
- 用户绑定功能
- 简洁消息格式

## 欢迎提交Issue和Pull Request！
- 使用清晰的提交信息
- 添加适当的测试
- 更新文档

## 📄 许可证
本项目采用 MIT 许可证 

## 👥 社区支持
- **QQ群**: [710574642](https://qm.qq.com/q/UIgSKUGFG2) 
- **GitHub Issues**: [提交问题](https://github.com/TZYCeng/astrbot_plugin_owcx/issues) 
- **Discussions**: [讨论区](https://github.com/TZYCeng/astrbot_plugin_owcx/discussions) 

## 🙏 致谢
- Kimi和豆包
- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 优秀的机器人框架
- [OverFast API](https://overfast-api.tekrop.fr) - 提供稳定的守望先锋API
- [守望先锋社区](https://ow.blizzard.cn) - 游戏数据来源

---

<div align="center">
  <p><strong>🎮 来玩守望先锋吗？加入我们的QQ群：710574642</strong></p>
  <p><em>让游戏更有趣，让查询更便捷！</em></p>
</div>
