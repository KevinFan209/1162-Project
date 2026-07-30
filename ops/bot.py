# -*- coding: utf-8 -*-
"""PyPoly ops bot 進入點。

啟動：
    cd ops
    python bot.py

需先複製 .env.example 為 .env 並填入 DISCORD_TOKEN。
"""
from __future__ import annotations

import sys

# UTF-8 輸出保險：避免在 cp950(繁中) 主控台下，含 emoji 的 print 直接讓 bot 崩潰
# （與 PyPoly/main.py 開頭相同的處理）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import discord
from discord.ext import commands

import config
from services import server_manager, tunnel_manager

# 只用 slash command，不需要 message_content 這類特權 intent
intents = discord.Intents.default()


class OpsBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!pypoly ", intents=intents, help_command=None)

    async def setup_hook(self):
        await self.load_extension("cogs.ops_cog")
        await self.load_extension("cogs.ask_cog")

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"✅ 已同步 {len(synced)} 個指令到伺服器 {config.GUILD_ID}（立即生效）")
        else:
            synced = await self.tree.sync()
            print(f"✅ 已同步 {len(synced)} 個全域指令（最久需 1 小時才會出現）")
            print("   提示：於 .env 填入 GUILD_ID 可讓指令立即生效")

    async def on_ready(self):
        print(f"🤖 已登入為 {self.user}")
        print(f"   PyPoly 目錄：{config.PYPOLY_DIR}")
        print(f"   cloudflared：{config.CLOUDFLARED}")
        await self.change_presence(activity=discord.Game(name="/start 開遊戲"))

    async def close(self):
        # 關掉 bot 時一併收掉它啟動的子行程，避免留下孤兒 uvicorn / cloudflared
        tunnel_manager.stop()
        server_manager.stop()
        await super().close()


def main():
    problems = config.missing()
    if problems:
        print("❌ 設定不完整：")
        for p in problems:
            print(f"   - {p}")
        sys.exit(1)

    try:
        OpsBot().run(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ DISCORD_TOKEN 無效，請至 Discord Developer Portal 重新產生。")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
