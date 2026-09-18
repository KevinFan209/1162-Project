# -*- coding: utf-8 -*-
"""PyPoly 伺服器控制指令。

安全性設計：services 層的指令字串全部寫死，能觸發的行為侷限在
「啟動 / 停止 / 查狀態 / 查網址 / 查分支」這幾件事。

唯一接受自由文字的是 /start 與 /restart 的分支參數。它在進入 services 之前
必須先通過 branch_manager.resolve_branch() 的白名單比對——分支名要真的存在於
git branch -r 的結果裡，否則直接拒絕——且全程用 list 形式呼叫 git、不經過 shell。
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import branch_manager, server_manager, tunnel_manager

GREEN, RED, GREY = 0x00CDAC, 0xFF7675, 0x95A5A6


def _embed(title: str, desc: str, color: int) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


class OpsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _bring_up(self, title: str, branch_raw: str | None = None) -> discord.Embed:
        """準備分支、啟動伺服器與隧道，回傳要貼回 Discord 的 embed。

        branch_raw 省略時沿用目前正在服務的分支；若尚未啟動過則用預設分支。
        """
        # 沒指定就沿用現在這個，讓單純的 /restart 不會意外切走
        if not branch_raw:
            branch_raw = server_manager.current_branch() or config.DEFAULT_BRANCH

        ok, branch, workdir, notes = await branch_manager.prepare(branch_raw)
        if not ok:
            return _embed("❌ 無法準備分支", "\n".join(notes), RED)

        ok, msg = await server_manager.start(branch=branch, workdir=workdir)
        if not ok:
            return _embed("❌ 伺服器啟動失敗", msg, RED)

        ok, result = await tunnel_manager.start()
        if not ok:
            return _embed("❌ 隧道建立失敗", result, RED)

        verified = tunnel_manager.url_verified()
        e = _embed(
            title,
            f"**點這裡開始玩**\n{result}/static/login.html\n\n"
            "· 第一次進去請允許相機權限\n"
            "· 帳號是學號，密碼同帳號\n"
            "· 建議用 Chrome 或 Edge",
            GREEN if verified else 0xFFA502,
        )
        # 讓組員知道自己測的到底是哪一版
        e.add_field(
            name="🌿 目前分支",
            value=f"`{branch}`\n{branch_manager.head_summary(workdir)}",
            inline=False)
        if notes:
            e.add_field(name="ℹ️ 備註", value="\n".join(notes)[:1000], inline=False)
        if not verified:
            # 隧道行程活著但連不到 PyPoly。改用固定網域之後不再有
            # DNS 傳播的問題，所以這種情況幾乎都是後端伺服器沒起來。
            e.add_field(
                name="⚠️ 尚未驗證連線",
                value=("隧道已建立，但這台主機透過它連不到 PyPoly。\n"
                       "通常是後端伺服器沒有正常啟動，可用 `/status` 確認；\n"
                       "網址本身是固定的，不會因為重啟而失效。"),
                inline=False)
        e.set_footer(text="網址是固定的，之後每次都一樣")
        return e

    # ── 分支參數的自動完成 ────────────────────────────────
    # 用 autocomplete 而不是寫死的 Choice：新分支一 push 就會出現在選單裡，
    # 不必改程式也不必重新註冊指令。
    async def _branch_autocomplete(self, interaction: discord.Interaction,
                                   current: str) -> list[app_commands.Choice[str]]:
        cur = (current or "").lower()
        names = [b for b in branch_manager.list_branches() if cur in b.lower()]
        return [app_commands.Choice(name=b, value=b) for b in names[:25]]

    # ── /start ───────────────────────────────────────────
    @app_commands.command(name="start", description="啟動 PyPoly 伺服器並建立公開網址")
    @app_commands.describe(branch="要啟動哪個分支（留空則沿用目前的）")
    @app_commands.autocomplete(branch=_branch_autocomplete)
    async def start(self, interaction: discord.Interaction, branch: str | None = None):
        # 準備分支、建隧道加起來可能要 30 秒以上，必須先 defer 否則 Discord 會判定逾時
        await interaction.response.defer(thinking=True)
        await interaction.followup.send(embed=await self._bring_up("🎮 PyPoly 已上線", branch))

    # ── /restart ─────────────────────────────────────────
    @app_commands.command(name="restart", description="重新啟動伺服器（可順便換分支）")
    @app_commands.describe(branch="要切換到哪個分支（留空則沿用目前的）")
    @app_commands.autocomplete(branch=_branch_autocomplete)
    async def restart(self, interaction: discord.Interaction, branch: str | None = None):
        await interaction.response.defer(thinking=True)

        # 先記住目前的分支，因為 stop() 會把它清掉
        keep = branch or server_manager.current_branch()

        tunnel_manager.stop()
        server_manager.stop()

        # 若停不掉又還活著，代表伺服器是別的方式啟動的（例如 dev-tunnel.ps1），
        # 這時硬啟第二個只會撞埠，明講比裝作成功好
        if await server_manager.is_up():
            await interaction.followup.send(embed=_embed(
                "⚠️ 無法重啟",
                "伺服器不是由 bot 啟動的，bot 不會去關別人的行程。\n"
                "請在原本啟動它的視窗按 Ctrl+C 之後，再執行 `/start`。",
                RED))
            return

        await interaction.followup.send(embed=await self._bring_up("🔄 PyPoly 已重新啟動", keep))

    # ── /url ─────────────────────────────────────────────
    @app_commands.command(name="url", description="查詢遊戲網址（固定不變，不會改變任何狀態）")
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
            branch = server_manager.current_branch()
            workdir = server_manager.current_workdir()
            if branch:
                lines.append(f"**分支**：`{branch}`")
                if workdir:
                    lines.append(f"**版本**：{branch_manager.head_summary(workdir)}")
            elif server_manager.owned():
                lines.append("**分支**：（未記錄，可能是舊版 bot 啟動的）")
            players = await server_manager.online_players()
            if players is not None:
                lines.append(f"**房間內玩家**：{players} 人")
        lines.append(f"**公開網址**：{current + '/static/login.html' if current else '無（隧道未啟動）'}")

        await interaction.followup.send(
            embed=_embed("📊 PyPoly 狀態", "\n".join(lines), GREEN if up else GREY))

    # ── /branches ────────────────────────────────────────
    @app_commands.command(name="branches", description="列出所有分支，以及哪個正在服務")
    async def branches(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        names = branch_manager.list_branches()
        if not names:
            await interaction.followup.send(embed=_embed(
                "⚠️ 取不到分支清單",
                "請確認 ops/.env 的 PROJECT_ROOT 指向正確的 git 倉庫。", RED))
            return

        ready = branch_manager.existing_worktrees()
        serving = server_manager.current_branch()

        lines = []
        for b in names:
            if b == serving:
                mark = "🟢 服務中"
            elif b in ready:
                mark = "📁 已就緒"
            else:
                mark = "　 未建立"
            lines.append(f"{mark}　`{b}`")

        body = "\n".join(lines)
        body += ("\n\n未建立的分支在第一次 `/start` 時會自動建好工作目錄。\n"
                 "同時只能服務一個分支——ngrok 免費方案只允許一條隧道。")

        await interaction.followup.send(
            embed=_embed("🌿 分支清單", body[:4000], GREEN))

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
