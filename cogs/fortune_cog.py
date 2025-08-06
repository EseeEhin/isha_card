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
            if not all(k in fortune_data for k in ["levels", "tag_pools", "connectors"]):
                await interaction.response.send_message("抱歉，运势数据结构不正确，请检查 `fortune.json`。")
                return

            chosen_level = random.choice(fortune_data["levels"])
            stars = chosen_level.get("stars", 3)

            tag_pools = fortune_data.get("tag_pools", {})
            good_pool = tag_pools.get("good", [])
            bad_pool = tag_pools.get("bad", [])
            neutral_pool = tag_pools.get("neutral", [])
            
            luck_type = "neutral"
            if stars >= 5: luck_type = "good"
            elif stars <= 2: luck_type = "bad"

            selected_tag_objects = []
            total_tags = random.randint(1, 5)

            base_pool = []
            if luck_type == "good":
                base_pool = good_pool
            elif luck_type == "bad":
                base_pool = bad_pool
            else:
                base_pool = neutral_pool
            
            if base_pool:
                selected_tag_objects.append(random.choice(base_pool))

            num_additional_tags = total_tags - len(selected_tag_objects)
            if num_additional_tags > 0 and neutral_pool:
                existing_ids = {t['id'] for t in selected_tag_objects}
                drawable_neutral_pool = [t for t in neutral_pool if t['id'] not in existing_ids]
                
                num_to_draw = min(num_additional_tags, len(drawable_neutral_pool))

                if num_to_draw > 0:
                    additional_tags = random.sample(drawable_neutral_pool, k=num_to_draw)
                    selected_tag_objects.extend(additional_tags)

            tags_to_display = [obj['tag'] for obj in selected_tag_objects]
            text_fragments = [obj['text'] for obj in selected_tag_objects]
            
            connectors = fortune_data.get("connectors", {})
            
            intro_options = connectors.get("intro", [""])
            intro = random.choice(intro_options) if intro_options else ""

            outro_options = connectors.get(f"outro_{luck_type}", [""])
            outro = random.choice(outro_options) if outro_options else ""
            
            final_text = intro + " " + "".join(text_fragments).strip().rstrip('，').rstrip('。').rstrip(',') + "。"
            if outro:
                final_text += " " + outro

            level_name = chosen_level["level_name"]
            color = discord.Color.light_grey()
            if luck_type == "good": color = discord.Color.gold()
            elif luck_type == "bad": color = discord.Color.dark_purple()

            star_icons = {'heart': '❤️', 'coin': '💰', 'star': '✨', 'thorn': '🥀', 'skull': '💀'}
            star_symbol = star_icons.get(chosen_level.get("star_shape", "star"), '✨')
            stars_display = star_symbol * stars + '🖤' * (7 - stars)

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
                f"来自暗影与月光下的祝福 | {self.bot.user.name}",
                f"由 {self.bot.user.name} 为你占卜",
                "愿星光指引你的道路",
                "血族猫娘的神秘低语"
            ]

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
            app_commands.Choice(name=f"({level['stars']}★) {level['level_name']}", value=level['id'])
            for level in fortune_data.get('levels', []) if current.lower() in level['level_name'].lower()
        ]
        return choices[:25]

async def setup(bot):
    await bot.add_cog(FortuneCog(bot))
