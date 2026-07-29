# -*- coding: utf-8 -*-
"""PyPoly 伺服器控制指令。

安全性設計：本 cog 只提供四個固定動作，沒有任何指令接受自由文字參數，
services 層的指令字串也全部寫死。因此即使頻道內所有人都能使用，
能觸發的行為仍侷限在「啟動 / 停止 / 查狀態 / 查網址」這四件事。
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import server_manager, tunnel_manager

GREEN, RED, GREY = 0x00CDAC, 0xFF7675, 0x95A5A6


def _embed(title: str, desc: str, color: int) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


class OpsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /start ───────────────────────────────────────────
    @app_commands.command(name="start", description="啟動 PyPoly 伺服器並建立公開網址")
    async def start(self, interaction: discord.Interaction):
        # 建隧道與等 DNS 可能要 30 秒以上，必須先 defer 否則 Discord 會判定逾時
        await interaction.response.defer(thinking=True)

        ok, msg = await server_manager.start()
        if not ok:
            await interaction.followup.send(embed=_embed("❌ 伺服器啟動失敗", msg, RED))
            return

        ok, result = await tunnel_manager.start()
        if not ok:
            await interaction.followup.send(embed=_embed("❌ 隧道建立失敗", result, RED))
            return

        login = f"{result}/static/login.html"
        e = _embed(
            "🎮 PyPoly 已上線",
            f"**點這裡開始玩**\n{login}\n\n"
            "· 第一次進去請允許相機權限\n"
            "· 帳號是學號，密碼同帳號\n"
            "· 建議用 Chrome 或 Edge",
            GREEN,
        )
        e.set_footer(text="網址每次重新啟動都會變，請以最新一則為準")
        await interaction.followup.send(embed=e)

    # ── /url ─────────────────────────────────────────────
    @app_commands.command(name="url", description="查詢目前的遊戲網址（不會改變任何狀態）")
    async def url(self, interaction: discord.Interaction):
        current = tunnel_manager.current_url()
        if not current:
            await interaction.response.send_message(
                embed=_embed("💤 目前沒有公開網址", "請先用 `/start` 啟動。", GREY))
            return
        await interaction.response.send_message(
            embed=_embed("🔗 目前的遊戲網址", f"{current}/static/login.html", GREEN))

    # ── /status ──────────────────────────────────────────
    @app_commands.command(name="status", description="查詢伺服器與隧道狀態")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        up = await server_manager.is_up()
        current = tunnel_manager.current_url()

        lines = [f"**伺服器**：{'🟢 執行中' if up else '🔴 未執行'}"]
        if up:
            lines.append(f"**啟動方式**：{'由 bot 啟動' if server_manager.owned() else '由其他方式啟動'}")
            players = await server_manager.online_players()
            if players is not None:
                lines.append(f"**房間內玩家**：{players} 人")
        lines.append(f"**公開網址**：{current + '/static/login.html' if current else '無（隧道未啟動）'}")

        await interaction.followup.send(
            embed=_embed("📊 PyPoly 狀態", "\n".join(lines), GREEN if up else GREY))

    # ── /stop ────────────────────────────────────────────
    @app_commands.command(name="stop", description="停止 PyPoly 伺服器與公開網址")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        t_ok, t_msg = tunnel_manager.stop()
        s_ok, s_msg = server_manager.stop()

        body = f"**隧道**：{t_msg}\n**伺服器**：{s_msg}"
        await interaction.followup.send(
            embed=_embed("🛑 已停止" if s_ok else "⚠️ 部分未停止", body, GREEN if s_ok else RED))


async def setup(bot: commands.Bot):
    await bot.add_cog(OpsCog(bot))
