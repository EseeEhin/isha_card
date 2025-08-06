import discord
from discord import app_commands
from discord.ext import commands
import random
import os
from utils.logger import logger, op_logger
from utils.data_manager import load_json_data, save_json_data

class TarotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tarot_file = os.path.join(self.bot.data_dir, 'tarot.json')

    @app_commands.command(name="塔罗", description="抽一张塔罗牌")
    async def tarot(self, interaction: discord.Interaction):
        try:
            tarot_cards = load_json_data(self.tarot_file)
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
                
            embed.set_footer(text=f"由 {self.bot.user.name} 提供给 {interaction.user.name}")

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in tarot command: {e}")
            await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

    @app_commands.command(name="更新塔罗图片", description="更新指定塔罗牌的卡面图片")
    @app_commands.rename(card_id="塔罗牌", url="链接")
    @app_commands.describe(card_id="请选择要更新的塔罗牌", url="新的图片URL")
    async def update_tarot_image(self, interaction: discord.Interaction, card_id: int, url: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("抱歉，只有服务器管理员才能使用此命令。", ephemeral=True)
            return
        
        try:
            tarot_cards = load_json_data(self.tarot_file)
            card_to_update = next((c for c in tarot_cards if c['id'] == card_id), None)

            if not card_to_update:
                await interaction.response.send_message(f"未找到ID为 {card_id} 的塔罗牌。", ephemeral=True)
                return

            old_url = card_to_update.get("image", "")
            card_to_update["image"] = url
            save_json_data(self.tarot_file, tarot_cards)

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
    async def tarot_card_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        tarot_cards = load_json_data(self.tarot_file)
        choices = [
            app_commands.Choice(name=card['name'], value=card['id'])
            for card in tarot_cards if current.lower() in card['name'].lower()
        ]
        return choices[:25]

async def setup(bot):
    await bot.add_cog(TarotCog(bot))
