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
import logging
import logging.handlers
from werkzeug.utils import secure_filename

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设置操作日志
op_log_dir = 'logs'
os.makedirs(op_log_dir, exist_ok=True)
op_log_file = os.path.join(op_log_dir, 'operations.log')
op_logger = logging.getLogger('operations')
op_logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(op_log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
op_logger.addHandler(handler)

# 加载环境变量
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Flask 应用
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class TarotBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)
        self.data_dir = os.getenv('HF_DISK_PATH', 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        self.tarot_file = os.path.join(self.data_dir, 'tarot.json')
        self.fortune_file = os.path.join(self.data_dir, 'fortune.json')

    async def setup_hook(self):
        try:
            guild_ids_str = os.getenv("DISCORD_GUILD_ID")
            if guild_ids_str:
                guild_ids = [int(gid.strip()) for gid in guild_ids_str.split(',') if gid.strip()]
                for gid in guild_ids:
                    try:
                        guild = discord.Object(id=gid)
                        self.tree.copy_global_to(guild=guild)
                        await self.tree.sync(guild=guild)
                        logger.info(f"Synced commands to guild: {gid}")
                    except Exception as e:
                        logger.error(f"Failed to sync commands to guild {gid}: {e}")
            else:
                await self.tree.sync()
                logger.info("Synced commands globally")
        except Exception as e:
            logger.error(f"Error in setup_hook: {e}")

    def load_data(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load {file_path}: {e}")
            return []

    def save_data(self, file_path, data):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Data saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving data to {file_path}: {e}")

bot = TarotBot()

@bot.event
async def on_ready():
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    logger.info(f"Bot ID: {bot.user.id}")
    logger.info(f"Connected to {len(bot.guilds)} guilds")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {args} {kwargs}")

# /fortune 指令
@bot.tree.command(name="运势", description="抽一张今日运势牌")
async def fortune(interaction: discord.Interaction):
    try:
        fortunes = bot.load_data(bot.fortune_file)
        if not fortunes:
            await interaction.response.send_message("抱歉，运势数据正在维护中，请稍后再试。")
            return

        chosen_fortune = random.choice(fortunes)
        
        if "吉" in chosen_fortune["level"] or "高照" in chosen_fortune["level"]:
            color = discord.Color.gold()
        elif "厄" in chosen_fortune["level"] or "笼罩" in chosen_fortune["level"]:
            color = discord.Color.dark_purple()
        else:
            color = discord.Color.light_grey()

        star_icons = {'heart': '❤️', 'coin': '💰', 'star': '✨', 'thorn': '🥀', 'skull': '💀'}
        star_symbol = star_icons.get(chosen_fortune.get("star_shape", "star"), '✨')
        stars_display = star_symbol * chosen_fortune["stars"] + '🖤' * (7 - chosen_fortune["stars"])

        embed = discord.Embed(
            title=f"血族猫娘的今日占卜",
            description=f"喵~ {interaction.user.mention}，来看看你的今日运势吧！",
            color=color
        )
        
        embed.add_field(name="今日运势", value=f"**{chosen_fortune['level']}**", inline=False)
        embed.add_field(name="幸运星", value=stars_display, inline=False)
        
        if chosen_fortune.get("tags"):
            tags = " | ".join([f"`{tag}`" for tag in chosen_fortune["tags"]])
            embed.add_field(name="运势标签", value=tags, inline=False)
            
        embed.add_field(name="血族猫娘的低语", value=chosen_fortune["description"], inline=False)
        
        image_path = chosen_fortune.get("image")
        if image_path:
            if image_path.startswith('http'):
                image_url = image_path
            elif os.path.exists(image_path):
                image_filename = os.path.basename(image_path)
                base_url = os.getenv("BASE_URL", "http://localhost:7860") 
                image_url = f"{base_url}/{image_path}"
                embed.set_image(url=image_url)
        
        embed.set_footer(text=f"来自暗影与月光下的祝福 | {bot.user.name}")
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Error in fortune command: {e}")
        await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

# /tarot 指令
@bot.tree.command(name="塔罗", description="抽一张塔罗牌")
async def tarot(interaction: discord.Interaction):
    try:
        tarot_cards = bot.load_data(bot.tarot_file)
        if not tarot_cards:
            await interaction.response.send_message("抱歉，塔罗牌数据正在维护中，请稍后再试。")
            return
            
        chosen_card = random.choice(tarot_cards)
        orientation = random.choice(['upright', 'reversed'])
        
        orientation_text = "正位" if orientation == 'upright' else "逆位"
        description = chosen_card['description'][orientation]
        card_name_with_orientation = f"{chosen_card['name']} ({orientation_text})"

        embed = discord.Embed(
            title=f"你抽到了... {card_name_with_orientation}",
            description=f"**牌面解读:**\n{description}",
            color=discord.Color.purple()
        )
        
        image_url = chosen_card.get("image")
        if image_url:
            if not image_url.startswith('http'):
                 base_url = os.getenv("BASE_URL", "http://localhost:7860")
                 image_url = f"{base_url}/{image_url}"
            embed.set_image(url=image_url)
            
        embed.set_footer(text=f"由 {bot.user.name} 提供给 {interaction.user.name}")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Error in tarot command: {e}")
        await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

# --- 管理指令 ---

@bot.tree.command(name="更新塔罗图片", description="更新指定塔罗牌的卡面图片")
@app_commands.rename(card_id="塔罗牌", url="链接")
@app_commands.describe(card_id="请选择要更新的塔罗牌", url="新的图片URL")
async def update_tarot_image(interaction: discord.Interaction, card_id: int, url: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("抱歉，只有服务器管理员才能使用此命令。", ephemeral=True)
        return
    
    try:
        tarot_cards = bot.load_data(bot.tarot_file)
        card_to_update = next((c for c in tarot_cards if c['id'] == card_id), None)

        if not card_to_update:
            await interaction.response.send_message(f"未找到ID为 {card_id} 的塔罗牌。", ephemeral=True)
            return

        old_url = card_to_update.get("image", "")
        card_to_update["image"] = url
        bot.save_data(bot.tarot_file, tarot_cards)

        log_message = f"User '{interaction.user}' (ID: {interaction.user.id}) updated image for Tarot (ID: {card_id}, Name: {card_to_update['name']}): from '{old_url}' to '{url}'"
        op_logger.info(log_message)

        embed = discord.Embed(title="🖼️ 塔罗牌图片更新成功", description=f"已成功更新 **{card_to_update['name']}** 的图片。", color=discord.Color.green())
        if url:
            embed.set_image(url=url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in update_tarot_image command: {e}")
        await interaction.response.send_message("更新过程中出现错误，请检查日志。", ephemeral=True)

@update_tarot_image.autocomplete('card_id')
async def tarot_card_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    tarot_cards = bot.load_data(bot.tarot_file)
    choices = [
        app_commands.Choice(name=card['name'], value=card['id'])
        for card in tarot_cards if current.lower() in card['name'].lower()
    ]
    return choices[:25]

@bot.tree.command(name="更新运势图片", description="更新指定运势的图片")
@app_commands.rename(fortune_id="运势", url="链接")
@app_commands.describe(fortune_id="请选择要更新的运势", url="新的图片URL")
async def update_fortune_image(interaction: discord.Interaction, fortune_id: int, url: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("抱歉，只有服务器管理员才能使用此命令。", ephemeral=True)
        return

    try:
        fortunes = bot.load_data(bot.fortune_file)
        fortune_to_update = next((f for f in fortunes if f['id'] == fortune_id), None)

        if not fortune_to_update:
            await interaction.response.send_message(f"未找到ID为 {fortune_id} 的运势。", ephemeral=True)
            return

        old_url = fortune_to_update.get("image", "")
        fortune_to_update["image"] = url
        bot.save_data(bot.fortune_file, fortunes)

        log_message = f"User '{interaction.user}' (ID: {interaction.user.id}) updated image for Fortune (ID: {fortune_id}, Name: {fortune_to_update['level']}): from '{old_url}' to '{url}'"
        op_logger.info(log_message)

        embed = discord.Embed(title="🖼️ 运势图片更新成功", description=f"已成功更新 **{fortune_to_update['level']}** 的图片。", color=discord.Color.green())
        if url:
            embed.set_image(url=url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in update_fortune_image command: {e}")
        await interaction.response.send_message("更新过程中出现错误，请检查日志。", ephemeral=True)

@update_fortune_image.autocomplete('fortune_id')
async def fortune_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    fortunes = bot.load_data(bot.fortune_file)
    choices = [
        app_commands.Choice(name=f"({item['stars']}★) {item['level']}", value=item['id'])
        for item in fortunes if current.lower() in item['level'].lower()
    ]
    return choices[:25]

# --- Flask 路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return {"status": "healthy", "bot_ready": bot.is_ready() if hasattr(bot, 'is_ready') else False}

@app.route('/tarot', methods=['GET', 'POST'])
def tarot_web():
    try:
        tarot_cards = bot.load_data(bot.tarot_file)
        if request.method == 'POST':
            for card in tarot_cards:
                upright_desc = request.form.get(f'upright_{card["id"]}')
                if upright_desc is not None:
                    card['description']['upright'] = upright_desc
                
                reversed_desc = request.form.get(f'reversed_{card["id"]}')
                if reversed_desc is not None:
                    card['description']['reversed'] = reversed_desc

                file_key = f'image_upload_{card["id"]}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"tarot_{card['id']}{os.path.splitext(file.filename)[1]}")
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(save_path)
                        card['image'] = os.path.join(UPLOAD_FOLDER, filename).replace(os.path.sep, '/')
            
            bot.save_data(bot.tarot_file, tarot_cards)
            return redirect(url_for('tarot_web'))
        return render_template('tarot.html', tarot_cards=tarot_cards)
    except Exception as e:
        logger.error(f"Error in tarot_web: {e}")
        return "Error loading tarot data", 500

@app.route('/fortune', methods=['GET', 'POST'])
def fortune_web():
    try:
        fortunes = bot.load_data(bot.fortune_file)
        if request.method == 'POST':
            updated_fortunes = []
            for i in range(len(fortunes)):
                item_id = int(request.form.get(f'id_{i}'))
                item = next((f for f in fortunes if f['id'] == item_id), None)
                if not item:
                    continue

                item['level'] = request.form.get(f'level_{item_id}', item['level'])
                tags_str = request.form.get(f'tags_{item_id}', '')
                item['tags'] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                item['stars'] = int(request.form.get(f'stars_{item_id}', item['stars']))
                item['star_shape'] = request.form.get(f'star_shape_{item_id}', item['star_shape'])
                item['description'] = request.form.get(f'description_{item_id}', item['description'])

                file_key = f'image_upload_{item_id}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"fortune_bg_{item_id}{os.path.splitext(file.filename)[1]}")
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(save_path)
                        item['image'] = os.path.join(UPLOAD_FOLDER, filename).replace(os.path.sep, '/')
                
                updated_fortunes.append(item)

            existing_ids = {f['id'] for f in updated_fortunes}
            for f in fortunes:
                if f['id'] not in existing_ids:
                    updated_fortunes.append(f)

            bot.save_data(bot.fortune_file, updated_fortunes)
            return redirect(url_for('fortune_web'))
            
        return render_template('fortune.html', fortunes=fortunes)
    except Exception as e:
        logger.error(f"Error in fortune_web: {e}")
        return "Error loading fortune data", 500

def run_flask():
    try:
        logger.info("Starting Flask server on port 7860")
        app.run(host='0.0.0.0', port=7860, debug=False)
    except Exception as e:
        logger.error(f"Error starting Flask: {e}")

def run_bot():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("DISCORD_TOKEN environment variable is not set!")
        return
    
    logger.info("Starting Discord bot...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    logger.info("Starting application...")
    
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started in background")
    
    run_bot()
