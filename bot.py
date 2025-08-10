import os
import discord
from discord.ext import commands
import asyncio
import threading
from dotenv import load_dotenv

from utils.logger import logger
from web.app import register_routes

# 加载环境变量
load_dotenv()

class TarotBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="/", intents=intents)
        
        self.data_dir = os.getenv('HF_DISK_PATH', 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 确保上传文件夹存在
        os.makedirs('static/uploads', exist_ok=True)

    async def setup_hook(self):
        # 加载所有 cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"成功加载 Cog: {filename}")
                except Exception as e:
                    logger.error(f"加载 Cog {filename} 失败: {e}")

        # 同步指令
        try:
            guild_ids_str = os.getenv("DISCORD_GUILD_ID")
            if guild_ids_str:
                guild_ids = [int(gid.strip()) for gid in guild_ids_str.split(',') if gid.strip()]
                for gid in guild_ids:
                    try:
                        guild = discord.Object(id=gid)
                        self.tree.copy_global_to(guild=guild)
                        await self.tree.sync(guild=guild)
                        logger.info(f"已将指令同步到服务器: {gid}")
                    except Exception as e:
                        logger.error(f"无法将指令同步到服务器 {gid}: {e}")
            else:
                await self.tree.sync()
                logger.info("已全局同步指令")
        except Exception as e:
            logger.error(f"指令同步期间出错: {e}")

    async def on_ready(self):
        logger.info(f"机器人已准备就绪！已登录为 {self.user}")
        logger.info(f"机器人ID: {self.user.id}")
        logger.info(f"已连接到 {len(self.guilds)} 个服务器")

    async def on_error(self, event, *args, **kwargs):
        logger.error(f"在 {event} 中发生错误: {args} {kwargs}")

def run_flask(bot):
    try:
        flask_app = register_routes(bot)
        logger.info("在端口 7860 上启动 Flask 服务器")
        # 使用 waitress 或 gunicorn 等生产服务器会更好
        from waitress import serve
        port = int(os.getenv('FLASK_PORT', 7860))
        logger.info(f"在端口 {port} 上启动 Flask 服务器")
        serve(flask_app, host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"启动 Flask 时出错: {e}")

def run_bot(bot):
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("未设置 DISCORD_TOKEN 环境变量！")
        return
    
    logger.info("正在启动 Discord 机器人...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"运行机器人时出错: {e}")

if __name__ == "__main__":
    logger.info("正在启动应用程序...")
    
    bot_instance = TarotBot()
    
    flask_thread = threading.Thread(target=run_flask, args=(bot_instance,))
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask 服务器已在后台启动")
    
    run_bot(bot_instance)
