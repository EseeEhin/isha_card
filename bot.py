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
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import math

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

def create_fortune_image(fortune_data: dict):
    """根据运势数据生成一张图片"""
    # --- 资源路径 ---
    base_path = 'static'
    font_path = os.path.join(base_path, 'fonts', 'font.ttf')
    default_bg_path = os.path.join(base_path, 'images', 'default_background.png')
    
    # --- 图像尺寸和颜色 ---
    img_width, img_height = 800, 600
    text_color = (255, 255, 255)
    shadow_color = (0, 0, 0)

    # --- 加载背景 ---
    bg_path = fortune_data.get("image", default_bg_path)
    if not os.path.exists(bg_path):
        bg_path = default_bg_path
    
    try:
        background = Image.open(bg_path).convert("RGBA").resize((img_width, img_height))
    except FileNotFoundError:
        logger.warning(f"Background image not found at {bg_path}, creating a placeholder background.")
        # Create a gradient background if default is not found
        background = Image.new("RGBA", (img_width, img_height))
        draw = ImageDraw.Draw(background)
        for i in range(img_height):
            # A simple dark blue/purple gradient
            color = (20 + i // 10, 15 + i // 12, 40 + i // 8)
            draw.line([(0, i), (img_width, i)], fill=color)

    draw = ImageDraw.Draw(background)

    # --- 加载字体 ---
    try:
        font_large = ImageFont.truetype(font_path, 60)
        font_medium = ImageFont.truetype(font_path, 28)
        font_small = ImageFont.truetype(font_path, 22)
    except IOError:
        logger.warning(f"Font file not found at {font_path}, using default font.")
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # --- 绘制星星 ---
    star_shape = fortune_data.get("star_shape", "star")
    star_filled_path = os.path.join(base_path, 'images', f'{star_shape}_filled.png')
    star_empty_path = os.path.join(base_path, 'images', f'{star_shape}_empty.png')
    
    # --- Star Drawing Logic ---
    stars_count = fortune_data.get("stars", 0)
    total_stars = 7
    star_y = 300
    star_size = 50
    star_spacing = 5
    total_star_width = total_stars * (star_size + star_spacing)
    star_x_start = (img_width - total_star_width) // 2

    try:
        # Try to load images first
        star_filled_img = Image.open(star_filled_path).convert("RGBA").resize((star_size, star_size))
        star_empty_img = Image.open(star_empty_path).convert("RGBA").resize((star_size, star_size))

        for i in range(total_stars):
            star_to_paste = star_filled_img if i < stars_count else star_empty_img
            x_pos = star_x_start + i * (star_size + star_spacing)
            background.paste(star_to_paste, (x_pos, star_y), star_to_paste)

    except FileNotFoundError:
        logger.warning(f"Star images for '{star_shape}' not found. Drawing placeholder shapes.")
        # Fallback to drawing shapes if images are missing
        for i in range(total_stars):
            x_pos = star_x_start + i * (star_size + star_spacing) + star_size // 2
            y_pos = star_y + star_size // 2
            is_filled = i < stars_count
            
            fill_color = (255, 223, 0) if is_filled else None
            outline_color = (255, 223, 0)
            
            # Simple placeholder drawing logic
            if "star" in star_shape:
                # Draw a 5-pointed star
                points = []
                for k in range(10):
                    angle_deg = -90 + k * 36  # Start from top
                    angle_rad = math.radians(angle_deg)
                    r = star_size / 2 if k % 2 == 0 else star_size / 4
                    points.append((x_pos + r * math.cos(angle_rad), y_pos + r * math.sin(angle_rad)))
                draw.polygon(points, fill=fill_color, outline=outline_color)
            elif "heart" in star_shape:
                # Draw a heart
                draw.ellipse((x_pos - star_size//4, y_pos - star_size//4, x_pos + star_size//4, y_pos + star_size//4), fill=fill_color, outline=outline_color, width=2)
            else: # Default to circles
                radius = star_size // 2 - 2
                if is_filled:
                    draw.ellipse((x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius), fill=fill_color, outline=outline_color)
                else:
                    draw.ellipse((x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius), outline=outline_color, width=2)


    # --- 绘制运势等级和标签 ---
    level_text = fortune_data.get("level", "")
    tags_text = " | ".join(fortune_data.get("tags", []))
    combined_text = f"{level_text} - {tags_text}"
    
    text_y = 380
    draw.text((img_width / 2, text_y + 2), combined_text, font=font_medium, fill=shadow_color, anchor="ms")
    draw.text((img_width / 2, text_y), combined_text, font=font_medium, fill=text_color, anchor="ms")

# --- 绘制描述 ---
    description = fortune_data.get("description", "")
    # A bit more robust wrapping
    wrapped_text = ""
    if font_small.getsize("a")[0] > 0: # Check if font is not default
        avg_char_width = font_small.getsize("A")[0]
        wrap_width = (img_width - 100) // avg_char_width
        wrapped_text = textwrap.fill(description, width=wrap_width if wrap_width > 0 else 45)
    else: # Fallback for default font
        wrapped_text = textwrap.fill(description, width=45)

    desc_y = 440
    draw.text((img_width / 2, desc_y + 2), wrapped_text, font=font_small, fill=shadow_color, anchor="ms", align="center")
    draw.text((img_width / 2, desc_y), wrapped_text, font=font_small, fill=text_color, anchor="ms", align="center")

    # --- 保存到内存 ---
    img_byte_arr = io.BytesIO()
    background.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr

# /fortune 指令
@bot.tree.command(name="运势", description="抽一张今日运势牌")
async def fortune(interaction: discord.Interaction):
    try:
        await interaction.response.defer() # 延迟响应，因为图片生成可能需要时间

        fortunes = bot.load_data(bot.fortune_file)
        if not fortunes:
            await interaction.followup.send("抱歉，运势数据正在维护中，请稍后再试。")
            return

        chosen_fortune = random.choice(fortunes)
        
        # 生成图片
        image_file_bytes = create_fortune_image(chosen_fortune)
        
        # 创建 discord.File 对象
        picture = discord.File(fp=image_file_bytes, filename="fortune.png")
        
        # 发送消息
        message = f"喵~ {interaction.user.mention}，来看看你的今日运势吧！"
        await interaction.followup.send(message, file=picture)

    except Exception as e:
        logger.error(f"Error in fortune command: {e}")
        await interaction.followup.send("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

# --- 调试指令 ---

@bot.tree.command(name="debug_fortune", description="[仅管理员] 抽取指定的运势牌")
@app_commands.rename(fortune_id="运势id")
@app_commands.describe(fortune_id="请选择要抽取的运势牌")
@app_commands.checks.has_permissions(administrator=True)
async def debug_fortune(interaction: discord.Interaction, fortune_id: int):
    try:
        await interaction.response.defer(ephemeral=True)

        fortunes = bot.load_data(bot.fortune_file)
        chosen_fortune = next((f for f in fortunes if f['id'] == fortune_id), None)

        if not chosen_fortune:
            await interaction.followup.send(f"未找到ID为 {fortune_id} 的运势。", ephemeral=True)
            return

        image_file_bytes = create_fortune_image(chosen_fortune)
        picture = discord.File(fp=image_file_bytes, filename=f"fortune_{fortune_id}.png")
        await interaction.followup.send(f"调试抽取运势: **{chosen_fortune['level']}**", file=picture, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in debug_fortune command: {e}")
        await interaction.followup.send("生成调试运势图时出错。", ephemeral=True)

@debug_fortune.autocomplete('fortune_id')
async def debug_fortune_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    fortunes = bot.load_data(bot.fortune_file)
    choices = [
        app_commands.Choice(name=f"({item['stars']}★) {item['level']}", value=item['id'])
        for item in fortunes if current.lower() in item['level'].lower() or str(item['id']) == current
    ]
    return choices[:25]

@bot.tree.command(name="debug_tarot", description="[仅管理员] 抽取指定的塔罗牌")
@app_commands.rename(card_id="塔罗牌id", orientation="正逆位")
@app_commands.describe(card_id="请选择要抽取的塔罗牌", orientation="选择正位或逆位")
@app_commands.choices(orientation=[
    app_commands.Choice(name="正位", value="upright"),
    app_commands.Choice(name="逆位", value="reversed")
])
@app_commands.checks.has_permissions(administrator=True)
async def debug_tarot(interaction: discord.Interaction, card_id: int, orientation: str):
    try:
        await interaction.response.defer(ephemeral=True)
        tarot_cards = bot.load_data(bot.tarot_file)
        chosen_card = next((c for c in tarot_cards if c['id'] == card_id), None)

        if not chosen_card:
            await interaction.followup.send(f"未找到ID为 {card_id} 的塔罗牌。", ephemeral=True)
            return

        orientation_text = "正位" if orientation == 'upright' else "逆位"
        description = chosen_card['description'][orientation]
        card_name_with_orientation = f"{chosen_card['name']} ({orientation_text})"

        embed = discord.Embed(
            title=f"调试抽取... {card_name_with_orientation}",
            description=f"**牌面解读:**\n{description}",
            color=discord.Color.blue()
        )
        
        image_url = chosen_card.get("image")
        if image_url:
            if not image_url.startswith('http'):
                 base_url = os.getenv("BASE_URL", "http://localhost:7860")
                 image_url = f"{base_url}/{image_url}"
            embed.set_image(url=image_url)
            
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in debug_tarot command: {e}")
        await interaction.followup.send("生成调试塔罗牌时出错。", ephemeral=True)

@debug_tarot.autocomplete('card_id')
async def debug_tarot_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    tarot_cards = bot.load_data(bot.tarot_file)
    choices = [
        app_commands.Choice(name=card['name'], value=card['id'])
        for card in tarot_cards if current.lower() in card['name'].lower() or str(card['id']) == current
    ]
    return choices[:25]


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
