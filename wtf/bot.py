import os
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import random
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

guild_id = os.getenv("DISCORD_GUILD_ID")  # 可选，指定服务器加速指令同步

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.queue = []
        self.play_mode = "顺序播放"  # 可选：顺序播放、随机播放、单曲循环
        self.current_url = None
        self.added_by = None

    async def setup_hook(self):
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

bot = MusicBot()

@bot.event
async def on_ready():
    print(f"已上线: {bot.user}")

# /点歌 指令
@bot.tree.command(name="点歌", description="点歌（支持YouTube/B站/歌单等链接）")
@app_commands.describe(
    链接="请输入歌曲或歌单链接"
)
async def 点歌(interaction: discord.Interaction, 链接: str):
    user = interaction.user
    # 兼容用户类型
    voice_state = None
    if hasattr(user, 'voice'):
        voice_state = user.voice
    elif hasattr(interaction, 'guild') and interaction.guild:
        member = interaction.guild.get_member(user.id)
        if member:
            voice_state = member.voice
    if not voice_state or not voice_state.channel:
        await interaction.response.send_message("请先加入一个语音频道！", ephemeral=True)
        return
    voice_channel = voice_state.channel
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not vc or not getattr(vc, 'is_connected', lambda: False)():
        vc = await voice_channel.connect()
    # 解析链接，支持歌单/单曲
    ydl_opts = {
        'extract_flat': False,
        'quiet': True,
        'format': 'bestaudio/best',
        'ignoreerrors': True,
        'playlistend': 20,  # 歌单最多取20首
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(链接, download=False)
        entries = []
        if 'entries' in info:
            entries = [e for e in info['entries'] if e]
        else:
            entries = [info]
        for entry in entries:
            bot.queue.append({
                'title': entry.get('title', '未知标题'),
                'url': entry.get('webpage_url', 链接),
                'audio_url': entry['url'],
                'added_by': user.display_name if hasattr(user, 'display_name') else user.name
            })
        await interaction.response.send_message(f"已添加 {len(entries)} 首歌到队列！", ephemeral=False)
        # 如果未在播放，自动播放
        if not getattr(vc, 'is_playing', lambda: False)():
            await play_next(vc, interaction.channel)
    except Exception as e:
        await interaction.response.send_message(f"添加失败: {e}", ephemeral=True)

# /播放方式 指令
@bot.tree.command(name="播放方式", description="设置播放方式（顺序播放/随机播放/单曲循环）")
@app_commands.describe(
    方式="选择播放方式"
)
@app_commands.choices(方式=[
    app_commands.Choice(name="顺序播放", value="顺序播放"),
    app_commands.Choice(name="随机播放", value="随机播放"),
    app_commands.Choice(name="单曲循环", value="单曲循环")
])
async def 播放方式(interaction: discord.Interaction, 方式: app_commands.Choice[str]):
    bot.play_mode = 方式.value
    await interaction.response.send_message(f"播放方式已设置为：{方式.value}")

# /歌单列表 指令
@bot.tree.command(name="歌单列表", description="查看当前歌单队列")
async def 歌单列表(interaction: discord.Interaction):
    if not bot.queue:
        await interaction.response.send_message("当前歌单队列为空。", ephemeral=True)
        return
    msg = "当前歌单队列：\n"
    for idx, song in enumerate(bot.queue, 1):
        msg += f"{idx}. {song['title']}（添加者：{song['added_by']}）\n"
    await interaction.response.send_message(msg)

# 播放下一个
async def play_next(vc, text_channel):
    if not bot.queue:
        await text_channel.send("队列已播放完毕。")
        await vc.disconnect()
        return
    if bot.play_mode == "随机播放":
        song = random.choice(bot.queue)
        bot.queue.remove(song)
    elif bot.play_mode == "单曲循环":
        song = bot.queue[0]
    else:
        song = bot.queue.pop(0)
    bot.current_url = song['url']
    try:
        vc.play(discord.FFmpegPCMAudio(song['audio_url']), after=lambda e: asyncio.run_coroutine_threadsafe(play_next(vc, text_channel), bot.loop))
        await text_channel.send(f"正在播放: {song['title']}\n链接: {song['url']}")
    except Exception as e:
        await text_channel.send(f"播放失败: {e}")
        await play_next(vc, text_channel)

# /跳过 指令
@bot.tree.command(name="跳过", description="跳过当前歌曲")
async def 跳过(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc and getattr(vc, 'is_playing', lambda: False)():
        if hasattr(vc, 'stop') and callable(getattr(vc, 'stop')):
            vc.stop()
            await interaction.response.send_message("已跳过当前歌曲。")
        else:
            await interaction.response.send_message("无法跳过，语音客户端不支持 stop。", ephemeral=True)
    else:
        await interaction.response.send_message("没有正在播放的歌曲。", ephemeral=True)

TOKEN = os.getenv("DISCORD_TOKEN")
if __name__ == "__main__":
    if not TOKEN:
        print("请设置环境变量 DISCORD_TOKEN")
    else:
        bot.run(TOKEN) 