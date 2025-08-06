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

一个功能丰富的 Discord 机器人，提供塔罗牌抽卡和今日运势功能，并配有网页管理界面。项目经过模块化重构，更易于维护和扩展。

## 🔮 功能特性

- **🎴 塔罗牌占卜 (`/tarot`)**: 随机抽取一张塔罗牌，并提供正逆位解读。
- **✨ 每日运势 (`/fortune`)**: 获取你今天的专属运势，包含幸运星级和趣味解读。
- **🖼️ 图片管理**: 管理员可以通过指令 (`/更新塔罗图片`, `/更新运势图片`) 直接在 Discord 中更新卡牌和运势背景图。
- **🌐 网页管理后台**:
  - 实时编辑塔罗牌和运势的文本内容。
  - 上传和管理卡牌图片。
  - 修改即时生效，无需重启服务。

## 🚀 技术栈与架构

- **Python 3.10+**
- **discord.py**: 核心机器人框架。
- **Flask (Waitress)**: 提供稳定的 Web 服务。
- **模块化设计**:
  - `bot.py`: 应用主入口，负责启动和协调。
  - `cogs/`: 存放机器人指令模块 (Cogs)，如 `tarot_cog.py` 和 `fortune_cog.py`。
  - `utils/`: 存放通用工具，如 `logger.py` 和 `data_manager.py`。
  - `web/`: 存放 Flask 网页应用和路由。
  - `templates/` & `static/`: 网页模板和静态文件。
  - `data/`: 存放 `tarot.json` 和 `fortune.json` 数据文件。

## 🛠️ 如何部署与使用

### 环境变量

在 Hugging Face Spaces 或你的部署环境中，设置以下环境变量：

- `DISCORD_TOKEN`: **必需**，你的 Discord 机器人 Token。
- `DISCORD_GUILD_ID`: (可选) 你的 Discord 服务器 ID。如果设置，指令将只在该服务器内快速同步，适合开发测试。如果留空，指令将全局同步。
- `BASE_URL`: (可选) 你的 Web 服务公开访问地址，用于拼接图片 URL。默认为 `http://localhost:7860`。
- `HF_DISK_PATH`: (可选) Hugging Face 持久化存储路径，默认为 `data`。

### 本地运行

1.  克隆仓库:
    ```bash
    git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
    cd YOUR_SPACE_NAME
    ```
2.  创建并激活虚拟环境:
    ```bash
    python -m venv venv
    source venv/bin/activate  # on Windows, use `venv\Scripts\activate`
    ```
3.  安装依赖:
    ```bash
    pip install -r requirements.txt
    ```
4.  创建 `.env` 文件并填入你的环境变量:
    ```
    DISCORD_TOKEN="YOUR_DISCORD_TOKEN"
    DISCORD_GUILD_ID="YOUR_GUILD_ID"
    ```
5.  运行机器人:
    ```bash
    python bot.py
    ```

### 网页管理

部署后，访问你的服务 URL (例如 `https://your-space-name.hf.space`) 即可进入管理后台。

- **管理塔罗牌**: `.../tarot`
- **管理运势**: `.../fortune`
