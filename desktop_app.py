#python -m PyInstaller --noconfirm --windowed --onefile --name "PersonalLearningAgent" --icon "assets/app_icon.ico" --add-data "assets;assets" desktop_app.py
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import textwrap
import tkinter as tk
import ctypes
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFont, ImageTk


PROJECT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PersonalLearningAgent"
USER_DB_DIR = APP_DATA_DIR / "data" / "users"
LEGACY_USER_DB_DIR = PROJECT_DIR / "data" / "users"
APP_CONFIG_PATH = APP_DATA_DIR / "config.json"
LOCAL_CONFIG_PATH = PROJECT_DIR / "config.local.json"
BG_PATH = BUNDLE_DIR / "assets" / "anime_study_background.png"
ICON_PATH = BUNDLE_DIR / "assets" / "app_icon.ico"
AI_ICON_PATH = BUNDLE_DIR / "assets" / "ai_assistant_icon.png"

TEXT = "#65465b"
PINK_BUTTON = (251, 225, 239, 218)
PANEL = (255, 247, 252, 112)
FIELD = (255, 250, 253, 88)
BAR = (249, 223, 237, 178)
LINE = (239, 190, 216, 160)
MOODS = ["开心 · 小心心", "平静 · 云朵", "有动力 · 星光", "有点累 · 休息", "焦虑 · 深呼吸", "想摆烂 · 充电"]
INPUT_TEXT = "#6f435c"
TOAST_TEXT = "#efb6d4"
INPUT_FONT_SIZE = 16
BASE_WIDTH = 820
BASE_HEIGHT = 560
AI_DEFAULT_REPLY = "今天也要元气满满哦！"
AI_THINKING_REPLY = "别着急，我在努力思考哦~"


class LogRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    content TEXT NOT NULL,
                    tasks TEXT DEFAULT '',
                    problems TEXT DEFAULT '',
                    tomorrow_plan TEXT DEFAULT '',
                    category VARCHAR(100) DEFAULT '',
                    status VARCHAR(30) DEFAULT '进行中',
                    duration_minutes INTEGER DEFAULT 0,
                    remark TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    plan_date DATE DEFAULT '',
                    plan_text TEXT DEFAULT '',
                    applied INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def create(self, payload: dict[str, str | int]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_logs (
                    date, content, tasks, problems, tomorrow_plan, category,
                    status, duration_minutes, remark, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["date"],
                    payload["content"],
                    payload["tasks"],
                    payload["problems"],
                    payload["tomorrow_plan"],
                    payload["category"],
                    payload["status"],
                    payload["duration_minutes"],
                    payload["remark"],
                    now,
                    now,
                ),
            )
            conn.commit()

    def latest_by_date(self, log_date: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM learning_logs WHERE date = ? ORDER BY id DESC LIMIT 1",
                (log_date,),
            ).fetchone()

    def list_between(self, start_date: str, end_date: str, limit: int = 30) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM learning_logs
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()

    def list_recent(self, days: int = 14, limit: int = 30) -> list[sqlite3.Row]:
        end = date.today()
        start = end - timedelta(days=days - 1)
        return self.list_between(start.isoformat(), end.isoformat(), limit=limit)

    def search_text(self, keyword: str, limit: int = 20) -> list[sqlite3.Row]:
        like = f"%{keyword}%"
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM learning_logs
                WHERE content LIKE ? OR tasks LIKE ? OR problems LIKE ? OR tomorrow_plan LIKE ?
                ORDER BY date DESC, id DESC
                LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()

    def create_snapshot(
        self,
        log_date: str,
        content: str = "",
        tasks: str = "",
        problems: str = "",
        tomorrow_plan: str = "",
        category: str = "学习日志",
        status: str = "进行中",
        duration_minutes: int = 0,
        remark: str = "",
    ) -> None:
        self.create(
            {
                "date": log_date,
                "content": content,
                "tasks": tasks,
                "problems": problems,
                "tomorrow_plan": tomorrow_plan,
                "category": category,
                "status": status,
                "duration_minutes": duration_minutes,
                "remark": remark,
            }
        )

    def save_ai_message(
        self,
        role: str,
        content: str,
        plan_date: str = "",
        plan_text: str = "",
        applied: int = 0,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_messages (role, content, plan_date, plan_text, applied)
                VALUES (?, ?, ?, ?, ?)
                """,
                (role, content, plan_date, plan_text, applied),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_ai_messages(self, limit: int | None = None) -> list[sqlite3.Row]:
        with self.connect() as conn:
            if limit is None:
                rows = conn.execute("SELECT * FROM ai_messages ORDER BY id ASC").fetchall()
                return list(rows)
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM ai_messages
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return list(reversed(rows))

    def mark_ai_plan_applied(self, message_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE ai_messages SET applied = 1 WHERE id = ?", (message_id,))
            conn.commit()


def user_db_path(username: str) -> Path:
    safe = "".join(ch for ch in username.strip() if ch.isalnum() or ch in ("_", "-"))
    if not safe:
        safe = "default"
    target = USER_DB_DIR / f"{safe}.db"
    legacy = LEGACY_USER_DB_DIR / f"{safe}.db"
    if legacy.exists() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
    return target


def load_llm_config() -> dict[str, str | float]:
    for path in (APP_CONFIG_PATH, LOCAL_CONFIG_PATH):
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                config = json.load(f)
            break
    else:
        config = {}

    api_key = str(config.get("api_key") or os.getenv("PERSONAL_AGENT_API_KEY") or "").strip()
    return {
        "api_key": api_key,
        "base_url": str(config.get("base_url") or "https://api.deepseek.com/chat/completions").strip(),
        "model": str(config.get("model") or "deepseek-chat").strip(),
        "temperature": float(config.get("temperature", 0.4)),
    }


def call_chat_model(messages: list[dict[str, str]]) -> str:
    config = load_llm_config()
    api_key = str(config["api_key"])
    if not api_key:
        raise RuntimeError(f"未配置 API Key。请在 {APP_CONFIG_PATH} 或 config.local.json 中配置 api_key。")

    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        str(config["base_url"]),
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"模型接口返回错误：HTTP {exc.code}\n{detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接模型接口：{exc.reason}") from exc

    try:
        return result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"模型返回格式无法解析：{str(result)[:300]}") from exc


def remove_emoji(text: str) -> str:
    emoji_ranges = (
        (0x1F000, 0x1FAFF),
        (0x2600, 0x27BF),
        (0xFE00, 0xFE0F),
    )
    return "".join(
        char
        for char in text
        if not any(start <= ord(char) <= end for start, end in emoji_ranges)
    )


class CanvasDiaryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.repo: LogRepository | None = None
        self.username = ""
        self.login_mode = True
        self.root.geometry(f"{BASE_WIDTH}x{BASE_HEIGHT}")
        self.root.minsize(460, 314)
        self.root.aspect(BASE_WIDTH, BASE_HEIGHT, BASE_WIDTH, BASE_HEIGHT)
        self.root.overrideredirect(False)
        self.root.resizable(True, True)
        self.root.title("今日の学习手账")
        self.icon_photo: ImageTk.PhotoImage | None = None
        self.set_app_user_model_id()
        self.configure_window_icon()

        self.bg_source = Image.open(BG_PATH).convert("RGB") if BG_PATH.exists() else None
        self.ai_icon_source = Image.open(AI_ICON_PATH).convert("RGBA") if AI_ICON_PATH.exists() else None
        self.bg_photo: ImageTk.PhotoImage | None = None
        self.font_cache: dict[tuple[int, bool] | tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.values = {
            "login": "",
            "note": "",
            "todo": "",
            "plan": "",
            "tomorrow": "",
            "ai_query": "",
            "ai_answer": AI_DEFAULT_REPLY,
            "date": date.today().isoformat(),
            "mood": MOODS[0],
        }
        self.cursors = {key: len(value) for key, value in self.values.items()}
        self.active_field: str | None = "login"
        self.tomorrow_open = False
        self.calendar_open = False
        self.ai_open = False
        self.ai_messages: list[dict[str, str | int]] = []
        self.ai_scroll_offset = 0
        self.ai_scroll_max = 0
        self.ai_chat_box: tuple[int, int, int, int] | None = None
        self.pending_plan_message_id: int | None = None
        self.pending_plan_date = ""
        self.pending_plan_text = ""
        self.calendar_month = date.today().replace(day=1)
        self.hover_point: tuple[int, int] | None = None
        self.hovering_control = False
        self.dragging_title = False
        self.always_on_top = False
        self.caret_visible = True
        self.toast_text = ""
        self.buttons: list[tuple[str, tuple[int, int, int, int]]] = []
        self.fields: list[tuple[str, tuple[int, int, int, int]]] = []
        self.display_scale_x = 1.0
        self.display_scale_y = 1.0

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Key>", self.on_key)
        self.root.bind("<Configure>", self.on_resize)
        self.canvas.focus_set()
        self.root.after(500, self.blink_caret)
        self.root.after(200, self.show_in_taskbar)
        self.draw()

    def font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (size, bold)
        if key in self.font_cache:
            return self.font_cache[key]
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                self.font_cache[key] = font
                return font
            except OSError:
                continue
        font = ImageFont.load_default()
        self.font_cache[key] = font
        return font

    def kai_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = ("kai-bold" if bold else "kai", size)
        if key in self.font_cache:
            return self.font_cache[key]
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/simkai.ttf",
            "C:/Windows/Fonts/simkai.ttf",
            "C:/Windows/Fonts/kaiti.ttf",
            "C:/Windows/Fonts/STKAITI.TTF",
            "C:/Windows/Fonts/msyh.ttc",
        ]
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                self.font_cache[key] = font
                return font
            except OSError:
                continue
        font = ImageFont.load_default()
        self.font_cache[key] = font
        return font

    def set_app_user_model_id(self) -> None:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("huaixuexue.personal_learning_agent")
        except Exception:
            pass

    def configure_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            self.root.iconbitmap(default=str(ICON_PATH))
        except Exception:
            pass
        try:
            icon_image = Image.open(ICON_PATH).resize((32, 32), Image.Resampling.LANCZOS)
            self.icon_photo = ImageTk.PhotoImage(icon_image)
            self.root.iconphoto(True, self.icon_photo)
        except Exception:
            pass

    def on_resize(self, event: tk.Event) -> None:
        if event.widget == self.root:
            self.draw()

    def fill_background(self, width: int, height: int) -> Image.Image:
        width = max(width, 320)
        height = max(height, 240)
        if self.bg_source is None:
            return Image.new("RGB", (width, height), "#fff6fb")
        src_w, src_h = self.bg_source.size
        scale = max(width / src_w, height / src_h)
        new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
        resized = self.bg_source.resize(new_size, Image.Resampling.LANCZOS)
        left = max((new_size[0] - width) // 2, 0)
        top = max((new_size[1] - height) // 2, 0)
        return resized.crop((left, top, left + width, top + height)).convert("RGBA")

    def rounded(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1) -> None:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

    def draw(self) -> None:
        display_w = self.root.winfo_width()
        display_h = self.root.winfo_height()
        if display_w <= 1:
            display_w = BASE_WIDTH
        if display_h <= 1:
            display_h = BASE_HEIGHT
        w = BASE_WIDTH
        h = BASE_HEIGHT
        self.display_scale_x = display_w / w
        self.display_scale_y = display_h / h
        img = self.fill_background(w, h)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        self.buttons.clear()
        self.fields.clear()

        if self.login_mode:
            self.draw_login(draw, w, h)
            self.draw_input_text(draw)
            composed = Image.alpha_composite(img.convert("RGBA"), overlay)
            composed = composed.resize((display_w, display_h), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(composed)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
            return

        mx, my, mw, mh = 12, 12, w - 24, h - 24
        self.rounded(draw, (mx, my, mx + mw, my + mh), 12, PANEL, LINE)
        self.button(draw, "logout", (mx + 14, my + mh - 42, mx + 78, my + mh - 14), "退出")
        self.ai_button(draw, (mx + 18, my + 10, mx + 132, my + 40))
        pin_text = "取消置顶" if self.always_on_top else "置顶"
        self.button(draw, "topmost", (mx + mw - 86, my + 10, mx + mw - 18, my + 38), pin_text)

        compact = w < 660
        mood_box = (mx + 18, my + 48, mx + mw - 18, my + (128 if compact else 96))
        self.rounded(draw, mood_box, 10, BAR, LINE)
        mood_font = 16 if compact else 20
        self.text(draw, (mood_box[0] + 24, mood_box[1] + 24), "今日の心情：", mood_font, True, anchor="lm")
        if compact:
            self.button(draw, "mood", (mood_box[0] + 142, mood_box[1] + 10, mood_box[2] - 18, mood_box[1] + 38), self.values["mood"], fill=(247, 191, 220, 230))
            self.field(draw, "date", (mood_box[0] + 24, mood_box[1] + 48, mood_box[0] + 156, mood_box[1] + 76), single=True)
            self.button(draw, "calendar", (mood_box[0] + 168, mood_box[1] + 48, mood_box[0] + 224, mood_box[1] + 76), "日期")
        else:
            self.button(draw, "mood", (mood_box[0] + 178, mood_box[1] + 10, mood_box[0] + 346, mood_box[1] + 38), self.values["mood"], fill=(247, 191, 220, 230))
            self.field(draw, "date", (mood_box[2] - 238, mood_box[1] + 10, mood_box[2] - 112, mood_box[1] + 38), single=True)
            self.button(draw, "calendar", (mood_box[2] - 100, mood_box[1] + 10, mood_box[2] - 46, mood_box[1] + 38), "日期")

        top = mood_box[3] + 24
        bottom = my + mh - 62
        left_w = max(132, int(mw * 0.32))
        gap = 14
        left_x = mx + 18
        right_x = left_x + left_w + gap
        right_w = mx + mw - 18 - right_x

        label_gap = 34
        plan_h = max(64, int((bottom - top) * 0.42))
        self.text(draw, (left_x, top), "今日计划", 17, True, anchor="la")
        self.field(draw, "plan", (left_x, top + label_gap, left_x + left_w, top + label_gap + plan_h))

        todo_y = top + label_gap + plan_h + 22
        self.text(draw, (left_x, todo_y), "待解决事项", 17, True, anchor="la")
        self.field(draw, "todo", (left_x, todo_y + label_gap, left_x + left_w, bottom))

        header_y = top
        self.text(draw, (right_x, header_y), "今日笔记", 18, True, anchor="la")
        self.button(draw, "tomorrow", (right_x + right_w - 142, header_y - 4, right_x + right_w - 76, header_y + 24), "明日")
        self.button(draw, "save", (right_x + right_w - 66, header_y - 4, right_x + right_w, header_y + 24), "保存")
        self.field(draw, "note", (right_x, top + label_gap, right_x + right_w, bottom))

        if self.tomorrow_open:
            tx = int(w * 0.58)
            ty = int(h * 0.2)
            tw = int(w * 0.36)
            th = int(h * 0.56)
            self.rounded(draw, (tx, ty, tx + tw, ty + th), 14, (255, 247, 252, 186), LINE)
            self.text(draw, (tx + 16, ty + 18), "明日计划", 18, True, anchor="la")
            self.button(draw, "tomorrow_save", (tx + tw - 142, ty + 10, tx + tw - 82, ty + 38), "保存")
            self.button(draw, "tomorrow_close", (tx + tw - 74, ty + 10, tx + tw - 14, ty + 38), "返回")
            self.field(draw, "tomorrow", (tx + 14, ty + 52, tx + tw - 14, ty + th - 14))

        if self.calendar_open:
            self.draw_calendar(draw, w, h)

        self.draw_input_text(draw)

        if self.ai_open:
            self.draw_ai_panel(draw, w, h)
            self.draw_input_text(draw, only_names={"ai_query"})

        composed = Image.alpha_composite(img.convert("RGBA"), overlay)
        composed = composed.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(composed)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
        if self.toast_text:
            self.draw_toast()
        if self.hovering_control and self.hover_point is not None:
            self.canvas.create_text(self.hover_point[0] + 13, self.hover_point[1] - 13, text="♡", fill="#d783ae", font=("Microsoft YaHei UI", 16, "bold"))

    def draw_login(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        box_w, box_h = min(420, w - 60), 190
        x = (w - box_w) // 2
        y = (h - box_h) // 2
        self.rounded(draw, (x, y, x + box_w, y + box_h), 18, (255, 247, 252, 180), LINE)
        self.text(draw, (x + box_w // 2, y + 38), "登录你的学习手帐", 22, True, anchor="mm")
        self.text(draw, (x + 42, y + 82), "用户名", 16, True, anchor="la")
        self.field(draw, "login", (x + 42, y + 104, x + box_w - 42, y + 138), single=True)
        self.button(draw, "login", (x + box_w - 136, y + 150, x + box_w - 42, y + 180), "进入")

    def ai_button(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
        self.rounded(draw, box, 12, (255, 232, 244, 210), LINE)
        if self.ai_icon_source is not None:
            icon = self.ai_icon_source.resize((24, 24), Image.Resampling.LANCZOS)
            draw._image.alpha_composite(icon, (box[0] + 10, box[1] + 3))
        else:
            self.text(draw, (box[0] + 22, box[1] + 15), "♡", 16, True, anchor="mm", color="#d783ae")
        self.text(draw, (box[0] + 42, box[1] + 15), "AI助手", 14, True, anchor="lm")
        self.buttons.append(("ai_open", box))

    def draw_ai_panel(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        self.rounded(draw, (0, 0, w, h), 0, (255, 246, 251, 228), None)
        px, py = 34, 42
        pw, ph = w - 68, h - 72
        self.rounded(draw, (px, py, px + pw, py + ph), 18, (255, 247, 252, 242), LINE, width=2)
        if self.ai_icon_source is not None:
            icon = self.ai_icon_source.resize((42, 42), Image.Resampling.LANCZOS)
            draw._image.alpha_composite(icon, (px + 20, py + 16))
        self.text(draw, (px + 74, py + 36), "主人，来聊聊天吧~", 20, True, anchor="lm")
        if self.pending_plan_text:
            self.button(draw, "ai_apply_plan", (px + pw - 154, py + 18, px + pw - 88, py + 46), "应用")
        self.button(draw, "ai_close", (px + pw - 76, py + 18, px + pw - 18, py + 46), "返回")

        gap = 18
        left_w = int((pw - 54) * 0.62)
        right_w = pw - 36 - left_w - gap
        body_y = py + 74
        body_bottom = py + ph - 22
        left_x = px + 18
        right_x = left_x + left_w + gap
        self.text(draw, (left_x, body_y), "会话记忆：", 16, True, anchor="la")
        chat_box = (left_x, body_y + 30, left_x + left_w, body_bottom)
        self.ai_chat_box = chat_box
        self.rounded(draw, chat_box, 8, FIELD, LINE)
        self.draw_ai_conversation(draw, chat_box)
        self.text(draw, (right_x, body_y), "你想问 AI：", 16, True, anchor="la")
        self.field(draw, "ai_query", (right_x, body_y + 30, right_x + right_w, body_bottom - 42))
        self.button(draw, "ai_ask", (right_x + right_w - 72, body_bottom - 30, right_x + right_w, body_bottom), "发送")

    def draw_display_text(self, draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int]) -> None:
        x, y, x2, y2 = box
        font = self.kai_font(INPUT_FONT_SIZE + 2, True)
        if text in (AI_DEFAULT_REPLY, AI_THINKING_REPLY):
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text(
                (x + (x2 - x - text_w) / 2, y + (y2 - y - text_h) / 2 - 2),
                text,
                font=font,
                fill=INPUT_TEXT,
            )
            return
        line_height = self.input_line_height(font)
        lines = self.wrap_value_by_pixels(text, x2 - x - 20, font)
        shown = "\n".join(lines[: max(1, (y2 - y - 16) // line_height)])
        draw.multiline_text((x + 10, y + 9), shown, font=font, fill=INPUT_TEXT, spacing=4)

    def draw_ai_conversation(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
        x, y, x2, y2 = box
        font = self.kai_font(INPUT_FONT_SIZE + 1, True)
        view_w = x2 - x
        view_h = y2 - y
        layer = Image.new("RGBA", (view_w, view_h), (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        max_width = max(120, view_w - 92)
        line_height = self.input_line_height(font)
        blocks: list[tuple[str, list[str], int]] = []
        source = self.ai_messages if self.ai_messages else [{"role": "assistant", "content": AI_DEFAULT_REPLY}]
        for item in source:
            role = str(item.get("role", "assistant"))
            lines = self.wrap_value_by_pixels(str(item.get("content", "")), max_width, font)
            block_h = max(1, len(lines)) * line_height + 20
            blocks.append((role, lines, block_h))

        total_height = sum(block_h + 10 for _, _, block_h in blocks) + 14
        self.ai_scroll_max = max(0, total_height - (view_h - 24))
        self.ai_scroll_offset = max(0, min(self.ai_scroll_offset, self.ai_scroll_max))
        cursor_y = 12 - self.ai_scroll_offset

        for role, lines, block_h in blocks:
            if cursor_y + block_h < 8:
                cursor_y += block_h + 10
                continue
            if cursor_y > view_h - 12:
                break
            color = "#a86189" if role == "user" else INPUT_TEXT
            fill = (255, 232, 244, 170) if role == "user" else (255, 250, 253, 145)
            text_w = max((self.measure_font_text(font, line) for line in lines), default=0)
            bubble_w = min(view_w - 34, max(108, text_w + 24))
            bubble_x1 = view_w - 18 - bubble_w if role == "user" else 16
            bubble_x2 = bubble_x1 + bubble_w
            layer_draw.rounded_rectangle((bubble_x1, cursor_y, bubble_x2, cursor_y + block_h), radius=10, fill=fill, outline=LINE)
            layer_draw.multiline_text((bubble_x1 + 12, cursor_y + 10), "\n".join(lines), font=font, fill=color, spacing=4)
            cursor_y += block_h + 10

        if self.ai_scroll_max > 0:
            bar_x = view_w - 8
            bar_y1 = 12
            bar_h = view_h - 24
            thumb_h = max(24, int(bar_h * bar_h / max(total_height, 1)))
            thumb_y = bar_y1 + int((bar_h - thumb_h) * self.ai_scroll_offset / max(self.ai_scroll_max, 1))
            layer_draw.rounded_rectangle((bar_x, bar_y1, bar_x + 3, view_h - 12), radius=2, fill=(239, 190, 216, 120))
            layer_draw.rounded_rectangle((bar_x - 1, thumb_y, bar_x + 4, thumb_y + thumb_h), radius=3, fill=(216, 136, 180, 180))
        draw._image.alpha_composite(layer, (x, y))

    def draw_calendar(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        cal_w, cal_h = 322, 300
        x = w - cal_w - 42
        y = 110
        self.rounded(draw, (x, y, x + cal_w, y + cal_h), 16, (255, 247, 252, 210), LINE)
        title = self.calendar_month.strftime("%Y-%m")
        self.button(draw, "cal_prev", (x + 18, y + 16, x + 54, y + 44), "‹")
        self.text(draw, (x + cal_w // 2, y + 30), title, 18, True, anchor="mm")
        self.button(draw, "cal_next", (x + cal_w - 54, y + 16, x + cal_w - 18, y + 44), "›")

        week = ["一", "二", "三", "四", "五", "六", "日"]
        cell_w = 40
        start_x = x + 22
        start_y = y + 66
        for i, day in enumerate(week):
            self.text(draw, (start_x + i * cell_w + 20, start_y), day, 13, True, anchor="mm", color="#9a6b82")

        first = self.calendar_month
        offset = first.weekday()
        if first.month == 12:
            next_month = date(first.year + 1, 1, 1)
        else:
            next_month = date(first.year, first.month + 1, 1)
        days = (next_month - first).days
        for d in range(1, days + 1):
            idx = offset + d - 1
            row = idx // 7
            col = idx % 7
            bx = start_x + col * cell_w
            by = start_y + 18 + row * 34
            day_date = date(first.year, first.month, d).isoformat()
            fill = (247, 191, 220, 230) if day_date == self.values["date"] else PINK_BUTTON
            self.button(draw, f"cal_day:{day_date}", (bx + 4, by, bx + 36, by + 28), str(d), fill=fill)

    def text(self, draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, bold: bool = False, anchor: str = "la", color: str = TEXT) -> None:
        draw.text(xy, text, font=self.font(size, bold), fill=color, anchor=anchor)

    def button(self, draw: ImageDraw.ImageDraw, name: str, box: tuple[int, int, int, int], text: str, fill=PINK_BUTTON) -> None:
        self.rounded(draw, box, 10, fill, LINE)
        self.text(draw, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), text, 14, True, anchor="mm")
        self.buttons.append((name, box))

    def field(self, draw: ImageDraw.ImageDraw, name: str, box: tuple[int, int, int, int], single: bool = False) -> None:
        outline = (218, 136, 180, 210) if self.active_field == name else LINE
        self.rounded(draw, box, 8, FIELD, outline, width=2 if self.active_field == name else 1)
        self.fields.append((name, box))

    def draw_input_text(self, draw: ImageDraw.ImageDraw, only_names: set[str] | None = None) -> None:
        for name, box in self.fields:
            if only_names is not None and name not in only_names:
                continue
            value = self.values.get(name, "")
            x, y, x2, y2 = box
            if name == "date":
                font = self.font(INPUT_FONT_SIZE, True)
                text_y = y + ((y2 - y) - self.text_height(font)) // 2 - 1
                draw.text((x + 10, text_y), value, font=font, fill=INPUT_TEXT)
                if self.active_field == name and self.caret_visible:
                    pos = self.cursors.get(name, len(value))
                    prefix = value[:pos]
                    caret_x = min(x + 10 + self.measure_font_text(font, prefix) + 1, x2 - 12)
                    self.draw_caret(draw, caret_x, text_y, font)
                continue
            if name == "login":
                font = self.font(INPUT_FONT_SIZE, True)
                text_y = y + ((y2 - y) - self.text_height(font)) // 2 - 1
                draw.text((x + 10, text_y), value, font=font, fill=INPUT_TEXT)
                if self.active_field == name and self.caret_visible:
                    prefix = value[: self.cursors.get(name, len(value))]
                    caret_x = min(x + 10 + self.measure_font_text(font, prefix) + 1, x2 - 12)
                    self.draw_caret(draw, caret_x, text_y, font)
                continue
            font = self.font(INPUT_FONT_SIZE, True)
            line_height = self.input_line_height(font)
            lines = self.wrap_value_by_pixels(value, x2 - x - 20, font)
            shown = "\n".join(lines[: max(1, (y2 - y - 16) // line_height)])
            draw.multiline_text((x + 10, y + 9), shown, font=font, fill=INPUT_TEXT, spacing=4)
            if self.active_field == name and self.caret_visible:
                caret_x, caret_y = self.caret_xy(name, box, font)
                self.draw_caret(draw, caret_x, caret_y, font)

    def draw_caret(self, draw: ImageDraw.ImageDraw, x: int, text_y: int, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> None:
        height = self.text_height(font)
        y1 = text_y + 1
        draw.line((x, y1, x, y1 + height), fill="#d783ae", width=2)

    def draw_toast(self) -> None:
        w = max(self.root.winfo_width(), 1)
        h = max(self.root.winfo_height(), 1)
        y1 = (h - 48) // 2
        self.canvas.create_text(w // 2, y1 + 24, text=self.toast_text, fill=TOAST_TEXT, font=("Microsoft YaHei UI", 18, "bold"))

    def app_title(self) -> str:
        return f"{self.username}の学习手账" if self.username else "今日の学习手账"

    def show_toast(self, text: str, duration_ms: int = 1000) -> None:
        self.toast_text = text
        self.draw()
        self.root.after(duration_ms, self.clear_toast)

    def clear_toast(self) -> None:
        self.toast_text = ""
        self.draw()

    def caret_xy(self, name: str, box: tuple[int, int, int, int], font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int]:
        value = self.values.get(name, "")
        pos = max(0, min(self.cursors.get(name, len(value)), len(value)))
        x, y, x2, _ = box
        before = value[:pos]
        wrapped = self.wrap_value_by_pixels(before, x2 - x - 20, font)
        line = wrapped[-1] if wrapped else ""
        row = max(len(wrapped) - 1, 0)
        return min(x + 10 + self.measure_font_text(font, line) + 1, x2 - 16), y + 9 + row * self.input_line_height(font)

    def measure_text(self, text: str, size: int, bold: bool = False) -> int:
        if not text:
            return 0
        bbox = self.font(size, bold).getbbox(text)
        return bbox[2] - bbox[0]

    def measure_font_text(self, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> int:
        if not text:
            return 0
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def text_height(self, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
        bbox = font.getbbox("Hg")
        return bbox[3] - bbox[1]

    def input_line_height(self, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
        return self.text_height(font) + 4

    def wrap_value_by_pixels(self, value: str, max_width: int, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> list[str]:
        result: list[str] = []
        for paragraph in value.splitlines() or [""]:
            if paragraph == "":
                result.append("")
                continue
            line = ""
            for char in paragraph:
                if self.measure_font_text(font, line + char) <= max_width:
                    line += char
                else:
                    result.append(line)
                    line = char
            result.append(line)
        return result

    def wrap_value(self, value: str, width: int) -> list[str]:
        result: list[str] = []
        for paragraph in value.splitlines() or [""]:
            if not paragraph:
                result.append("")
            else:
                result.extend(textwrap.wrap(paragraph, width=width, replace_whitespace=False, drop_whitespace=False))
        return result

    def on_click(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        point = self.to_ui_point(event.x, event.y)
        if self.ai_open:
            for name, box in reversed(self.buttons):
                if name.startswith("ai_") and self.inside(point, box):
                    self.handle_button(name)
                    return
            for name, box in reversed(self.fields):
                if name == "ai_query" and self.inside(point, box):
                    self.active_field = name
                    self.cursors[name] = len(self.values.get(name, ""))
                    self.draw()
                    return
            self.active_field = None
            self.draw()
            return
        for name, box in reversed(self.buttons):
            if self.inside(point, box):
                self.handle_button(name)
                return
        for name, box in reversed(self.fields):
            if self.inside(point, box):
                self.active_field = name
                self.cursors[name] = len(self.values.get(name, ""))
                self.draw()
                return
        self.active_field = None
        self.draw()

    def on_release(self, _event: tk.Event) -> None:
        self.dragging_title = False

    def on_drag(self, event: tk.Event) -> None:
        if self.dragging_title:
            self.do_move(event)

    def on_motion(self, event: tk.Event) -> None:
        point = self.to_ui_point(event.x, event.y)
        if self.ai_open:
            hovering = any(
                self.inside(point, box)
                for name, box in self.buttons + self.fields
                if name.startswith("ai_") or name == "ai_query"
            )
        else:
            hovering = any(self.inside(point, box) for _, box in self.buttons + self.fields)
        self.canvas.configure(cursor="hand2" if hovering else "")
        self.hover_point = (event.x, event.y)
        if hovering != self.hovering_control or hovering:
            self.hovering_control = hovering
            self.draw()

    def on_mousewheel(self, event: tk.Event) -> None:
        if not self.ai_open or self.ai_scroll_max <= 0:
            return
        point = self.to_ui_point(event.x, event.y)
        if self.ai_chat_box is not None and not self.inside(point, self.ai_chat_box):
            return
        step = -1 if event.delta > 0 else 1
        self.ai_scroll_offset = max(0, min(self.ai_scroll_offset + step * 38, self.ai_scroll_max))
        self.draw()

    def inside(self, point: tuple[int, int], box: tuple[int, int, int, int]) -> bool:
        x, y = point
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def to_ui_point(self, x: int, y: int) -> tuple[int, int]:
        scale_x = self.display_scale_x or 1.0
        scale_y = self.display_scale_y or 1.0
        return int(x / scale_x), int(y / scale_y)

    def handle_button(self, name: str) -> None:
        if name == "topmost":
            self.toggle_topmost()
        elif name == "login":
            self.login()
        elif name == "logout":
            self.logout()
        elif name == "ai_open":
            self.ai_open = True
            self.values["ai_query"] = ""
            self.values["ai_answer"] = AI_DEFAULT_REPLY
            self.cursors["ai_query"] = 0
            self.cursors["ai_answer"] = len(AI_DEFAULT_REPLY)
            self.load_ai_memory()
            self.ai_scroll_offset = 10**9
            self.active_field = "ai_query"
        elif name == "ai_close":
            self.ai_open = False
            self.active_field = None
        elif name == "ai_ask":
            self.ask_ai()
        elif name == "ai_apply_plan":
            self.apply_ai_plan()
        elif name == "ai_scroll_up":
            self.ai_scroll_offset = max(0, self.ai_scroll_offset - 80)
        elif name == "ai_scroll_down":
            self.ai_scroll_offset = min(self.ai_scroll_max, self.ai_scroll_offset + 80)
        elif name == "mood":
            idx = MOODS.index(self.values["mood"]) if self.values["mood"] in MOODS else 0
            self.values["mood"] = MOODS[(idx + 1) % len(MOODS)]
        elif name == "calendar":
            self.calendar_open = not self.calendar_open
        elif name == "cal_prev":
            self.shift_calendar_month(-1)
        elif name == "cal_next":
            self.shift_calendar_month(1)
        elif name.startswith("cal_day:"):
            self.values["date"] = name.split(":", 1)[1]
            self.calendar_open = False
            self.load_selected_date()
        elif name == "save":
            self.save_log()
        elif name == "tomorrow":
            self.tomorrow_open = True
            self.active_field = "tomorrow"
        elif name == "tomorrow_save":
            self.save_tomorrow_plan()
        elif name == "tomorrow_close":
            self.tomorrow_open = False
            self.active_field = None
        self.draw()

    def on_key(self, event: tk.Event) -> None:
        if self.active_field is None:
            return
        key = event.keysym
        value = self.values.get(self.active_field, "")
        pos = max(0, min(self.cursors.get(self.active_field, len(value)), len(value)))
        if key == "BackSpace":
            if pos > 0:
                self.values[self.active_field] = value[: pos - 1] + value[pos:]
                self.cursors[self.active_field] = pos - 1
        elif key == "Left":
            self.cursors[self.active_field] = max(0, pos - 1)
        elif key == "Right":
            self.cursors[self.active_field] = min(len(value), pos + 1)
        elif key == "Home":
            self.cursors[self.active_field] = 0
        elif key == "End":
            self.cursors[self.active_field] = len(value)
        elif key == "Return":
            if self.login_mode and self.active_field == "login":
                self.login()
            elif self.active_field == "date":
                self.load_selected_date()
            else:
                self.values[self.active_field] = value[:pos] + "\n" + value[pos:]
                self.cursors[self.active_field] = pos + 1
        elif key == "Tab":
            self.focus_next()
        elif len(event.char) == 1 and event.char >= " ":
            if self.active_field == "date" and len(value) >= 10:
                return
            if self.active_field == "login" and len(value) >= 24:
                return
            self.values[self.active_field] = value[:pos] + event.char + value[pos:]
            self.cursors[self.active_field] = pos + 1
        self.draw()

    def focus_next(self) -> None:
        order = ["login"] if self.login_mode else ["plan", "todo", "note", "tomorrow", "ai_query", "date"]
        if self.active_field not in order:
            self.active_field = order[0]
            return
        self.active_field = order[(order.index(self.active_field) + 1) % len(order)]

    def ask_ai(self) -> None:
        query = self.values["ai_query"].strip()
        if not query:
            self.active_field = "ai_query"
            return

        if self.repo is None:
            self.ai_messages.append({"role": "assistant", "content": "请先登录账号，我才能读取这个用户的本地学习日志。"})
            self.active_field = "ai_query"
            return

        self.repo.save_ai_message("user", query)
        self.ai_messages.append({"role": "user", "content": query})
        self.values["ai_query"] = ""
        self.cursors["ai_query"] = 0
        self.ai_messages.append({"role": "assistant", "content": AI_THINKING_REPLY})
        self.ai_scroll_offset = 10**9
        self.active_field = "ai_query"
        self.draw()
        self.root.update_idletasks()

        try:
            logs = self.collect_ai_logs(query)
            context = self.format_logs_for_ai(logs)
            messages = self.build_ai_messages(query, context)
            answer = remove_emoji(call_chat_model(messages))
        except Exception as exc:
            answer = f"AI 调用失败：{exc}"

        if self.ai_messages and self.ai_messages[-1].get("content") == AI_THINKING_REPLY:
            self.ai_messages.pop()
        plan_date, plan_text = self.parse_ai_plan(query, answer)
        message_id = self.repo.save_ai_message("assistant", answer, plan_date=plan_date, plan_text=plan_text)
        self.ai_messages.append(
            {
                "id": message_id,
                "role": "assistant",
                "content": answer,
                "plan_date": plan_date,
                "plan_text": plan_text,
                "applied": 0,
            }
        )
        self.set_pending_plan(message_id, plan_date, plan_text)
        self.values["ai_answer"] = answer
        self.cursors["ai_answer"] = len(answer)
        self.active_field = "ai_query"
        self.ai_scroll_offset = 10**9
        self.draw()

    def collect_ai_logs(self, query: str) -> list[sqlite3.Row]:
        today = date.today()
        if "今天" in query:
            return self.repo.list_between(today.isoformat(), today.isoformat(), limit=10)
        if "昨天" in query:
            target = today - timedelta(days=1)
            return self.repo.list_between(target.isoformat(), target.isoformat(), limit=10)
        if "上周三" in query:
            start_this_week = today - timedelta(days=today.weekday())
            target = start_this_week - timedelta(days=5)
            return self.repo.list_between(target.isoformat(), target.isoformat(), limit=10)
        if "这个月" in query or "本月" in query:
            start = today.replace(day=1)
            return self.repo.list_between(start.isoformat(), today.isoformat(), limit=40)
        if "这周" in query or "本周" in query:
            start = today - timedelta(days=today.weekday())
            return self.repo.list_between(start.isoformat(), today.isoformat(), limit=20)
        if "最近" in query or "前几天" in query:
            return self.repo.list_recent(days=7, limit=20)

        keyword_hits = []
        for keyword in ("Agent", "agent", "论文", "项目", "计组", "计网", "开题"):
            if keyword in query:
                keyword_hits.extend(self.repo.search_text(keyword, limit=10))
        if keyword_hits:
            seen: set[int] = set()
            unique = []
            for row in keyword_hits:
                row_id = int(row["id"])
                if row_id not in seen:
                    seen.add(row_id)
                    unique.append(row)
            return unique[:20]

        return self.repo.list_recent(days=14, limit=25)

    def format_logs_for_ai(self, logs: list[sqlite3.Row]) -> str:
        if not logs:
            return "没有检索到相关日志。"
        chunks = []
        for row in reversed(logs):
            chunks.append(
                "\n".join(
                    [
                        f"日期：{row['date']}",
                        f"今日计划：{row['tasks'] or '无'}",
                        f"今日笔记：{self.extract_note(row['content'] or '') or '无'}",
                        f"待解决事项：{row['problems'] or '无'}",
                        f"明日计划：{row['tomorrow_plan'] or '无'}",
                    ]
                )
            )
        text = "\n\n---\n\n".join(chunks)
        return text[-7000:]

    def build_ai_messages(self, query: str, context: str) -> list[dict[str, str]]:
        planning = any(word in query for word in ("计划", "规划", "安排", "目标", "这周", "本周"))
        task = (
            "如果用户在请求规划，请根据历史日志、未完成事项和用户目标拆解成具体学习计划。"
            "任务要具体、可执行，并根据轻重缓急安排顺序。"
            "如果用户说的是今天、明天或某个具体日期，必须在回复第一行写【规划日期】YYYY-MM-DD。"
            "规划内容必须用 1. 2. 3. 这样的编号逐条列出，便于应用到计划。"
            if planning
            else "请直接回答用户问题。如果问题和学习日志有关，可以结合日志；如果只是普通聊天或通用知识问题，可以使用你的通用知识回答。只输出回答内容本身，不要额外添加固定小标题。"
        )
        history = self.format_ai_history_for_prompt()
        return [
            {
                "role": "system",
                "content": (
                    "你是一个可爱的个人学习管理 AI 助手。你既可以陪用户聊天，也可以回答通用知识问题。"
                    "当用户询问学习记录、项目进度或计划时，优先结合提供的本地学习日志；"
                    "如果日志没有相关信息，要明确说明没有查到对应记录，不要编造日志内容。"
                    "回答使用中文，语气温和自然，直接给出内容，不要套用固定格式。"
                    "禁止输出任何 emoji 或图形表情符号，因为桌面端可能显示为乱码；"
                    "如果需要表达语气，只能使用普通文本颜文字，例如 (＾▽＾)、(>_<)、(￣▽￣)。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"当前日期：{date.today().isoformat()}\n\n"
                    f"最近聊天记忆：\n{history}\n\n"
                    f"用户问题：{query}\n\n"
                    f"检索到的本地学习日志：\n{context}\n\n"
                    f"任务要求：{task}"
                ),
            },
        ]

    def format_ai_history_for_prompt(self) -> str:
        recent = self.ai_messages[-10:]
        if not recent:
            return "暂无历史聊天。"
        lines = []
        for item in recent:
            role = "用户" if item.get("role") == "user" else "AI"
            content = str(item.get("content", "")).strip()
            if content and content != AI_THINKING_REPLY:
                lines.append(f"{role}：{content}")
        return "\n".join(lines[-10:]) or "暂无历史聊天。"

    def load_ai_memory(self) -> None:
        self.pending_plan_message_id = None
        self.pending_plan_date = ""
        self.pending_plan_text = ""
        if self.repo is None:
            self.ai_messages = []
            return
        rows = self.repo.list_ai_messages(limit=None)
        self.ai_messages = [
            {
                "id": int(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "plan_date": row["plan_date"] or "",
                "plan_text": row["plan_text"] or "",
                "applied": int(row["applied"] or 0),
            }
            for row in rows
        ]
        for item in reversed(self.ai_messages):
            if item.get("role") == "assistant" and item.get("plan_text") and not int(item.get("applied") or 0):
                self.set_pending_plan(int(item["id"]), str(item.get("plan_date") or ""), str(item.get("plan_text") or ""))
                break
        self.ai_scroll_offset = 10**9

    def set_pending_plan(self, message_id: int, plan_date: str, plan_text: str) -> None:
        if not plan_text:
            self.pending_plan_message_id = None
            self.pending_plan_date = ""
            self.pending_plan_text = ""
            return
        self.pending_plan_message_id = message_id
        self.pending_plan_date = plan_date
        self.pending_plan_text = plan_text

    def parse_ai_plan(self, query: str, answer: str) -> tuple[str, str]:
        if not any(word in query for word in ("计划", "规划", "安排", "目标", "这周", "本周")):
            return "", ""
        plan_date = self.extract_plan_date(query, answer)
        plan_text = self.extract_plan_text(answer)
        return plan_date, plan_text

    def extract_plan_date(self, query: str, answer: str) -> str:
        today = date.today()
        if "明天" in query:
            return (today + timedelta(days=1)).isoformat()
        if "今天" in query:
            return today.isoformat()
        combined = f"{answer}\n{query}"
        match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", combined)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass
        return self.values["date"].strip() or today.isoformat()

    def extract_plan_text(self, answer: str) -> str:
        lines = []
        for raw in answer.splitlines():
            line = raw.strip()
            if not line or line.startswith("【规划日期】"):
                continue
            if re.match(r"^(\d+[\.\、]|[-*])\s*", line):
                lines.append(line)
        return "\n".join(lines) if lines else answer.strip()

    def apply_ai_plan(self) -> None:
        if self.repo is None:
            messagebox.showerror("应用失败", "请先登录")
            return
        if not self.pending_plan_text:
            self.show_toast("没有可应用的计划！")
            return
        target_date = self.pending_plan_date or self.values["date"].strip()
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            target_date = self.values["date"].strip()

        old = self.repo.latest_by_date(target_date)
        self.repo.create_snapshot(
            target_date,
            content=(old["content"] if old else "心情：开心 · 小心心\n\n"),
            tasks=self.pending_plan_text,
            problems=(old["problems"] if old else ""),
            tomorrow_plan=(old["tomorrow_plan"] if old else ""),
            category=(old["category"] if old else "学习日志"),
            status=(old["status"] if old else "进行中"),
            duration_minutes=(old["duration_minutes"] if old else 0),
            remark=(old["remark"] if old else ""),
        )
        if self.pending_plan_message_id is not None:
            self.repo.mark_ai_plan_applied(self.pending_plan_message_id)
            for item in self.ai_messages:
                if item.get("id") == self.pending_plan_message_id:
                    item["applied"] = 1
                    break
        self.values["date"] = target_date
        self.load_selected_date()
        self.pending_plan_message_id = None
        self.pending_plan_date = ""
        self.pending_plan_text = ""
        self.show_toast("计划已应用！")

    def shift_calendar_month(self, months: int) -> None:
        year = self.calendar_month.year
        month = self.calendar_month.month + months
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self.calendar_month = date(year, month, 1)

    def login(self) -> None:
        username = self.values["login"].strip()
        if not username:
            messagebox.showerror("鐧诲綍澶辫触", "璇疯緭鍏ョ敤鎴峰悕")
            return
        self.username = username
        self.root.title(self.app_title())
        self.repo = LogRepository(user_db_path(username))
        self.login_mode = False
        self.active_field = "plan"
        self.reset_form()
        self.load_selected_date()
        self.draw()

    def logout(self) -> None:
        self.repo = None
        self.username = ""
        self.root.title(self.app_title())
        self.login_mode = True
        self.active_field = "login"
        self.ai_open = False
        self.ai_messages = []
        self.pending_plan_message_id = None
        self.pending_plan_date = ""
        self.pending_plan_text = ""
        self.values.update({
            "login": "",
            "note": "",
            "todo": "",
            "plan": "",
            "tomorrow": "",
            "ai_query": "",
            "ai_answer": AI_DEFAULT_REPLY,
            "date": date.today().isoformat(),
            "mood": MOODS[0],
        })
        self.cursors = {key: len(value) for key, value in self.values.items()}
        self.draw()

    def blink_caret(self) -> None:
        self.caret_visible = not self.caret_visible
        if self.active_field is not None:
            self.draw()
        self.root.after(500, self.blink_caret)

    def start_move(self, event: tk.Event) -> None:
        self.drag_x = event.x
        self.drag_y = event.y

    def do_move(self, event: tk.Event) -> None:
        x = self.root.winfo_pointerx() - self.drag_x
        y = self.root.winfo_pointery() - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def minimize_window(self) -> None:
        self.root.iconify()

    def toggle_topmost(self) -> None:
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)

    def restore_custom_title(self) -> None:
        if self.root.state() == "normal":
            self.root.overrideredirect(False)
            self.root.after(100, self.show_in_taskbar)
        else:
            self.root.after(200, self.restore_custom_title)

    def show_in_taskbar(self) -> None:
        try:
            self.configure_window_icon()
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            gwl_exstyle = -20
            ws_ex_appwindow = 0x00040000
            ws_ex_toolwindow = 0x00000080
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_nozorder = 0x0004
            swp_framechanged = 0x0020
            get_window_long = ctypes.windll.user32.GetWindowLongW
            set_window_long = ctypes.windll.user32.SetWindowLongW
            set_window_pos = ctypes.windll.user32.SetWindowPos
            style = get_window_long(hwnd, gwl_exstyle)
            style = (style & ~ws_ex_toolwindow) | ws_ex_appwindow
            set_window_long(hwnd, gwl_exstyle, style)
            set_window_pos(hwnd, 0, 0, 0, 0, 0, swp_nomove | swp_nosize | swp_nozorder | swp_framechanged)
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)
        except Exception:
            pass

    def reset_form(self) -> None:
        self.values.update(
            {
                "note": "",
                "todo": "",
                "plan": "",
                "tomorrow": "",
                "date": date.today().isoformat(),
                "mood": MOODS[0],
            }
        )
        for key, value in self.values.items():
            self.cursors[key] = len(value)
        self.draw()

    def extract_note(self, content: str) -> str:
        if content.startswith("心情：") and "\n\n" in content:
            mood_line, note = content.split("\n\n", 1)
            mood = mood_line.replace("心情：", "").strip()
            if mood:
                self.values["mood"] = mood
            return note
        return content

    def load_selected_date(self) -> None:
        if self.repo is None:
            return
        selected_date = self.values["date"].strip()
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("日期格式错误", "日期格式应为 YYYY-MM-DD，例如 2026-06-12")
            return

        log = self.repo.latest_by_date(selected_date)
        if log is None:
            self.values["note"] = ""
            self.values["plan"] = ""
            self.values["todo"] = ""
            self.values["tomorrow"] = ""
            for key in ("note", "plan", "todo", "tomorrow"):
                self.cursors[key] = 0
            return

        self.values["note"] = self.extract_note(log["content"] or "")
        self.values["plan"] = log["tasks"] or ""
        self.values["todo"] = log["problems"] or ""
        self.values["tomorrow"] = log["tomorrow_plan"] or ""
        for key in ("note", "plan", "todo", "tomorrow"):
            self.cursors[key] = len(self.values[key])

    def save_tomorrow_plan(self) -> None:
        if self.repo is None:
            messagebox.showerror("保存失败", "请先登录")
            return
        try:
            current_day = datetime.strptime(self.values["date"].strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("日期格式错误", "日期格式应为 YYYY-MM-DD，例如 2026-06-12")
            return

        tomorrow_text = self.values["tomorrow"].strip()
        if not tomorrow_text:
            self.show_toast("明日计划为空")
            return

        current_date = current_day.isoformat()
        next_date = (current_day + timedelta(days=1)).isoformat()
        note = self.values["note"].strip()
        current_content = f"心情：{self.values['mood']}\n\n{note}" if note else f"心情：{self.values['mood']}\n\n"

        try:
            self.repo.create_snapshot(
                current_date,
                content=current_content,
                tasks=self.values["plan"].strip(),
                problems=self.values["todo"].strip(),
                tomorrow_plan=tomorrow_text,
            )

            next_log = self.repo.latest_by_date(next_date)
            if next_log is None:
                self.repo.create_snapshot(
                    next_date,
                    content="心情：开心 · 小心心\n\n",
                    tasks=tomorrow_text,
                )
            else:
                self.repo.create_snapshot(
                    next_date,
                    content=next_log["content"] or "心情：开心 · 小心心\n\n",
                    tasks=tomorrow_text,
                    problems=next_log["problems"] or "",
                    tomorrow_plan=next_log["tomorrow_plan"] or "",
                    category=next_log["category"] or "学习日志",
                    status=next_log["status"] or "进行中",
                    duration_minutes=next_log["duration_minutes"] or 0,
                    remark=next_log["remark"] or "",
                )
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return

        self.tomorrow_open = False
        self.active_field = None
        self.show_toast("明日计划已保存！")

    def save_log(self) -> None:
        if self.repo is None:
            messagebox.showerror("保存失败", "请先登录")
            return
        try:
            datetime.strptime(self.values["date"].strip(), "%Y-%m-%d")
            note = self.values["note"].strip()
            if not note:
                raise ValueError("今日笔记不能为空")
            self.repo.create(
                {
                    "date": self.values["date"].strip(),
                    "content": f"心情：{self.values['mood']}\n\n{note}",
                    "tasks": self.values["plan"].strip(),
                    "problems": self.values["todo"].strip(),
                    "tomorrow_plan": self.values["tomorrow"].strip(),
                    "category": "学习日志",
                    "status": "进行中",
                    "duration_minutes": 0,
                    "remark": "",
                }
            )
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self.show_toast("保存成功！")


def main() -> None:
    root = tk.Tk()
    CanvasDiaryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
