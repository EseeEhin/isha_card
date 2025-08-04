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

## 部署到 Hugging Face Spaces

### 环境变量设置

在 HF Spaces 的设置中，需要配置以下环境变量：

1. **DISCORD_TOKEN**: 你的 Discord 机器人 Token
2. **DISCORD_GUILD_ID** (可选): 指定服务器ID以加速指令同步

### 项目结构

```
├── bot.py              # 主机器人代码（包含Flask服务）
├── Dockerfile          # Docker配置
├── requirements.txt    # Python依赖
├── README.md          # 项目说明
├── data/
│   ├── tarot.json     # 塔罗牌数据
│   └── fortune.json   # 运势数据
└── templates/
    ├── index.html     # 主页
    ├── tarot.html     # 塔罗牌管理页
    └── fortune.html   # 运势管理页
```

### 使用方法

#### Discord 指令
- `/tarot` - 抽一张塔罗牌
- `/fortune` - 抽一张今日运势牌

#### 网页管理
部署成功后，访问你的 HF Space URL 即可使用网页管理界面：
- 主页：查看机器人状态
- 管理塔罗牌：修改卡牌解读
- 管理运势：编辑运势内容

## 技术栈

- Python 3.10+
- discord.py
- Flask
- Docker
- Hugging Face Spaces

## 本地开发

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 设置环境变量：
```bash
export DISCORD_TOKEN="你的机器人Token"
```

3. 运行机器人：
```bash
python bot.py
```

4. 访问网页管理界面：
```
http://localhost:7860
```

## 许可证

MIT License 