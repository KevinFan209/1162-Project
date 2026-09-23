# -*- coding: utf-8 -*-
"""限制特定指令只能在特定頻道使用。

Discord 內建的「Integrations → 這個 bot → 指令權限」只能整包限制
（該 bot 的全部指令都套用同一組頻道/身分組設定），沒辦法只針對
單一指令個別設定頻道——實測 Server Settings → Integrations 那頁
確認過。所以改在程式碼這層做，跟其他安全性設計（分支白名單、
services 層指令字串寫死）一樣，不依賴 Discord 介面。
"""
from __future__ import annotations

from typing import Callable

import discord
from discord import app_commands


class WrongChannel(app_commands.CheckFailure):
    """頻道不符時丟出，帶著「應該去哪個頻道用」的資訊，方便錯誤訊息裡直接 @提及。"""

    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        super().__init__(f"此指令只能在 <#{channel_id}> 使用")


def restrict_to(channel_id_getter: Callable[[], int | None]):
    """給單一 app_commands.command 用的裝飾器。

    channel_id_getter 是個 callable（例如 `lambda: config.CHANNEL_OPS_ID`）
    而不是直接傳值，這樣才會在「每次指令被呼叫時」才讀 config，而不是
    在模組載入、裝飾器套用的當下就把值固定住。
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        allowed = channel_id_getter()
        if not allowed or interaction.channel_id == allowed:
            return True
        raise WrongChannel(allowed)
    return app_commands.check(predicate)


async def check_channel(interaction: discord.Interaction, channel_id: int | None) -> bool:
    """給 app_commands.Group.interaction_check 用，邏輯跟 restrict_to 共用，
    避免 issue_cog.py 自己再重寫一次同樣的判斷式。
    """
    if not channel_id or interaction.channel_id == channel_id:
        return True
    raise WrongChannel(channel_id)
