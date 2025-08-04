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

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设置操作日志
op_log_dir = 'logs'
os.makedirs(op_log_dir, exist_ok=True)
op_log_file = os.path.join(op_log_dir, 'operations.log')
op_logger = logging.getLogger('operations')
op_logger.setLevel(logging.INFO)
# 使用RotatingFileHandler来防止日志文件无限增大
handler = logging.handlers.RotatingFileHandler(op_log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
op_logger.addHandler(handler)

# 加载环境变量
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

guild_id = os.getenv("DISCORD_GUILD_ID")  # 可选，指定服务器加速指令同步

# Flask 应用
app = Flask(__name__)

from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        """从JSON文件加载数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load {file_path}: {e}")
            return []

    def save_data(self, file_path, data):
        """保存数据到JSON文件"""
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
    """处理/fortune指令"""
    try:
        fortunes = bot.load_data(bot.fortune_file)
        if not fortunes:
            await interaction.response.send_message("抱歉，运势数据正在维护中，请稍后再试。")
            return

        chosen_fortune = random.choice(fortunes)
        
        # 根据运势等级决定颜色
        if "吉" in chosen_fortune["level"] or "高照" in chosen_fortune["level"]:
            color = discord.Color.gold()
        elif "厄" in chosen_fortune["level"] or "笼罩" in chosen_fortune["level"]:
            color = discord.Color.dark_purple()
        else:
            color = discord.Color.light_grey()

        # 星星系统
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
        
        # 优先使用本地图片
        image_path = chosen_fortune.get("image")
        if image_path and os.path.exists(image_path):
            # 为了在Discord中显示，需要一个URL。我们将通过Flask提供这个URL。
            # 假设图片在 static/uploads/ 目录下
            image_filename = os.path.basename(image_path)
            # 注意：这里需要你的Flask应用有一个可访问的外部URL
            base_url = os.getenv("BASE_URL", "http://localhost:7860") 
            image_url = f"{base_url}/static/uploads/{image_filename}"
            embed.set_image(url=image_url)
        
        embed.set_footer(text=f"来自暗影与月光下的祝福 | {bot.user.name}")
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Error in fortune command: {e}")
        await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

# /tarot 指令
@bot.tree.command(name="塔罗", description="抽一张塔罗牌")
async def tarot(interaction: discord.Interaction):
    """处理/tarot指令"""
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
        
        if chosen_card.get("image"):
            embed.set_image(url=chosen_card["image"])
            
        embed.set_footer(text=f"由 {bot.user.name} 提供给 {interaction.user.name}")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Error in tarot command: {e}")
        await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

# --- 带自动补全功能的新指令 ---

# 更新塔罗牌图片
@bot.tree.command(name="更新塔罗图片", description="更新指定塔罗牌的卡面图片")
@app_commands.rename(card_id="塔罗牌", url="链接")
@app_commands.describe(card_id="请选择要更新的塔罗牌", url="新的图片URL")
async def update_tarot_image(interaction: discord.Interaction, card_id: int, url: str):
    """使用自动补全处理塔罗牌图片更新"""
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

# 更新运势图片
@bot.tree.command(name="更新运势图片", description="更新指定运势的图片")
@app_commands.rename(fortune_id="运势", url="链接")
@app_commands.describe(fortune_id="请选择要更新的运势", url="新的图片URL")
async def update_fortune_image(interaction: discord.Interaction, fortune_id: int, url: str):
    """使用自动补全处理运势图片更新"""
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

        log_message = f"User '{interaction.user}' (ID: {interaction.user.id}) updated image for Fortune (ID: {fortune_id}, Name: {fortune_to_update['fortune']}): from '{old_url}' to '{url}'"
        op_logger.info(log_message)

        embed = discord.Embed(title="🖼️ 运势图片更新成功", description=f"已成功更新 **{fortune_to_update['fortune']}** 的图片。", color=discord.Color.green())
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


# --- 调试指令 ---
test_group = app_commands.Group(name="测试", description="用于测试机器人功能的调试指令", default_permissions=discord.Permissions(administrator=True))

@test_group.command(name="抽塔罗", description="抽取一张指定的塔罗牌进行测试")
@app_commands.rename(card_id="塔罗牌", orientation="牌面朝向")
@app_commands.describe(card_id="请选择要抽取的塔罗牌", orientation="选择正位或逆位（可选，默认随机）")
@app_commands.choices(orientation=[
    app_commands.Choice(name="正位", value="upright"),
    app_commands.Choice(name="逆位", value="reversed"),
])
async def test_draw_tarot(interaction: discord.Interaction, card_id: int, orientation: str = None):
    """处理测试抽取塔罗牌指令"""
    try:
        tarot_cards = bot.load_data(bot.tarot_file)
        chosen_card = next((c for c in tarot_cards if c['id'] == card_id), None)

        if not chosen_card:
            await interaction.response.send_message("错误：找不到指定的塔罗牌。", ephemeral=True)
            return

        if orientation is None:
            orientation = random.choice(['upright', 'reversed'])
        
        orientation_text = "正位" if orientation == 'upright' else "逆位"
        description = chosen_card['description'][orientation]
        card_name_with_orientation = f"{chosen_card['name']} ({orientation_text})"

        embed = discord.Embed(
            title=f"【测试】你抽到了... {card_name_with_orientation}",
            description=f"**牌面解读:**\n{description}",
            color=discord.Color.blue()
        )
        if chosen_card.get("image"):
            embed.set_image(url=chosen_card["image"])
        embed.set_footer(text=f"测试指令由 {interaction.user.name} 执行")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in test_draw_tarot: {e}")
        await interaction.response.send_message("测试指令执行失败。", ephemeral=True)

@test_draw_tarot.autocomplete('card_id')
async def test_tarot_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    return await tarot_card_autocomplete(interaction, current)


@test_group.command(name="抽运势", description="抽取一张指定的运势牌进行测试")
@app_commands.rename(fortune_id="运势")
@app_commands.describe(fortune_id="请选择要抽取的运势")
async def test_draw_fortune(interaction: discord.Interaction, fortune_id: int):
    """处理测试抽取运势牌指令"""
    try:
        fortunes = bot.load_data(bot.fortune_file)
        chosen_fortune = next((f for f in fortunes if f['id'] == fortune_id), None)

        if not chosen_fortune:
            await interaction.response.send_message("错误：找不到指定的运势。", ephemeral=True)
            return
        
        # 复用主指令的逻辑来构建测试Embed
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
            title=f"【测试】血族猫娘的今日占卜",
            description=f"喵~ {interaction.user.mention}，这是你的测试运势！",
            color=color
        )
        
        embed.add_field(name="今日运势", value=f"**{chosen_fortune['level']}**", inline=False)
        embed.add_field(name="幸运星", value=stars_display, inline=False)
        
        if chosen_fortune.get("tags"):
            tags = " | ".join([f"`{tag}`" for tag in chosen_fortune["tags"]])
            embed.add_field(name="运势标签", value=tags, inline=False)
            
        embed.add_field(name="血族猫娘的低语", value=chosen_fortune["description"], inline=False)
        
        image_path = chosen_fortune.get("image")
        if image_path and os.path.exists(image_path):
            image_filename = os.path.basename(image_path)
            base_url = os.getenv("BASE_URL", "http://localhost:7860") 
            image_url = f"{base_url}/static/uploads/{image_filename}"
            embed.set_image(url=image_url)
        
        embed.set_footer(text=f"测试指令由 {interaction.user.name} 执行")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in test_draw_fortune: {e}")
        await interaction.response.send_message("测试指令执行失败。", ephemeral=True)

@test_draw_fortune.autocomplete('fortune_id')
async def test_fortune_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
    return await fortune_autocomplete(interaction, current)

bot.tree.add_command(test_group)

# Flask 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """健康检查端点"""
    return {"status": "healthy", "bot_ready": bot.is_ready() if hasattr(bot, 'is_ready') else False}

@app.route('/tarot', methods=['GET', 'POST'])
def tarot_web():
    try:
        tarot_cards = bot.load_data(bot.tarot_file)
        if request.method == 'POST':
            for card in tarot_cards:
                # 处理文本更新
                upright_desc = request.form.get(f'upright_{card["id"]}')
                if upright_desc is not None:
                    card['description']['upright'] = upright_desc
                
                reversed_desc = request.form.get(f'reversed_{card["id"]}')
                if reversed_desc is not None:
                    card['description']['reversed'] = reversed_desc

                # 处理文件上传
                file_key = f'image_upload_{card["id"]}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"tarot_{card['id']}_{file.filename}")
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(save_path)
                        card['image'] = f"/{save_path.replace(os.path.sep, '/')}" # 使用URL友好的路径
            
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
            # 使用索引来处理表单提交，因为ID可能不是连续的
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

                # 处理文件上传
                file_key = f'image_upload_{item_id}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename and allowed_file(file.filename):
                        # 使用 item_id 确保文件名唯一性
                        filename = secure_filename(f"fortune_bg_{item_id}{os.path.splitext(file.filename)[1]}")
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(save_path)
                        # 保存相对路径以便于机器人内部使用
                        item['image'] = os.path.join(UPLOAD_FOLDER, filename).replace(os.path.sep, '/')
                
                updated_fortunes.append(item)

            # 确保所有原始数据都被处理
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
    """在单独的线程中运行Flask"""
    try:
        logger.info("Starting Flask server on port 7860")
        app.run(host='0.0.0.0', port=7860, debug=False)
    except Exception as e:
        logger.error(f"Error starting Flask: {e}")

def run_bot():
    """运行Discord机器人"""
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("DISCORD_TOKEN environment variable is not set!")
        print("请设置环境变量 DISCORD_TOKEN")
        return
    
    logger.info("Starting Discord bot...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        print(f"机器人启动失败: {e}")

if __name__ == "__main__":
    logger.info("Starting application...")
    
    # 启动Flask服务器在后台线程
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask server started in background")
    
    # 启动Discord机器人
    run_bot()
