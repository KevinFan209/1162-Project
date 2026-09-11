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


# ── 更新 ────────────────────────────────────────────────────

async def update(branch: str, path: Path) -> str:
    """把該 worktree 更新到遠端最新。回傳要顯示給使用者的說明（空字串代表順利）。

    刻意只做「快轉」。有未提交的改動或分支已分歧時一律跳過並說明原因，
    絕不 reset --hard 或 checkout -- ——那會無聲地毀掉別人正在做的事。
    """
    ok, out = await _git_async(["fetch", "origin", branch])
    if not ok:
        return f"⚠️ fetch 失敗，改用磁碟上現有的版本：\n```\n{out[-300:]}\n```"

    ok, dirty = await _git_async(["status", "--porcelain"], cwd=path)
    if ok and dirty.strip():
        n = len(dirty.strip().splitlines())
        return f"⚠️ 這個工作目錄有 {n} 個未提交的改動，已跳過更新，用的是磁碟上現有的版本。"

    ok, out = await _git_async(["merge", "--ff-only", f"origin/{branch}"], cwd=path)
    if not ok:
        return (f"⚠️ 無法快轉到 origin/{branch}（可能已分歧），"
                f"用的是磁碟上現有的版本：\n```\n{out[-300:]}\n```")

    return ""


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
