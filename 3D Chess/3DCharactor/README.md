# 3DCharactor — Folder Overview

This folder contains the character customization feature developed for the PyPoly 3D Monopoly project.

---

## Folder Structure

```
3DCharactor/
  my-work/             Current development version
  full-integration/    Complete integration package (all changes)
  clean-integration/   Character-only integration package
```

---

## my-work

The full working version of the project as it currently stands on this machine.
Includes all changes made during development — character customization, database migration (MySQL → SQLite), dynamic API URL, leave-room logic, OTP email, and other miscellaneous fixes.

Use this folder to run and test the project locally.

---

## full-integration

A delivery package containing **all changes** made on top of the original project.

Includes:
- `static/character.html` — 3D character customization page
- `static/pypoly_char.js` — character rendering module for game.html
- `static/models/` — Steve GLB model and texture
- `static/game.html` — updated with full character system + leave-room logic + dynamic API URL
- `static/lobby.html` — updated with character customization menu link + dynamic API URL
- `static/index.html` — root redirect page
- `templates/board_preview.html` — 3D board preview page
- `database.py` — switched from MySQL to SQLite
- `demo_server.py` / `demo.bat` / `demo_requirements.txt` — standalone demo server
- `整合說明.md` — integration guide (Chinese)
- `個人完整修改紀錄.md` — complete change log (Chinese)

---

## clean-integration

A delivery package containing **only the character customization changes**, with no unrelated modifications.
This is the recommended package for the integration person if the rest of the team wants to handle other changes themselves.

Includes:
- `static/character.html` — 3D character customization page (new)
- `static/pypoly_char.js` — character rendering module (new)
- `static/models/minecraft_-_steve.glb` — Steve 3D model (new)
- `static/models/steve_tex_0.png` — model texture (new)
- `static/game.html` — original + character system only (no other changes)
- `static/lobby.html` — original + one menu link to character.html
- `main.py` — original + one Socket.IO event handler (`char_data_sync`)
- `整合說明.md` — step-by-step integration guide (Chinese)

See `clean-integration/整合說明.md` for detailed integration steps.
