# -*- coding: utf-8 -*-
"""為 /ask 產生「程式碼地圖 + 最近變更」的脈絡區塊。

為什麼是地圖而不是原始碼：
    實測全量餵入不可行——用 llama.cpp 自己的 tokenizer 量過，
    game.html 一個檔案就約 102,000 token、整個 PyPoly/ 約 247,000 token，
    而 prefill 速度約 340 tok/s，等於單次 /ask 要 5～12 分鐘
    （Discord 的 followup 額度只有 15 分鐘），且長脈絡會讓問題被淹沒、
    回答品質反而下降。
    改為抽出「檔案清單 + 路由 + socket 事件 + 資料表欄位 + 函式名」的結構化索引，
    幾千 token 就能回答絕大多數「某功能在哪」的問題。

🏆 在地圖之外，依照這次問的問題「額外」附上真正相關檔案的完整內容：
    用使用者問題的關鍵字（中英文都處理）跟每個檔案的原始碼做字串比對計分，
    分數最高的少數幾個檔案才附完整內容，其他檔案仍然只靠上面的地圖。
    不是「全部檔案一次讀」（物理上塞不進模型的 context window，詳見
    build() 的說明），是「這一題真正相關的檔案才讀」，而且挑檔案這件事
    是純字串比對，不花 token、不呼叫模型。

⚠️ 本模組只讀取專案自己的檔案，不執行任何東西（包含 git log 都是唯讀）。
   LLM 仍然無法要求讀檔——脈絡是在送出請求「之前」由本模組決定的，
   相關性判斷留在我們自己的程式碼裡，不交給模型。
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import config

# changeLog 尾端要帶多少字元（約當最近數個條目），用來解決系統提示會過期的問題
_CHANGELOG_TAIL = 4500

# 依問題挑出的相關檔案，完整內容最多附這麼多字元（粗估的保守上限，不是精確
# token 數——這個專案的檔案混雜中文/英文/程式碼，沒有本地 tokenizer 可用，
# 用字元數當代理指標。實際要設多少，要配合 LLAMA 那台模型真正的 context
# window 大小調整，見 ops/README.md 或跟管理那台機器的人確認）。
_MAX_RELEVANT_CHARS = 20000

# 最多附幾個檔案的完整內容，避免一次塞進太多不同主題稀釋問題本身
_MAX_RELEVANT_FILES = 3

# 分數至少要到這個門檻才算「真的相關」。中文用 2 字詞比對很容易因為
# 一個通用詞（例如「天氣」「的話」）剛好出現在某個檔案的註解裡而誤判，
# 單一個弱比對不該讓整個檔案被附上——至少要湊到兩個以上不同詞命中，
# 或至少一個夠長、夠具體的詞命中，才算數。
_MIN_SCORE = 3

# 問題裡出現這些字眼，才順便查最近改動這個檔案的 commit 歷史
_HISTORY_KEYWORDS = ("最近", "改了", "為什麼", "為何", "commit", "歷史", "更新了", "修改過")

_GIT_TIMEOUT = 15  # 本機 git log，不走網路，給短一點就好

_cache: str | None = None
_cache_stamp: tuple | None = None


# ────────────────────────── Python 解析 ──────────────────────────

def _decorator_info(dec) -> str | None:
    """從裝飾器取出 REST 路由或 socket 事件名稱。"""
    if not isinstance(dec, ast.Call):
        return None
    f = dec.func
    if not isinstance(f, ast.Attribute):
        return None

    obj = f.value.id if isinstance(f.value, ast.Name) else ""
    arg = ""
    if dec.args and isinstance(dec.args[0], ast.Constant):
        arg = str(dec.args[0].value)

    if obj == "app" and f.attr in ("get", "post", "put", "delete", "websocket"):
        verb = "WS" if f.attr == "websocket" else f.attr.upper()
        return f"{verb:<6} {arg}"
    if obj == "sio" and f.attr == "on":
        return f"SOCKET {arg}"
    return None


def _parse_python(path: Path) -> dict:
    """抽出路由、socket 事件、資料表欄位、其他函式名。"""
    out = {"routes": [], "sockets": [], "models": [], "funcs": []}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return out

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            tagged = False
            for dec in node.decorator_list:
                info = _decorator_info(dec)
                if info:
                    entry = f"{info}  →  {node.name}()  {path.name}:{node.lineno}"
                    (out["sockets"] if info.startswith("SOCKET") else out["routes"]).append(entry)
                    tagged = True
            if not tagged and not node.name.startswith("_"):
                out["funcs"].append(f"{node.name}()")

        elif isinstance(node, ast.ClassDef):
            # SQLAlchemy 模型：抓 __tablename__ 與 Column 欄位名
            table, cols = None, []
            for sub in node.body:
                if isinstance(sub, ast.Assign) and sub.targets:
                    t = sub.targets[0]
                    name = t.id if isinstance(t, ast.Name) else None
                    if name == "__tablename__" and isinstance(sub.value, ast.Constant):
                        table = sub.value.value
                    elif name and isinstance(sub.value, ast.Call):
                        fn = sub.value.func
                        if getattr(fn, "id", "") == "Column":
                            cols.append(name)
            if table and cols:
                out["models"].append(f"{table}({node.name}): " + ", ".join(cols))
            elif cols or any(isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) for s in node.body):
                methods = [s.name for s in node.body
                           if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and not s.name.startswith("__")]
                if methods:
                    out["funcs"].append(f"class {node.name}: " + ", ".join(methods))
    return out


# ────────────────────────── 前端解析 ──────────────────────────

_RE_FUNC = re.compile(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.M)
_RE_ON = re.compile(r"socket\.on\(['\"]([^'\"]+)")
_RE_EMIT = re.compile(r"socket\.emit\(['\"]([^'\"]+)")
_RE_API = re.compile(r"API_URL\}(/[A-Za-z0-9_/\-]+)")


def _parse_frontend(path: Path) -> dict:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    return {
        "funcs": _RE_FUNC.findall(src),
        "on": sorted(set(_RE_ON.findall(src))),
        "emit": sorted(set(_RE_EMIT.findall(src))),
        "api": sorted(set(_RE_API.findall(src))),
    }


# ────────────────────────── 組裝 ──────────────────────────

def _stamp() -> tuple:
    """所有來源檔的 (路徑, mtime, 大小)，任何一個變動就重建快取。"""
    items = []
    for p in sorted(_source_files()):
        try:
            st = p.stat()
            items.append((str(p), st.st_mtime, st.st_size))
        except OSError:
            pass
    return tuple(items)


def _source_files() -> list[Path]:
    root = config.PYPOLY_DIR
    files = list(root.glob("*.py"))
    files += sorted(root.glob("static/*.html"))
    files += sorted(root.glob("static/*.js"))
    cl = root / "changeLog.txt"
    if cl.exists():
        files.append(cl)
    return files


def _build_map() -> str:
    """回傳結構化的程式碼地圖＋changeLog 尾段；來源檔未變動時直接用快取。"""
    global _cache, _cache_stamp

    stamp = _stamp()
    if _cache is not None and stamp == _cache_stamp:
        return _cache

    root = config.PYPOLY_DIR
    routes, sockets_be, models, py_funcs = [], [], [], []

    for p in sorted(root.glob("*.py")):
        info = _parse_python(p)
        routes += info["routes"]
        sockets_be += info["sockets"]
        models += info["models"]
        if info["funcs"]:
            py_funcs.append(f"  {p.name}: " + ", ".join(info["funcs"][:25]))

    parts = ["# PyPoly 程式碼地圖（自動產生，不是完整原始碼）", ""]

    parts.append("## 後端 REST 路由")
    parts += [f"  {r}" for r in routes]
    parts.append("")

    parts.append("## 後端 Socket.IO 事件 handler")
    parts += [f"  {s}" for s in sockets_be]
    parts.append("")

    parts.append("## 資料表與欄位")
    parts += [f"  {m}" for m in models]
    parts.append("")

    parts.append("## 後端其他函式")
    parts += py_funcs
    parts.append("")

    # 前端：只列較大的頁面，並限制函式名數量避免脹大
    parts.append("## 前端頁面")
    for p in sorted(root.glob("static/*.html")):
        kb = p.stat().st_size // 1024
        if kb < 8:
            continue
        fe = _parse_frontend(p)
        line = [f"  {p.name} ({kb}KB)"]
        if fe.get("api"):
            line.append(f"    呼叫 API: {', '.join(fe['api'][:14])}")
        if fe.get("emit"):
            line.append(f"    socket.emit: {', '.join(fe['emit'])}")
        if fe.get("on"):
            line.append(f"    socket.on: {', '.join(fe['on'])}")
        if fe.get("funcs"):
            fns = fe["funcs"]
            shown = ", ".join(fns[:60])
            more = f" …等共 {len(fns)} 個" if len(fns) > 60 else ""
            line.append(f"    函式: {shown}{more}")
        parts.append("\n".join(line))
    parts.append("")

    # ── B. changeLog 尾段：讓它知道最近改了什麼，也避免系統提示過期 ──
    cl = root / "changeLog.txt"
    if cl.exists():
        try:
            text = cl.read_text(encoding="utf-8", errors="replace")
            tail = text[-_CHANGELOG_TAIL:]
            # 從第一個完整條目開始，避免從半句話中間切斷
            idx = tail.find("\n[20")
            if idx > 0:
                tail = tail[idx + 1:]
            parts.append("## 最近的變更紀錄（changeLog.txt 末尾，這裡的內容比上面的『已知問題』更新）")
            parts.append(tail.strip())
        except Exception:
            pass

    _cache = "\n".join(parts)
    _cache_stamp = stamp
    return _cache


# ────────────────────────── 依問題挑相關檔案 ──────────────────────────

_RE_ASCII_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_./]{2,}")
_RE_CJK_RUN = re.compile(r"[一-鿿]{2,}")


def _extract_terms(question: str) -> list[str]:
    """從問題裡抽出拿來比對檔案內容的候選字詞。

    中英文分開處理：英文/程式碼識別字（函式名、路由）直接整串當候選詞；
    中文沒有空白分詞，整段抓出來的連續中文字串另外切成重疊的 2 字詞，
    兼顧「過路費」這種專有名詞跟一般提問用語的比對命中率。
    """
    terms: set[str] = set()

    for m in _RE_ASCII_TOKEN.findall(question):
        if len(m) >= 3:
            terms.add(m)

    for run in _RE_CJK_RUN.findall(question):
        terms.add(run)
        for i in range(len(run) - 1):
            terms.add(run[i:i + 2])

    return [t for t in terms if len(t) >= 2]


def _score_file(text: str, terms: list[str]) -> int:
    """算這個檔案跟問題的相關分數：命中幾個不同的候選詞，長詞多算一點權重。"""
    score = 0
    lower = text.lower()
    for t in terms:
        hay = lower if t.isascii() else text
        needle = t.lower() if t.isascii() else t
        if needle in hay:
            score += 2 if len(t) >= 4 else 1
    return score


def _pick_relevant_files(question: str) -> list[Path]:
    """依問題關鍵字，從所有原始碼檔案裡挑出分數最高的少數幾個。

    全部不命中（分數都是 0）時回空清單——一般聊天或問題跟程式碼無關時，
    不應該硬塞檔案進去，維持原本只用地圖回答的行為。
    """
    terms = _extract_terms(question)
    if not terms:
        return []

    scored: list[tuple[int, Path]] = []
    for p in _source_files():
        if p.name == "changeLog.txt":
            continue  # changeLog 尾段本來就已經在地圖裡附過了
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        score = _score_file(text, terms)
        if score >= _MIN_SCORE:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:_MAX_RELEVANT_FILES]]


def _relevant_files_block(question: str) -> str:
    """挑出相關檔案並附上完整內容，受 _MAX_RELEVANT_CHARS 總量限制。

    超過上限時，後面的檔案改成只標註「太大沒附」，不會讓單一個問題
    把整個請求撐爆。
    """
    files = _pick_relevant_files(question)
    if not files:
        return ""

    parts = ["", "## 這題可能相關的檔案（以下是完整內容，不是地圖摘要）"]
    budget = _MAX_RELEVANT_CHARS
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > budget:
            if budget <= 0:
                parts.append(f"\n### {p.name}\n（字數上限已用完，這個檔案只能請使用者自己看，"
                             f"或在問題裡指定更具體的函式名再問一次）")
                continue
            text = text[:budget] + "\n…（檔案太長，已截斷，完整內容請看原始檔）"
        budget -= len(text)
        parts.append(f"\n### {p.name}\n```\n{text}\n```")

    return "\n".join(parts)


# ────────────────────────── 依問題查 git log ──────────────────────────

def _git_log(args: list[str]) -> str:
    """唯讀的 git log，不走網路、不碰 working tree。失敗就回空字串，不丟例外。"""
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=str(config.CONTROL_WORKTREE),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _history_block(question: str, relevant_files: list[Path]) -> str:
    """問題裡有「最近」「為什麼」之類的字眼時，附上相關檔案最近幾筆 commit。

    只給 commit 訊息＋日期，不夾帶完整 diff——diff 可能很長，而且這個
    專案的 commit 訊息／changeLog 通常已經把「為什麼」寫清楚了。
    """
    if not any(kw in question for kw in _HISTORY_KEYWORDS):
        return ""
    if not relevant_files:
        return ""

    parts = ["", "## 這題相關檔案的最近變更紀錄（git log，只有 commit 訊息，沒有完整 diff）"]
    for p in relevant_files:
        try:
            rel = p.relative_to(config.CONTROL_WORKTREE)
        except ValueError:
            continue
        log = _git_log(["log", "--oneline", "-n", "15", "--date=short",
                        "--format=%h %ad %s", "--", str(rel)])
        if log:
            parts.append(f"\n### {p.name}\n```\n{log}\n```")

    return "\n".join(parts) if len(parts) > 2 else ""


def build(question: str | None = None) -> str:
    """回傳完整脈絡區塊：程式碼地圖（快取）＋這題相關檔案的完整內容
    （若有命中）＋這題相關檔案的近期 commit 紀錄（若問題像在問歷史）。

    question 省略或完全沒命中任何檔案時，行為跟舊版一樣只回程式碼地圖，
    不會因為這次改動讓既有行為跑掉。
    """
    out = _build_map()

    if not question:
        return out

    relevant = _pick_relevant_files(question)
    extra = _relevant_files_block(question)
    if extra:
        out += "\n" + extra

    history = _history_block(question, relevant)
    if history:
        out += "\n" + history

    return out
