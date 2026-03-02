# AstrBOT 守望先锋·归来国际服查询插件
作者其实是个小白来的，部分由ai创建，希望各位大神有兴趣可以改吧改吧
# ❗ API似乎出问题了无法查询，高三了没时间排查和修改，大家有兴趣可以自己改，或者说等三个月后考完，我看看怎么个事儿

🎮 **守望先锋·归来国际服查询插件**

[![Version](https://img.shields.io/badge/version-v1.2.1-blue.svg)](https://github.com/TZYCeng/astrbot_plugin_owcx)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.0+-orange.svg)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚀 功能特性
### ✨ 功能
🎮 双模式基础战绩查询 - 支持查询玩家竞技 / 休闲模式基础数据，默认展示 PC 平台数据，可手动指定主机端  
🦸 英雄双模式数据查询 - 默认查询休闲模式英雄数据，支持显式切换竞技模式，覆盖总消灭、场均伤害  
🔗 用户战网绑定 - 绑定个人战网标签，后续可无参数快捷查询，无需重复输入标签  
🛡️ 多角色段位细分 - 单独显示坦克、输出、辅助三角色当前段位及分数范围  
💾 智能缓存降级 - 成功请求数据自动缓存（10 分钟 - 1 小时），请求失败时优先返回历史缓存  
⏱️ 增强超时与异常处理 - API 超时时间延长至 60 秒，500 错误额外重试 1 次；提前初始化变量避免崩溃，超时 / 服务器故障给出引导  
🔧 管理员缓存管理 - 管理员可清理玩家数据缓存或全部缓存，优化插件运行效率  
📋 详细错误引导 - 超时 / 无数据时提示切换模式  
⚡ 异步性能优化 - 并行请求多维度数据（概要 + 竞技 + 休闲），异步处理 API 调用，响应速度提升  

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

## 📝 使用方法
|### 基本命令	                |描述	                                                  |示例                       |
|:---                          |:---                                                     |:---                       |
|/ow绑定 玩家#12345	          |绑定玩家战网标签，后续可无参数查询（默认查休闲模式）	        |/ow绑定 Genji#12345        |
|/ow解绑	                      |解除当前用户绑定的战网账号	                                |/ow解绑                    |
|/ow	                         |查询已绑定账号的基础战绩（含竞技 + 休闲模式，默认 PC 平台）   |/ow                       |
|/ow 玩家#12345	             |直接查询指定玩家的基础战绩（默认 PC 平台，含竞技 + 休闲模式） |/ow Hanzo#67890           |
|/ow 玩家#12345 [pc/console]	 |指定平台查询玩家基础战绩（pc = 电脑端，console = 主机端）	  |/ow Mercy#45678 console   |
|/ow英雄 英雄名	                |（已绑定账号）查询指定英雄的默认休闲模式数据	              |/ow英雄 雾子               |
|/ow英雄 英雄名 竞技/休闲	       |（已绑定账号）显式指定模式查询英雄数据	                    |/ow英雄 源氏 竞技/休闲      |
|/ow英雄 英雄名 玩家#12345	    |（未绑定账号）查询指定玩家的英雄默认休闲模式数据	           |/ow英雄 狂鼠 Tracer#11223  |
|/ow清理缓存	                   |清理玩家数据缓存（默认不清理全部）	                       |/ow清理缓存                | 
|/ow清理缓存 全部	             |清理插件所有缓存（含玩家数据、英雄数据等）	                 |/ow清理缓存 全部           |
|/ow帮助	                      |显示插件所有命令用法、默认模式说明及示例	                    |/ow帮助                   |
|/ow状态	                      |显示插件运行状态（API 连通性、绑定数、缓存量、默认模式等） 	  |/ow状态                   | 

## 🔧 故障排除
### 常见问题
1. **查询失败**
   - 检查战网标签格式是否正确
   - 确保玩家资料是公开的
   - 检查网络连接
   - 是否设置为好友公开导致误判

2. **API错误**
   - 可能是API服务暂时不可用
   - 插件会自动重试，请稍后再试

3. **绑定失败**
   - 确认战网标签格式：玩家#数字
   - 检查是否包含特殊字符

4. **缓存问题**
   - 可以使用 ‘/ow清理缓存 全部’ 重置缓存
   - 在配置中禁用缓存进行测试

## 版本历史
### v1.2.1(当前版本)
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
