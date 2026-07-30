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

⚠️ 本模組只讀取專案自己的檔案，不執行任何東西。
   LLM 仍然無法要求讀檔——脈絡是在送出請求「之前」由本模組決定的。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import config

# changeLog 尾端要帶多少字元（約當最近數個條目），用來解決系統提示會過期的問題
_CHANGELOG_TAIL = 4500

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


def build() -> str:
    """回傳脈絡區塊；來源檔未變動時直接用快取。"""
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
