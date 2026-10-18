# -*- coding: utf-8 -*-
"""管理各分支的 git worktree，讓一個 bot 就能服務不同分支。

原本要讓組員測某個分支，得切到另一個資料夾、git switch、再重開 bot.py。
這個模組讓 /start <分支> 直接決定要服務哪一版。

為什麼用 worktree 而不是每個分支各自 clone：
    9 個分支各 clone 要約 900MB，worktree 全部共用同一個 .git 只要 104MB，
    而且 git fetch 一次所有分支都拿到新資料。

⚠️ 安全性
    server_manager 的設計前提是「啟動指令寫死，不接受任何來自 Discord 的輸入」。
    加上分支參數等於打破這個前提，所以本模組的每個公開函式都必須先經過
    resolve_branch() 的白名單比對：分支名要真的存在於 git branch -r 的結果裡，
    否則一律拒絕。所有 git 指令都用 list 形式呼叫、不經過 shell，
    路徑組出來之後還會再確認確實位於 PROJECT_ROOT 底下。
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import config

# git 指令的逾時。fetch 走網路，給寬一點。
_GIT_TIMEOUT = 120


def _git(args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    """執行 git 指令。回傳 (成功, 輸出)。

    一律用 list 形式且 shell=False，分支名即使含有特殊字元也不會被當成指令解析。
    """
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=str(cwd or config.CONTROL_WORKTREE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"git {' '.join(args[:2])} 逾時（{_GIT_TIMEOUT} 秒）"
    except FileNotFoundError:
        return False, "找不到 git，請確認已安裝且在 PATH 中"

    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, out.strip()


async def _git_async(args: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    """在執行緒裡跑 git，避免阻塞 discord.py 的事件迴圈。"""
    return await asyncio.to_thread(_git, args, cwd)


# ── 分支清單 ────────────────────────────────────────────────

def list_branches() -> list[str]:
    """可用的分支名稱，來源是遠端分支。

    用遠端而非本機分支，新分支一 push 就會出現在 Discord 的選單裡，
    不必手動維護清單，也不必先在本機 checkout 過。
    """
    # 用完整的 refname 而非 short：refs/remotes/origin/HEAD 的 short name 正好是
    # 「origin」，看起來像一個叫 origin 的分支，會混進清單裡。
    ok, out = _git(["branch", "-r", "--format=%(refname)"])
    if not ok:
        return []

    PREFIX = "refs/remotes/origin/"
    names = []
    for line in out.splitlines():
        ref = line.strip()
        if not ref.startswith(PREFIX):
            continue
        name = ref[len(PREFIX):]
        if not name or name == "HEAD":    # origin/HEAD 是符號連結，不是分支
            continue
        if name not in names:
            names.append(name)
    return sorted(names)


async def list_branches_fresh() -> list[str]:
    """跟 list_branches() 一樣，但先 fetch 一次確保看到最新 push 的分支。

    🏆 /branches 指令原本直接呼叫 list_branches()，而那個函式從不主動
    fetch——新分支一 push，本機 git 資料庫沒人手動 fetch 過就不會知道它
    存在，使用者會看到「明明建了分支卻沒出現在清單裡」。resolve_branch()
    （/start 用的）已經有一樣的 fetch-retry，但那段邏輯刻意沒有搬進
    list_branches() 本身，因為自動完成每打一個字就會呼叫它，加網路
    fetch 會明顯變慢。/branches 是使用者主動按一次的指令，不是每個按鍵
    都觸發，所以在這裡直接做無條件 fetch 是安全的，不會重現自動完成
    那個顧慮。fetch 失敗（例如離線）就靜默忽略，照樣回傳本機現有的清單，
    不讓 /branches 因為網路問題而整個失敗。
    """
    await _git_async(["fetch", "origin"])
    return list_branches()


def resolve_branch(raw: str | None) -> tuple[str | None, str]:
    """把使用者輸入的分支名對到真實存在的分支。回傳 (分支名, 錯誤訊息)。

    這是唯一的入口守門員——後面所有函式都假設分支名已經通過這裡。
    """
    name = (raw or "").strip()
    if not name:
        name = config.DEFAULT_BRANCH

    branches = list_branches()
    if not branches:
        return None, "取不到分支清單，請確認 PROJECT_ROOT 設定正確且該目錄是 git 倉庫"

    if name in branches:
        return name, ""

    # 大小寫不敏感的補救（Windows 的使用者常打錯大小寫）
    for b in branches:
        if b.lower() == name.lower():
            return b, ""

    return None, f"找不到分支 `{name}`。可用的有：{', '.join(branches)}"


# ── worktree ────────────────────────────────────────────────

def worktree_path(branch: str) -> Path:
    """該分支應該在的資料夾。呼叫端必須已經通過 resolve_branch。"""
    return (config.PROJECT_ROOT / branch).resolve()


def _inside_project_root(p: Path) -> bool:
    """確認路徑真的在 PROJECT_ROOT 底下，擋掉 ../ 之類的字串。"""
    try:
        p.relative_to(config.PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def existing_worktrees() -> dict[str, Path]:
    """目前已建立的 worktree：{分支名: 路徑}。"""
    ok, out = _git(["worktree", "list", "--porcelain"])
    if not ok:
        return {}

    result: dict[str, Path] = {}
    cur_path: Path | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            cur_path = Path(line[len("worktree "):].strip())
        elif line.startswith("branch ") and cur_path is not None:
            ref = line[len("branch "):].strip()
            if ref.startswith("refs/heads/"):
                result[ref[len("refs/heads/"):]] = cur_path
            cur_path = None
    return result


async def ensure_worktree(branch: str) -> tuple[bool, Path | None, str]:
    """確保該分支有一個可用的工作目錄。回傳 (成功, 路徑, 訊息)。

    分支若已在某個 worktree 被 checkout（例如 main 就在 bot 自己的 worktree），
    直接沿用那一個——git 不允許同一分支同時 checkout 在兩處。
    """
    existing = existing_worktrees()
    if branch in existing:
        p = existing[branch]
        if (p / "PyPoly" / "main.py").exists():
            return True, p, ""
        return False, None, f"分支 `{branch}` 的工作目錄 {p} 裡找不到 PyPoly/main.py"

    path = worktree_path(branch)
    if not _inside_project_root(path):
        # 理論上 resolve_branch 已經擋掉，這裡是第二道防線
        return False, None, f"路徑 {path} 不在 PROJECT_ROOT 底下，已拒絕"

    if path.exists() and any(path.iterdir()):
        return False, None, (f"{path} 已存在且非空，但不是這個分支的 worktree。\n"
                             "請先手動確認該目錄的用途。")

    ok, out = await _git_async(["worktree", "add", str(path), branch])
    if not ok:
        return False, None, f"建立 worktree 失敗：\n```\n{out[-500:]}\n```"

    if not (path / "PyPoly" / "main.py").exists():
        return False, None, f"worktree 已建立但找不到 {path / 'PyPoly' / 'main.py'}"

    return True, path, f"已為分支 `{branch}` 建立工作目錄"


async def _is_safe_to_reset(branch: str, path: Path) -> bool:
    """本機這個 worktree 的 HEAD 是否曾經是 origin/<branch> 自己指過的舊版本。

    🏆 只有在這個條件成立時，才能放心 reset --hard 追上去——這代表本機
    這份內容原本就是從 origin 複製來的快照，不是誰在這個（理論上 bot
    獨佔管理、沒人應該手動 commit）worktree 裡自己 commit 出來、從沒
    推上去的東西，reset 不會毀掉任何人的工作。

    會用到這個函式的情境：worktree 剛好在「本機第一次 fetch 到這個
    分支」跟「這個分支在遠端被強制推送（reset/rebase）改寫歷史」兩個
    事件中間的極短時間窗建立，卡死在改寫前的舊快照——這種情況
    git merge --ff-only 原理上永遠無法把本機追上去（fast-forward
    只能處理「新增 commit」，沒辦法處理「歷史被整個換掉」），需要
    reset 才能恢復正常，且用 origin/<branch> 自己的 reflog 驗證過
    「這份內容本來就來自 origin」，比單純判斷「分歧了就放手 reset」
    安全得多。
    """
    ok, head = await _git_async(["rev-parse", "HEAD"], cwd=path)
    if not ok:
        return False
    head = head.strip()

    ok, out = await _git_async(["log", "-g", "--format=%H", f"origin/{branch}"])
    if not ok:
        return False
    return head in out.splitlines()


# ── 更新 ────────────────────────────────────────────────────

async def update(branch: str, path: Path) -> str:
    """把該 worktree 更新到遠端最新。回傳要顯示給使用者的說明（空字串代表順利）。

    預設只做「快轉」。有未提交的改動時一律跳過並說明原因，絕不動
    uncommitted 的東西。分支已分歧時，只有在確認本機 HEAD 本來就是
    origin/<branch> 自己 reflog 裡曾經出現過的舊版本（見
    _is_safe_to_reset()）才會自動 reset --hard 追上去，其餘情況一律
    跳過並說明原因，不盲目 reset——那會無聲地毀掉別人正在做的事。
    """
    ok, out = await _git_async(["fetch", "origin", branch])
    if not ok:
        return f"⚠️ fetch 失敗，改用磁碟上現有的版本：\n```\n{out[-300:]}\n```"

    # 🏆 只擋「已追蹤檔案被改過」（git status --porcelain 的 XY 不是
    # "??"），未追蹤檔案（例如 ensure_env() 自己複製進來的 .env、
    # Python 跑過後留下的 __pycache__）就算有也不算數——這兩個指令
    # （merge --ff-only／reset --hard）都只動已追蹤檔案，未追蹤檔案
    # 原本就不會被影響，擋這個只會讓每個新建的 worktree 永遠卡在
    # 「有未提交的改動」，實際上沒有任何東西會被毀掉。
    ok, status_out = await _git_async(["status", "--porcelain"], cwd=path)
    tracked_dirty = [line for line in status_out.strip().splitlines() if not line.startswith("??")]
    if ok and tracked_dirty:
        return (f"⚠️ 這個工作目錄有 {len(tracked_dirty)} 個已追蹤檔案被改過但未提交，"
                "已跳過更新，用的是磁碟上現有的版本。")

    ok, out = await _git_async(["merge", "--ff-only", f"origin/{branch}"], cwd=path)
    if ok:
        return ""

    # 🏆 快轉失敗，先確認這真的只是「卡在 origin 自己的舊快照」，
    # 不是本機有從沒推上去的 commit，才動 reset --hard。
    if await _is_safe_to_reset(branch, path):
        ok2, out2 = await _git_async(["reset", "--hard", f"origin/{branch}"], cwd=path)
        if ok2:
            return (f"ℹ️ 偵測到 `{branch}` 在遠端被強制推送過（歷史改寫，無法單純快轉），"
                     "已確認本機只是卡在 origin 自己的舊快照、沒有任何未推送的本機 "
                     "commit，自動 reset 同步到最新版本。")
        return (f"⚠️ 無法快轉到 origin/{branch}（可能已分歧），嘗試自動 reset 也失敗了，"
                f"用的是磁碟上現有的版本：\n```\n{out2[-300:]}\n```")

    return (f"⚠️ 無法快轉到 origin/{branch}（可能已分歧，且本機有無法確認來源的獨立"
            f"commit，為安全起見不自動 reset），用的是磁碟上現有的版本：\n```\n{out[-300:]}\n```")


# ── .env ────────────────────────────────────────────────────

def ensure_env(path: Path) -> str:
    """確保該 worktree 有 PyPoly/.env。回傳說明（空字串代表本來就有或複製成功）。

    .env 被 gitignore，所以新建的 worktree 一定沒有。少了它，SECRET_KEY 會退回
    程式碼裡的公開預設值，環境部 AQI 也拿不到金鑰——但遊戲仍然跑得起來，
    所以這裡只警告不擋。
    """
    target = path / "PyPoly" / ".env"
    if target.exists():
        return ""

    source = config.CONTROL_WORKTREE / "PyPoly" / ".env"
    if not source.exists():
        return "⚠️ 這個分支沒有 PyPoly/.env，且找不到可複製的來源。SECRET_KEY 會用公開預設值。"

    try:
        shutil.copy2(source, target)
        return ""
    except OSError as e:
        return f"⚠️ 複製 PyPoly/.env 失敗（{e.__class__.__name__}），SECRET_KEY 會用公開預設值。"


# ── 顯示用 ──────────────────────────────────────────────────

def head_summary(path: Path) -> str:
    """該工作目錄目前的 commit，用來讓組員確認自己測的是哪一版。"""
    ok, out = _git(["log", "-1", "--format=%h %s", "--date=short"], cwd=path)
    if not ok or not out:
        return "（取不到 commit）"
    return out.splitlines()[0][:80]


async def prepare(branch_raw: str | None) -> tuple[bool, str, Path | None, list[str]]:
    """一次做完切分支前的所有準備。

    回傳 (成功, 分支名, 工作目錄, 要附註給使用者的訊息)。
    ops_cog 只要呼叫這一個函式即可。
    """
    notes: list[str] = []

    branch, err = resolve_branch(branch_raw)
    if not branch:
        # 🏆 list_branches() 只讀本機現有的 remote-tracking refs，從來不會
        # 自己 git fetch——分支剛 push 上去、本機還沒更新過的話，第一次
        # 一定找不到。這裡只在真的失敗時才 fetch 一次再重試，不放進
        # list_branches()／自動完成本身，避免使用者每打一個字都觸發網路
        # 請求。fetch 失敗（例如離線）就直接用原本的錯誤訊息，不額外出錯。
        ok, _ = await _git_async(["fetch", "origin"])
        if ok:
            branch, err = resolve_branch(branch_raw)
        if not branch:
            return False, "", None, [err]

    ok, path, msg = await ensure_worktree(branch)
    if not ok:
        return False, branch, None, [msg]
    if msg:
        notes.append(msg)

    note = await update(branch, path)
    if note:
        notes.append(note)

    note = ensure_env(path)
    if note:
        notes.append(note)

    return True, branch, path, notes
