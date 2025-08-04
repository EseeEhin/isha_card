import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 配置 ---
# 加载 .env 文件中的环境变量
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# !!重要!!
# 在下方填入您想清除指令的服务器ID (Guild ID)。
# 如果要清除多个服务器，请用逗号隔开，例如: "123456789,987654321"
# 您也可以直接使用 .env 文件中的 DISCORD_GUILD_ID 变量。
#
# 如果要清除所有“全局”指令，请将此变量设置为空字符串 ""
# 警告: 全局指令的清除可能需要长达一小时才能生效。
GUILD_IDS_TO_CLEAR = os.getenv("DISCORD_GUILD_ID", "")
# --- 配置结束 ---


class ClearBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!clear", intents=discord.Intents.default())

    async def on_ready(self):
        logging.info(f'以 {self.user} (ID: {self.user.id}) 的身份登录')
        logging.info('------')

        if GUILD_IDS_TO_CLEAR:
            guild_id_list = [int(gid.strip()) for gid in GUILD_IDS_TO_CLEAR.split(',') if gid.strip()]
            for guild_id in guild_id_list:
                try:
                    logging.info(f"正在尝试为服务器 {guild_id} 清除应用指令...")
                    guild = discord.Object(id=guild_id)
                    # 清空指定服务器的指令
                    self.tree.clear_commands(guild=guild)
                    # 同步空列表到服务器，完成清除
                    await self.tree.sync(guild=guild)
                    logging.info(f"成功为服务器 {guild_id} 清除了所有应用指令。")
                except Exception as e:
                    logging.error(f"为服务器 {guild_id} 清除指令失败: {e}")
        else:
            logging.warning("未指定服务器ID。正在尝试清除所有“全局”应用指令...")
            logging.warning("警告: 全局指令的更新可能需要长达一小时才能在所有服务器上生效。")
            try:
                # 清空全局指令
                self.tree.clear_commands(guild=None)
                # 同步空列表到全局，完成清除
                await self.tree.sync(guild=None)
                logging.info("成功清除了所有全局应用指令。")
            except Exception as e:
                logging.error(f"清除全局指令失败: {e}")

        logging.info("------")
        logging.info("任务完成。您可以随时使用 Ctrl+C 停止此脚本。")
        # 关闭机器人
        await self.close()

async def main():
    if not TOKEN:
        logging.error("错误: .env 文件中未设置 DISCORD_TOKEN。")
        return
    
    bot = ClearBot()
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("脚本被用户手动中断。")
