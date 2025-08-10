import discord
from discord import app_commands
from discord.ext import commands
import random
import os
from utils.logger import logger, op_logger
from utils.data_manager import load_json_data, save_json_data

class FortuneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fortune_file = os.path.join(self.bot.data_dir, 'fortune.json')

    @app_commands.command(name="运势", description="抽一张今日运势牌")
    async def fortune(self, interaction: discord.Interaction):
        try:
            fortune_data = load_json_data(self.fortune_file)
            if not all(k in fortune_data for k in ["levels", "activities", "domains", "connectors"]):
                await interaction.response.send_message("抱歉，运势数据结构不正确，请检查 `fortune.json`。")
                return

            # 1. 抽取运势等级
            chosen_level = random.choice(fortune_data["levels"])
            level_name = chosen_level["level_name"]
            stars = chosen_level.get("stars", 3)

            # 2. 生成宜忌列表
            activities = fortune_data.get("activities", {})
            good_activities_pool = activities.get("good", [])
            bad_activities_pool = activities.get("bad", [])

            num_good = chosen_level.get("good_events", 2)
            num_bad = chosen_level.get("bad_events", 2)

            good_events = random.sample(good_activities_pool, min(num_good, len(good_activities_pool)))
            bad_events = random.sample(bad_activities_pool, min(num_bad, len(bad_activities_pool)))

            # 3. 生成领域解读
            domain_fortunes = []
            for domain in fortune_data.get("domains", []):
                domain_name = domain.get("name")
                fortune_text = domain.get("fortunes", {}).get(level_name)
                if domain_name and fortune_text:
                    domain_fortunes.append(f"**{domain_name}**: {fortune_text}")

            # 4. 组装 Embed 消息
            luck_type = "neutral"
            if stars >= 5: luck_type = "good"
            elif stars <= 2: luck_type = "bad"
            
            color = discord.Color.light_grey()
            if luck_type == "good": color = discord.Color.gold()
            elif luck_type == "bad": color = discord.Color.dark_purple()

            star_icons = {'heart': '❤️', 'coin': '💰', 'star': '✨', 'thorn': '🥀', 'skull': '💀'}
            star_symbol = star_icons.get(chosen_level.get("star_shape", "star"), '✨')
            stars_display = star_symbol * stars + '🖤' * (7 - stars)

            embed = discord.Embed(
                title=f"今日运势 - {level_name}",
                description=f"喵~ {interaction.user.mention}，这是你今天的运势指引！",
                color=color
            )
            
            embed.add_field(name="幸运等级", value=f"**{level_name}**", inline=True)
            embed.add_field(name="幸运星", value=stars_display, inline=True)

            if good_events:
                good_events_text = "\n".join([f"**{e['name']}**: {e['description']}" for e in good_events])
                embed.add_field(name="今日宜", value=good_events_text, inline=False)

            if bad_events:
                bad_events_text = "\n".join([f"**{e['name']}**: {e['description']}" for e in bad_events])
                embed.add_field(name="今日忌", value=bad_events_text, inline=False)

            if domain_fortunes:
                embed.add_field(name="各领域运势", value="\n".join(domain_fortunes), inline=False)

            # 添加结尾祝福语
            connectors = fortune_data.get("connectors", {})
            outro_options = connectors.get(f"outro_{luck_type}", [""])
            outro = random.choice(outro_options) if outro_options else ""
            embed.set_footer(text=outro)

            image_url = chosen_level.get("image")
            if image_url:
                embed.set_image(url=image_url)

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in fortune command: {e}")
            await interaction.response.send_message("抱歉，出现了一些问题，请稍后再试。", ephemeral=True)

    @app_commands.command(name="更新运势图片", description="更新指定运势等级的背景图片")
    @app_commands.rename(level_id="运势等级", url="链接")
    @app_commands.describe(level_id="请选择要更新的运势等级", url="新的图片URL")
    async def update_fortune_image(self, interaction: discord.Interaction, level_id: int, url: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("抱歉，只有服务器管理员才能使用此命令。", ephemeral=True)
            return

        try:
            fortune_data = load_json_data(self.fortune_file)
            level_to_update = next((l for l in fortune_data['levels'] if l['id'] == level_id), None)

            if not level_to_update:
                await interaction.response.send_message(f"未找到ID为 {level_id} 的运势等级。", ephemeral=True)
                return

            old_url = level_to_update.get("image", "")
            level_to_update["image"] = url
            save_json_data(self.fortune_file, fortune_data)

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
    async def fortune_level_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        fortune_data = load_json_data(self.fortune_file)
        choices = [
            app_commands.Choice(name=f"({level.get('stars', 'N/A')}★) {level['level_name']}", value=level['id'])
            for level in fortune_data.get('levels', []) if current.lower() in level.get('level_name', '').lower()
        ]
        return choices[:25]

async def setup(bot):
    await bot.add_cog(FortuneCog(bot))
