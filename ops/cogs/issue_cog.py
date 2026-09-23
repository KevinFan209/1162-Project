# -*- coding: utf-8 -*-
"""待辦清單指令：/issue list/add/check/uncheck/edit/delete。

真正的資料存在 GitHub Issues（見 services/github_issues.py），這裡
只負責把 Discord 的輸入轉成對應的 API 呼叫、把結果排版成 embed。
跟 ops_cog.py（伺服器控制）刻意分開成獨立的 cog，理由同 ask_cog.py：
不同的關注點各自一個檔案，不要互相 import。

全部指令收在同一個 app_commands.Group（"issue"）底下，組員在 Discord
打 /issue 就會看到 list/add/check/uncheck/edit/delete 這幾個子指令，
不會跟其他指令混在同一層。
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from services import channel_guard, github_issues

GREEN, RED, GREY = 0x00CDAC, 0xFF7675, 0x95A5A6

# Discord 端顯示用的中文選項 <-> GitHub 標籤/狀態的對照表
_SECTION_TO_LABEL = {"緊急": "urgent", "次要": "polish", "全部": None}
_STATE_CHOICES = {"待辦中": "open", "已完成": "closed", "全部": "all"}


def _embed(title: str, desc: str, color: int) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color)


def _format_issue_line(item: dict) -> str:
    mark = "✅" if item.get("state") == "closed" else "⬜"
    return f"{mark} `#{item['number']}` {item['title']}"


class IssueGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="issue", description="待辦清單（背後是 GitHub Issues）")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Group.interaction_check 會在底下六個子指令執行前都先跑一次，
        # 所以頻道限制只要寫在這一個地方，不用逐一裝飾每個子指令。
        return await channel_guard.check_channel(interaction, config.CHANNEL_ISSUE_ID)

    # ── /issue list ──────────────────────────────────────
    @app_commands.command(name="list", description="列出待辦清單")
    @app_commands.describe(分類="只看緊急或次要，留空看全部", 狀態="預設只看待辦中")
    @app_commands.choices(
        分類=[app_commands.Choice(name=k, value=k) for k in _SECTION_TO_LABEL],
        狀態=[app_commands.Choice(name=k, value=k) for k in _STATE_CHOICES],
    )
    async def list_(self, interaction: discord.Interaction,
                     分類: app_commands.Choice[str] | None = None,
                     狀態: app_commands.Choice[str] | None = None):
        await interaction.response.defer(thinking=True)

        state = _STATE_CHOICES[狀態.value] if 狀態 else "open"
        section = 分類.value if 分類 else None

        async def _send_section(label: str | None, title: str):
            ok, result = await github_issues.list_issues(label, state)
            if not ok:
                await interaction.followup.send(embed=_embed("❌ 查詢失敗", result, RED))
                return
            if not result:
                await interaction.followup.send(embed=_embed(title, "（沒有符合的項目）", GREY))
                return
            body = "\n".join(_format_issue_line(item) for item in result)
            await interaction.followup.send(embed=_embed(title, body[:4000], GREEN))

        if section is None:
            # 沒篩選分類：緊急、次要各自送一個 embed，避免兩個分類混在
            # 一起塞爆單一 embed 4096 字的上限
            await _send_section("urgent", "🔴 緊急：會影響遊戲進程")
            await _send_section("polish", "🔵 次要：外觀／遊玩體驗")
        else:
            label = _SECTION_TO_LABEL[section]
            title = "🔴 緊急：會影響遊戲進程" if label == "urgent" else "🔵 次要：外觀／遊玩體驗"
            await _send_section(label, title)

    # ── /issue add ───────────────────────────────────────
    @app_commands.command(name="add", description="新增一條待辦")
    @app_commands.describe(分類="緊急還是次要", 標題="簡短標題", 說明="細節說明（可留空）")
    @app_commands.choices(分類=[
        app_commands.Choice(name="緊急", value="緊急"),
        app_commands.Choice(name="次要", value="次要"),
    ])
    async def add(self, interaction: discord.Interaction,
                  分類: app_commands.Choice[str], 標題: str, 說明: str = ""):
        await interaction.response.defer(thinking=True)

        # 標籤可能還沒建立過（第一次用），先確保存在
        ok, msg = await github_issues.ensure_labels()
        if not ok:
            await interaction.followup.send(embed=_embed("❌ 無法準備標籤", msg, RED))
            return

        label = _SECTION_TO_LABEL[分類.value]
        ok, result = await github_issues.create_issue(label, 標題, 說明)
        if not ok:
            await interaction.followup.send(embed=_embed("❌ 新增失敗", result, RED))
            return
        await interaction.followup.send(embed=_embed(
            "✅ 已新增",
            f"`#{result['number']}` {result['title']}\n{result.get('html_url', '')}",
            GREEN))

    # ── /issue check / uncheck ───────────────────────────
    @app_commands.command(name="check", description="打勾（標記為已完成）")
    @app_commands.describe(編號="issue 編號，用 /issue list 查")
    async def check(self, interaction: discord.Interaction, 編號: int):
        await interaction.response.defer(thinking=True)
        ok, msg = await github_issues.set_state(編號, closed=True)
        await interaction.followup.send(embed=_embed("✅ 已打勾" if ok else "❌ 失敗", msg, GREEN if ok else RED))

    @app_commands.command(name="uncheck", description="取消勾選（重新開啟）")
    @app_commands.describe(編號="issue 編號，用 /issue list 查")
    async def uncheck(self, interaction: discord.Interaction, 編號: int):
        await interaction.response.defer(thinking=True)
        ok, msg = await github_issues.set_state(編號, closed=False)
        await interaction.followup.send(embed=_embed("↩️ 已取消勾選" if ok else "❌ 失敗", msg, GREEN if ok else RED))

    # ── /issue edit ──────────────────────────────────────
    @app_commands.command(name="edit", description="編輯標題/說明")
    @app_commands.describe(編號="issue 編號", 標題="新標題（留空不改）", 說明="新說明（留空不改）")
    async def edit(self, interaction: discord.Interaction, 編號: int,
                    標題: str | None = None, 說明: str | None = None):
        await interaction.response.defer(thinking=True)
        if 標題 is None and 說明 is None:
            await interaction.followup.send(embed=_embed("⚠️ 沒有要改的內容", "標題與說明至少要給一個。", GREY))
            return
        ok, msg = await github_issues.edit_issue(編號, 標題, 說明)
        await interaction.followup.send(embed=_embed("✏️ 已更新" if ok else "❌ 失敗", msg, GREEN if ok else RED))

    # ── /issue delete ────────────────────────────────────
    @app_commands.command(name="delete", description="永久刪除（無法復原，不是關閉）")
    @app_commands.describe(編號="issue 編號，用 /issue list 查")
    async def delete(self, interaction: discord.Interaction, 編號: int):
        await interaction.response.defer(thinking=True)
        ok, msg = await github_issues.delete_issue(編號)
        await interaction.followup.send(embed=_embed("🗑️ 已永久刪除" if ok else "❌ 失敗", msg, RED))


class IssueCog(commands.Cog):
    """純粹掛載 IssueGroup 用的殼——群組指令要靠 bot.tree.add_command()
    註冊，不是靠 Cog 自動掃描（那只認得 @app_commands.command 直接掛在
    Cog 方法上的情況），所以 setup() 裡兩件事都要做。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(IssueCog(bot))
    bot.tree.add_command(IssueGroup())
