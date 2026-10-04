# ⚡ TaskPilot

A Windows desktop app that does the boring PC tasks in **one click**, tells you
**where your time actually goes**, and helps you **protect time for what matters**.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows-0078D6)

---

## ✨ What it does

| | |
|---|---|
| 🗑 **One-click actions** | Empty Recycle Bin, Play my music playlist, launch your apps, shut down / restart / sleep / lock |
| 📊 **Usage history** | Tracks which app you use and for how long — **Most Used**, **Most Opened (favourite)** and **Money-Making apps** |
| ⏱ **Time management** | Categorise apps, set daily limits (e.g. games = 30 min/day), Focus Mode blocks distractions |
| 💰 **Work value** | Tag work apps and set an hourly value → see what your screen time was worth |

---

## 🚀 Install & Run

You need **Windows 10/11** and **Python 3.10 or newer**.

### 1. Get Python (skip if you already have it)

Download it from <https://www.python.org/downloads/> and
**tick "Add Python to PATH"** during installation.

### 2. Install the two small libraries

Open **Command Prompt** in this folder and run:

```bat
pip install -r requirements.txt
```

### 3. Start the app

```bat
python main.py
```

That's it — the window opens and tracking starts automatically.

### 4. (Optional) Make a real `.exe`

Double-click **`build.bat`**. After about a minute you get
`dist\TaskPilot.exe` — a single file you can put anywhere and just double-click.

---

## 🧭 Using the app

### Dashboard
Four big buttons:
- **Empty Recycle Bin** — asks for confirmation first, then permanently empties the bin.
- **Play My Music** — opens your playlist (set the path in *Settings*).
- **Power** — Shut down / Restart / Sleep / Lock.
- **Quick Launch** — your own app shortcuts, one click each.

### Usage Stats
Pick **Today / 7 days / 30 days** and you get:
- **Most used app** — where most of your hours went
- **Most opened app** — the app you switch to the most (your "favourite")
- **💰 Money-Making Apps** — every app you tagged as work, ranked by time,
  with an estimated value (`hours × your hourly rate`)
- Bar charts for top apps and categories, a 14-day trend, and recent sessions

### Time Management
- **★ Important** — star the apps that matter so they stay first
- **Category** — `income` (work), `study`, `communication`, `entertainment`, `other`
- **min/day** — daily limit; 0 = unlimited. When you hit the limit you get a warning
- **🎯 Focus Mode** — flags you whenever you open a blocked category (games, streaming…)
- Turn on *"Automatically close apps over their limit"* in Settings if you want
  hard enforcement instead of warnings

### Settings
Music playlist, quick-launch apps, tracker speed, hourly work value,
CSV export and history cleanup.

---

## 💡 How the "money-making app" report works

1. Go to **Time Management** and set the category of your work apps to **`income`**
   (VS Code, Excel, Photoshop, your IDE, your trading terminal…).
2. In **Settings → 💰 Money Value**, enter what an hour of that work is worth.
3. **Usage Stats → Money-Making Apps** now shows time spent **and estimated value**.

The app auto-guesses categories for well-known programs (Steam/Discord →
entertainment, Office/IDEs → work) so you get useful data immediately, and you
can override any of them.

---

## 📁 Where your data lives

Everything is stored **locally on your PC** — nothing is sent anywhere.

```
%APPDATA%\TaskPilot\
├── config.json     ← your settings, apps, limits
└── usage.db        ← your usage history (SQLite)
```

Press **Settings → 🗄 Data → Open data folder** to jump straight there, or
**Export usage as CSV** to open it in Excel.

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| `'pip' is not recognized` | Use `python -m pip install -r requirements.txt` |
| `No module named tkinter` | Reinstall Python from python.org with **"tcl/tk and IDLE"** ticked |
| The window is blank / tiny | Maximise once — the layout adapts on resize |
| Nothing appears in Usage Stats | Make sure **📊 Usage Tracker** is on in Settings, and that you aren't idle |
| Antivirus asks about the .exe | Normal for PyInstaller apps — allow it, or keep running it with `python main.py` |
| I want to start fresh | Settings → 🗄 Data → **Delete all history** |

---

## 🗂 Project layout

```
taskpilot/
├── main.py               ← start the app here
├── build.bat             ← build TaskPilot.exe
├── requirements.txt
└── taskpilot/
    ├── config.py         ← settings (JSON)
    ├── storage.py        ← usage history (SQLite)
    ├── actions.py        ← recycle bin, power, music, launching
    ├── tracker.py        ← background usage tracking + limits
    └── ui/
        ├── app.py        ← main window + navigation
        ├── theme.py      ← dark theme + widgets
        ├── dashboard.py  ← one-click actions
        ├── stats.py      ← usage analytics
        ├── timeman.py    ← limits & focus mode
        └── settings.py   ← configuration
```

## 🧪 Tests

```bat
python tests/test_core.py      
python tests/test_ui_smoke.py  
```

`test_core.py` covers the config, the usage database, CSV export and the
tracker's session/limit logic. `test_ui_smoke.py` builds every page of the
window headlessly and catches crashes before you ever see them.
Neither needs a display or Windows APIs.
