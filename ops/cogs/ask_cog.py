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

# Discord embed description 上限 4096，留一點餘裕給結尾提示
_MAX_LEN = 3900

# LLM 產出的文字一律禁止觸發任何提及，否則模型若輸出 @everyone 會真的通知全體
_NO_MENTIONS = discord.AllowedMentions.none()


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

        truncated = len(result) > _MAX_LEN
        if truncated:
            result = result[:_MAX_LEN] + "\n\n…（回答過長，已截斷）"

        e = discord.Embed(title="💬 AI 回答", description=result, color=BLUE)
        # 問題本身也可能很長，欄位值上限 1024
        e.add_field(name="問題", value=question[:1024], inline=False)
        e.set_footer(text="AI 生成內容，可能有誤；它沒有執行任何操作的能力")
        await interaction.followup.send(embed=e, allowed_mentions=_NO_MENTIONS)


async def setup(bot: commands.Bot):
    await bot.add_cog(AskCog(bot))
