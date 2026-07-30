# -*- coding: utf-8 -*-
"""LLM 問答指令。

⚠️ 本 cog 刻意**不 import** services.server_manager 與 services.tunnel_manager。
   這是階段三的硬性約束：LLM 路徑與執行路徑完全隔離，
   模型的輸出只能變成貼回 Discord 的文字，永遠不能觸發任何動作。
   若日後有人想在這裡加上「讓 AI 幫你開伺服器」，請不要——
   Discord 頻道人人可打字，那等同把頻道變成公開的遠端 shell。
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import llm_client

BLUE, RED = 0x4FACFE, 0xFF7675

# 問題與回答都放在 description，讓問題顯示在回答上方。
# （embed 的排版順序與程式碼順序無關：description 永遠在 add_field 的欄位之前，
#   所以想讓問題在上面，就得跟回答放進同一個 description，而不是搬動程式碼位置。
#   選 description 而非 add_field 是因為欄位值上限只有 1024，裝不下多數回答。）
_MAX_DESC = 4096      # Discord embed description 硬上限
_Q_BUDGET = 400       # 問題最多佔用的字元數，其餘留給回答
_CUT_HINT = "\n\n…（回答過長，已截斷）"

# LLM 產出的文字一律禁止觸發任何提及，否則模型若輸出 @everyone 會真的通知全體
_NO_MENTIONS = discord.AllowedMentions.none()


def _compose(question: str, answer: str) -> str:
    """組出「問題在上、回答在下」的 description，並確保不超過 Discord 上限。"""
    q = question if len(question) <= _Q_BUDGET else question[:_Q_BUDGET] + "…"
    header = f"> ❓ **{q}**\n\n"
    room = _MAX_DESC - len(header)
    if len(answer) > room:
        answer = answer[:room - len(_CUT_HINT)] + _CUT_HINT
    return header + answer


class AskCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ask", description="問 AI 關於 PyPoly 的問題（只回文字，不會執行任何操作）")
    @app_commands.describe(question="你想問的問題，例如「結算的答對率是在哪裡算的？」")
    async def ask(self, interaction: discord.Interaction, question: str):
        question = question.strip()
        if not question:
            await interaction.response.send_message(
                embed=discord.Embed(title="⚠️ 請輸入問題", color=RED), ephemeral=True)
            return

        # 推理型模型單題可能要 30 秒以上，必須先 defer
        await interaction.response.defer(thinking=True)

        ok, result = await llm_client.ask(question)

        if not ok:
            e = discord.Embed(title="❌ 問答失敗", description=result, color=RED)
            e.set_footer(text=f"llama.cpp: {config.LLAMA_BASE_URL}")
            await interaction.followup.send(embed=e, allowed_mentions=_NO_MENTIONS)
            return

        e = discord.Embed(description=_compose(question, result), color=BLUE)
        e.set_footer(text="AI 生成內容，可能有誤；它沒有執行任何操作的能力")
        await interaction.followup.send(embed=e, allowed_mentions=_NO_MENTIONS)


async def setup(bot: commands.Bot):
    await bot.add_cog(AskCog(bot))
