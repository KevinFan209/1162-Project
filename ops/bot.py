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

import socket

import discord
from discord.ext import commands

import config
from services import server_manager, tunnel_manager

# 只用 slash command，不需要 message_content 這類特權 intent
intents = discord.Intents.default()

# ── 單一實例保護 ────────────────────────────────────────────
# 為什麼需要：同一個 token 連兩次時 Discord 會讓後連上的接管 gateway，
# 於是指令被送到 B，但伺服器與隧道的子行程握在 A 手上。B 的 server_manager
# 看不到 A 的 _proc，/restart 就會回「伺服器不是由 bot 啟動的」——實際發生過。
# 用綁定 localhost 連接埠來做互斥：行程結束時作業系統自動釋放，
# 不像 lock file 會留下無人清理的殘留。
_SINGLETON_PORT = 20242
_singleton_sock: socket.socket | None = None


def acquire_single_instance() -> bool:
    """搶下單一實例鎖；已有其他 bot 在跑則回 False。"""
    global _singleton_sock
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Windows 上若設 SO_REUSEADDR 會允許重複綁定，反而失去互斥效果，
    # 因此不設；有 SO_EXCLUSIVEADDRUSE 時再加強。
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        except OSError:
            pass
    try:
        s.bind(("127.0.0.1", _SINGLETON_PORT))
        s.listen(1)
    except OSError:
        s.close()
        return False
    _singleton_sock = s   # 保留參考，避免被回收而提前釋放
    return True


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
    if not acquire_single_instance():
        print("❌ 已經有另一個 bot 在執行中，這次不啟動。")
        print("   同時跑兩個會讓 Discord 把指令送給其中一個，")
        print("   但伺服器與隧道握在另一個手上，/restart 與 /stop 會失效。")
        print()
        print("   找出正在執行的那個：")
        print('     Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" |')
        print("       Where-Object { $_.CommandLine -like '*bot.py*' } |")
        print("       Select-Object ProcessId, CreationDate")
        print("   確定要改用這一個的話，先把上面查到的行程關掉再重跑。")
        sys.exit(1)

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
