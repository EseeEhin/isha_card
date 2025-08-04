import os
import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import asyncio
import threading
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

guild_id = os.getenv("DISCORD_GUILD_ID")  # 可选，指定服务器加速指令同步

# Flask 应用
app = Flask(__name__)

class TarotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)
        self.data_dir = os.getenv('HF_DISK_PATH', 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.tarot_file = os.path.join(self.data_dir, 'tarot.json')
        self.fortune_file = os.path.join(self.data_dir, 'fortune.json')

    async def setup_hook(self):
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    def load_data(self, file_path):
        """从JSON文件加载数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_data(self, file_path, data):
        """保存数据到JSON文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

bot = TarotBot()

@bot.event
async def on_ready():
    print(f"已上线: {bot.user}")

# /fortune 指令
@bot.tree.command(name="fortune", description="抽一张今日运势牌")
async def fortune(interaction: discord.Interaction):
    """处理/fortune指令"""
    fortunes = bot.load_data(bot.fortune_file)
    if not fortunes:
        await interaction.response.send_message("抱歉，运势数据正在维护中，请稍后再试。")
        return

    chosen_fortune = random.choice(fortunes)
    
    rating_stars = "★" * chosen_fortune["rating"] + "☆" * (5 - chosen_fortune["rating"])
    
    embed = discord.Embed(
        title="✨ 今日运势 ✨",
        description=f"你抽到了 **{chosen_fortune['fortune']}**！",
        color=discord.Color.gold()
    )
    embed.add_field(name="运势等级", value=rating_stars, inline=False)
    embed.add_field(name="运势解读", value=chosen_fortune["description"], inline=False)
    embed.set_footer(text=f"由 {bot.user.name} 提供")
    
    await interaction.response.send_message(embed=embed)

# /tarot 指令
@bot.tree.command(name="tarot", description="抽一张塔罗牌")
async def tarot(interaction: discord.Interaction):
    """处理/tarot指令"""
    tarot_cards = bot.load_data(bot.tarot_file)
    if not tarot_cards:
        await interaction.response.send_message("抱歉，塔罗牌数据正在维护中，请稍后再试。")
        return
        
    chosen_card = random.choice(tarot_cards)
    orientation = random.choice(['upright', 'reversed']) # 随机选择正位或逆位
    
    orientation_text = "正位" if orientation == 'upright' else "逆位"
    description = chosen_card['description'][orientation]
    card_name_with_orientation = f"{chosen_card['name']} ({orientation_text})"

    # 首先发送卡牌名称
    await interaction.response.send_message(f"你抽到了... **{card_name_with_orientation}**")
    
    # 模拟思考
    await asyncio.sleep(2)
    
    # 然后@用户并发送解读
    await interaction.followup.send(f"{interaction.user.mention} 这是你的卡牌解读：\n\n**{card_name_with_orientation}**\n{description}")

# Flask 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tarot', methods=['GET', 'POST'])
def tarot_web():
    tarot_cards = bot.load_data(bot.tarot_file)
    if request.method == 'POST':
        for card in tarot_cards:
            upright_desc = request.form.get(f'upright_{card["id"]}')
            reversed_desc = request.form.get(f'reversed_{card["id"]}')
            if upright_desc and reversed_desc:
                card['description']['upright'] = upright_desc
                card['description']['reversed'] = reversed_desc
        bot.save_data(bot.tarot_file, tarot_cards)
        return redirect(url_for('tarot_web'))
    return render_template('tarot.html', tarot_cards=tarot_cards)

@app.route('/fortune', methods=['GET', 'POST'])
def fortune_web():
    fortunes = bot.load_data(bot.fortune_file)
    if request.method == 'POST':
        for item in fortunes:
            new_description = request.form.get(f'description_{item["id"]}')
            if new_description:
                item['description'] = new_description
        bot.save_data(bot.fortune_file, fortunes)
        return redirect(url_for('fortune_web'))
    return render_template('fortune.html', fortunes=fortunes)

def run_flask():
    """在单独的线程中运行Flask"""
    app.run(host='0.0.0.0', port=7860, debug=False)

def run_bot():
    """运行Discord机器人"""
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("请设置环境变量 DISCORD_TOKEN")
    else:
        bot.run(TOKEN)

if __name__ == "__main__":
    # 启动Flask服务器在后台线程
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 启动Discord机器人
    run_bot() 