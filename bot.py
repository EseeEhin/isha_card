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
import requests
import hashlib

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
def generate_fortune_card(level, tags, text, image_path):
    try:
        # --- 字体加载（绝对路径 + 强化调试日志）---
        base_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(base_dir, 'static', 'fonts', 'SourceHanSans.otf')
        
        # 强化日志，用于最终调试
        logger.info(f"--- Font Loading Debug ---")
        logger.info(f"Script base directory: {base_dir}")
        logger.info(f"Calculated font absolute path: {font_path}")
        logger.info(f"Does font file exist at path? -> {os.path.exists(font_path)}")
        logger.info(f"--- End Debug ---")

        try:
            font_bold = ImageFont.truetype(font_path, 36)
            font_regular = ImageFont.truetype(font_path, 24)
            font_small = ImageFont.truetype(font_path, 20)
        except IOError as e:
            logger.error(f"CRITICAL: Failed to load font from {font_path}. Error: {e}. Falling back to default font.")
            font_bold = ImageFont.load_default()
            font_regular = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # --- 图片缓存逻辑 ---
        cache_dir = os.path.join('static', 'image_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        local_image_path = image_path
        if image_path.startswith('http'):
            # 根据URL生成一个安全的文件名
            url_hash = hashlib.sha1(image_path.encode()).hexdigest()
            file_extension = os.path.splitext(image_path.split('?')[0])[-1] or '.png' # 保留原始扩展名
            cached_filename = f"{url_hash}{file_extension}"
            local_image_path = os.path.join(cache_dir, cached_filename)

            # 如果缓存文件不存在，则下载
            if not os.path.exists(local_image_path):
                response = requests.get(image_path, stream=True)
                response.raise_for_status()
                with open(local_image_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
        
        # 打开背景图 (无论是本地路径还是缓存路径)
        bg_image = Image.open(local_image_path).convert("RGBA")
        # 创建一个半透明的黑色遮罩
        overlay = Image.new("RGBA", bg_image.size, (0, 0, 0, 80))
        # 将遮罩叠加到背景图上
        image = Image.alpha_composite(bg_image, overlay)
        draw = ImageDraw.Draw(image)

        # --- 绘制文本 ---
        text_color = (255, 255, 255)
        shadow_color = (0, 0, 0)
        
        def draw_text_with_shadow(position, text, font, fill, shadow_fill):
            x, y = position
            # 绘制阴影
            draw.text((x+2, y+2), text, font=font, fill=shadow_fill)
            # 绘制文本
            draw.text((x, y), text, font=font, fill=fill)

        # 1. 绘制运势等级
        level_text = f"今日运势: {level['level_name']}"
        draw_text_with_shadow((40, 40), level_text, font_bold, text_color, shadow_color)

        # 2. 绘制星星
        star_icons = {'heart': '❤️', 'coin': '💰', 'star': '✨', 'thorn': '🥀', 'skull': '💀'}
        star_symbol = star_icons.get(level.get("star_shape", "star"), '✨')
        stars_display = star_symbol * level['stars'] + '🖤' * (7 - level['stars'])
        draw_text_with_shadow((40, 90), f"幸运星: {stars_display}", font_regular, text_color, shadow_color)

        # 3. 绘制标签
        tags_str = " | ".join([f"#{t}" for t in tags])
        draw_text_with_shadow((40, 140), "运势标签:", font_regular, text_color, shadow_color)
        draw_text_with_shadow((40, 175), tags_str, font_small, text_color, shadow_color)

        # 4. 绘制低语
        draw_text_with_shadow((40, 230), "血族猫娘的低语:", font_regular, text_color, shadow_color)
        wrapped_text = textwrap.fill(text, width=35) # 假设图片宽度适合35个字符
        draw_text_with_shadow((40, 265), wrapped_text, font_small, text_color, shadow_color)

        # 将图片保存到内存
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return discord.File(img_byte_arr, filename="fortune_card.png")

    except Exception as e:
        logger.error(f"Error generating fortune card: {e}")
        return None

@bot.tree.command(name="运势", description="抽一张今日运势牌")
async def fortune(interaction: discord.Interaction):
    try:
        fortune_data = bot.load_data(bot.fortune_file)
        if not all(k in fortune_data for k in ["levels", "tag_pools", "connectors"]):
            await interaction.response.send_message("抱歉，运势数据结构不正确，请检查 `fortune.json`。")
            return

        # 1. 随机选择一个运势等级
        chosen_level = random.choice(fortune_data["levels"])
        stars = chosen_level.get("stars", 3)

        # 2. 根据星级决定运势类型和标签池
        tag_pools = fortune_data.get("tag_pools", {})
        good_pool = tag_pools.get("good", [])
        bad_pool = tag_pools.get("bad", [])
        neutral_pool = tag_pools.get("neutral", [])
        
        luck_type = "neutral"
        if stars >= 5: luck_type = "good"
        elif stars <= 2: luck_type = "bad"

        # 3. 模块化抽取标签和文本（新逻辑）
        selected_tag_objects = []
        total_tags = random.randint(1, 5)

        # 首先，根据运势类型选择一个基础标签
        base_pool = []
        if luck_type == "good":
            base_pool = good_pool
        elif luck_type == "bad":
            base_pool = bad_pool
        else: # neutral
            base_pool = neutral_pool
        
        if base_pool:
            selected_tag_objects.append(random.choice(base_pool))

        # 然后，抽取额外的中性标签，直到达到目标数量
        num_additional_tags = total_tags - len(selected_tag_objects)
        if num_additional_tags > 0 and neutral_pool:
            existing_ids = {t['id'] for t in selected_tag_objects}
            # 筛选出可用的中性标签
            drawable_neutral_pool = [t for t in neutral_pool if t['id'] not in existing_ids]
            
            # 确保抽取的数量不超过可用标签的数量
            num_to_draw = min(num_additional_tags, len(drawable_neutral_pool))

            if num_to_draw > 0:
                additional_tags = random.sample(drawable_neutral_pool, k=num_to_draw)
                selected_tag_objects.extend(additional_tags)

        # 4. 拼接最终描述
        tags_to_display = [obj['tag'] for obj in selected_tag_objects]
        text_fragments = [obj['text'] for obj in selected_tag_objects]
        
        connectors = fortune_data.get("connectors", {})
        
        # 从列表中随机选择连接语
        intro_options = connectors.get("intro", [""])
        intro = random.choice(intro_options) if intro_options else ""

        outro_options = connectors.get(f"outro_{luck_type}", [""])
        outro = random.choice(outro_options) if outro_options else ""
        
        # 确保结尾标点符号正确
        final_text = intro + " " + "".join(text_fragments).strip().rstrip('，').rstrip('。').rstrip(',') + "。"
        if outro:
            final_text += " " + outro

        # 5. 构建 Embed
        level_name = chosen_level["level_name"]
        color = discord.Color.light_grey()
        if luck_type == "good": color = discord.Color.gold()
        elif luck_type == "bad": color = discord.Color.dark_purple()

        star_icons = {'heart': '❤️', 'coin': '💰', 'star': '✨', 'thorn': '🥀', 'skull': '💀'}
        star_symbol = star_icons.get(chosen_level.get("star_shape", "star"), '✨')
        stars_display = star_symbol * stars + '🖤' * (7 - stars)

        # 随机化 Embed 内容
        titles = [
            "血族猫娘的今日占卜",
            "来自暗影与月光下的祝福",
            "今日运势指引",
            "喵~ 你的今日份好运！"
        ]
        descriptions = [
            f"喵~ {interaction.user.mention}，来看看你的今日运势吧！",
            f"你好呀，{interaction.user.mention}！这是给你的今日占卜。",
            f"{interaction.user.mention}，月光为你洒下今天的启示。",
            f"嗨，{interaction.user.mention}，看看今天有什么在等着你？"
        ]
        footers = [
            f"来自暗影与月光下的祝福 | {bot.user.name}",
            f"由 {bot.user.name} 为你占卜",
            "愿星光指引你的道路",
            "血族猫娘的神秘低语"
        ]

        # --- 新的流程：生成并发送图片 ---
        image_path = chosen_level.get("image")
        generated_card_file = None

        # 尝试生成图片，如果 image_path 存在
        if image_path:
            generated_card_file = generate_fortune_card(chosen_level, tags_to_display, final_text, image_path)

        if generated_card_file:
            # 如果图片生成成功，创建一个简单的 embed 并附上图片
            embed = discord.Embed(
                title=random.choice(titles),
                description=random.choice(descriptions),
                color=color
            )
            embed.set_image(url="attachment://fortune_card.png")
            embed.set_footer(text=random.choice(footers))
            await interaction.response.send_message(embed=embed, file=generated_card_file)
        else:
            # 如果图片生成失败或没有图片路径，回退到纯文本 embed
            embed = discord.Embed(
                title=random.choice(titles),
                description=random.choice(descriptions),
                color=color
            )
            embed.add_field(name="今日运势", value=f"**{level_name}**", inline=False)
            embed.add_field(name="幸运星", value=stars_display, inline=False)
            if tags_to_display:
                tags_display_str = " | ".join([f"`{tag}`" for tag in tags_to_display])
                embed.add_field(name="运势标签", value=tags_display_str, inline=False)
            embed.add_field(name="血族猫娘的低语", value=final_text, inline=False)
            embed.set_footer(text=random.choice(footers))
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

@bot.tree.command(name="更新运势图片", description="更新指定运势等级的背景图片")
@app_commands.rename(level_id="运势等级", url="链接")
@app_commands.describe(level_id="请选择要更新的运势等级", url="新的图片URL")
async def update_fortune_image(interaction: discord.Interaction, level_id: int, url: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("抱歉，只有服务器管理员才能使用此命令。", ephemeral=True)
        return

    try:
        fortune_data = bot.load_data(bot.fortune_file)
        level_to_update = next((l for l in fortune_data['levels'] if l['id'] == level_id), None)

        if not level_to_update:
            await interaction.response.send_message(f"未找到ID为 {level_id} 的运势等级。", ephemeral=True)
            return

        old_url = level_to_update.get("image", "")
        level_to_update["image"] = url
        bot.save_data(bot.fortune_file, fortune_data)

        log_message = f"User '{interaction.user}' (ID: {interaction.user.id}) updated image for Fortune Level (ID: {level_id}, Name: {level_to_update['level_name']}): from '{old_url}' to '{url}'"
        op_logger.info(log_message)

        embed = discord.Embed(title="🖼️ 运势图片更新成功", description=f"已成功更新 **{level_to_update['level_name']}** 的图片。", color=discord.Color.green())
        if url:
            embed.set_image(url=url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in update_fortune_image command: {e}")
        await interaction.response.send_message("更新过程中出现错误，请检查日志。", ephemeral=True)

@update_fortune_image.autocomplete('level_id')
async def fortune_level_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    fortune_data = bot.load_data(bot.fortune_file)
    choices = [
        app_commands.Choice(name=f"({level['stars']}★) {level['level_name']}", value=level['id'])
        for level in fortune_data.get('levels', []) if current.lower() in level['level_name'].lower()
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
        fortune_data = bot.load_data(bot.fortune_file)
        if request.method == 'POST':
            form_type = request.form.get('form_type')

            if form_type == 'connectors':
                fortune_data['connectors']['intro'] = request.form.get('intro')
                fortune_data['connectors']['outro_good'] = request.form.get('outro_good')
                fortune_data['connectors']['outro_neutral'] = request.form.get('outro_neutral')
                fortune_data['connectors']['outro_bad'] = request.form.get('outro_bad')

            elif form_type == 'edit_pool':
                pool_name = request.form.get('pool_name')
                if pool_name in fortune_data['tag_pools']:
                    if 'delete_tag' in request.form:
                        tag_id_to_delete = int(request.form.get('delete_tag'))
                        fortune_data['tag_pools'][pool_name] = [t for t in fortune_data['tag_pools'][pool_name] if t['id'] != tag_id_to_delete]
                    else:
                        for item in fortune_data['tag_pools'][pool_name]:
                            item_id = item['id']
                            item['tag'] = request.form.get(f'tag_{item_id}', item['tag'])
                            item['text'] = request.form.get(f'text_{item_id}', item['text'])
            
            elif form_type == 'add_to_pool':
                pool_name = request.form.get('pool_name')
                if pool_name in fortune_data['tag_pools']:
                    new_tag = request.form.get('new_tag')
                    new_text = request.form.get('new_text')
                    if new_tag and new_text:
                        pool = fortune_data['tag_pools'][pool_name]
                        max_id = max(t['id'] for t in pool) if pool else 0
                        pool.append({'id': max_id + 1, 'tag': new_tag, 'text': new_text})

            elif form_type == 'levels':
                for level in fortune_data['levels']:
                    level_id = level['id']
                    level['level_name'] = request.form.get(f'level_name_{level_id}', level['level_name'])
                    level['stars'] = int(request.form.get(f'stars_{level_id}', level['stars']))
                    level['star_shape'] = request.form.get(f'star_shape_{level_id}', level['star_shape'])
                    level['image'] = request.form.get(f'image_{level_id}', '')

            bot.save_data(bot.fortune_file, fortune_data)
            return redirect(url_for('fortune_web'))
            
        return render_template('fortune.html', fortune_data=fortune_data)
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
