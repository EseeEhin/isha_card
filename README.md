---
title: Discord Tarot Bot
emoji: 🎴
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: false
app_file: bot.py
---

# Discord 抽卡机器人

一个功能丰富的 Discord 机器人，提供塔罗牌抽卡和今日运势功能，支持网页管理界面。

## 功能特性

### 🎴 塔罗牌抽卡 (`/tarot`)
- 随机抽取大阿卡纳22张牌
- 支持正位和逆位解读
- 详细的卡牌含义说明

### ✨ 今日运势 (`/fortune`)
- 随机抽取今日运势
- 星级评分系统
- 个性化运势解读

### 🌐 网页管理界面
- 实时修改塔罗牌解读
- 编辑运势内容
- 无需重启机器人，修改即时生效

## 使用方法

### Discord 指令
- `/tarot` - 抽一张塔罗牌
- `/fortune` - 抽一张今日运势牌

### 网页管理
访问此 Space 的 URL 即可使用网页管理界面：
- 主页：查看机器人状态
- 管理塔罗牌：修改卡牌解读
- 管理运势：编辑运势内容

## 技术栈

- Python 3.10+
- discord.py
- Flask
- Docker
- Hugging Face Spaces

## 环境变量

需要在 HF Spaces 设置中配置：
- `DISCORD_TOKEN`: Discord 机器人 Token
- `DISCORD_GUILD_ID` (可选): Discord 服务器 ID 