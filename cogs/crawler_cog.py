import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import json
from sentence_transformers import SentenceTransformer
import zipfile
from datetime import datetime

class CrawlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

    @app_commands.command(name="crawl", description="爬取指定用户在指定频道的发言")
    @app_commands.describe(user="要爬取发言的用户", channel="要爬取的频道")
    async def crawl(self, interaction: discord.Interaction, user: discord.User, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        
        owner = self.bot.owner
        if interaction.user.id != owner.id:
            await interaction.followup.send("抱歉，只有机器人主人才能使用此命令。", ephemeral=True)
            return

        messages_data = []
        limit = 10000  # Discord API limit per request, but we'll iterate
        
        try:
            async for message in channel.history(limit=None):
                if message.author.id == user.id:
                    embedding = self.model.encode(message.content, convert_to_tensor=False).tolist()
                    messages_data.append({
                        "timestamp": message.created_at.isoformat(),
                        "content": message.content,
                        "vector": embedding
                    })

            if not messages_data:
                await interaction.followup.send(f"在频道 {channel.mention} 中没有找到用户 {user.mention} 的发言。", ephemeral=True)
                return

            # Save to file
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_json = f"crawl_{user.name}_{channel.name}_{timestamp_str}.json"
            filename_zip = f"crawl_{user.name}_{channel.name}_{timestamp_str}.zip"
            
            with open(filename_json, 'w', encoding='utf-8') as f:
                json.dump(messages_data, f, ensure_ascii=False, indent=4)

            # Zip the file
            with zipfile.ZipFile(filename_zip, 'w') as zf:
                zf.write(filename_json)

            # Send to owner
            await owner.send(f"这是您请求的爬取数据：用户 {user.name} 在频道 {channel.name} 的发言。", file=discord.File(filename_zip))
            
            await interaction.followup.send(f"数据已成功爬取并发送给您。", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"爬取过程中发生错误: {e}", ephemeral=True)
        finally:
            # Clean up files
            if os.path.exists(filename_json):
                os.remove(filename_json)
            if os.path.exists(filename_zip):
                os.remove(filename_zip)

async def setup(bot):
    # First, get the owner
    if not bot.owner_id:
        app_info = await bot.application_info()
        bot.owner = app_info.owner
    else:
        bot.owner = await bot.fetch_user(bot.owner_id)
        
    await bot.add_cog(CrawlerCog(bot))
