#python -m PyInstaller --noconfirm --windowed --onefile --name "PersonalLearningAgent" --icon "assets/app_icon.ico" --add-data "assets;assets" desktop_app.py
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import textwrap
import tkinter as tk
import ctypes
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageFont, ImageTk


PROJECT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PersonalLearningAgent"
USER_DB_DIR = APP_DATA_DIR / "data" / "users"
LEGACY_USER_DB_DIR = PROJECT_DIR / "data" / "users"
BG_PATH = BUNDLE_DIR / "assets" / "anime_study_background.png"
ICON_PATH = BUNDLE_DIR / "assets" / "app_icon.ico"

TEXT = "#65465b"
PINK_BUTTON = (251, 225, 239, 218)
PANEL = (255, 247, 252, 112)
FIELD = (255, 250, 253, 88)
BAR = (249, 223, 237, 178)
LINE = (239, 190, 216, 160)
MOODS = ["开心 · 小心心", "平静 · 云朵", "有动力 · 星光", "有点累 · 休息", "焦虑 · 深呼吸", "想摆烂 · 充电"]
INPUT_TEXT = "#d783ae"
TOAST_TEXT = "#efb6d4"
INPUT_FONT_SIZE = 16


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


class CanvasDiaryApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.repo: LogRepository | None = None
        self.username = ""
        self.login_mode = True
        self.root.geometry("820x560")
        self.root.minsize(560, 400)
        self.root.overrideredirect(True)
        self.root.title("今日の学习手账")
        self.icon_photo: ImageTk.PhotoImage | None = None
        self.set_app_user_model_id()
        self.configure_window_icon()

        self.bg_source = Image.open(BG_PATH).convert("RGB") if BG_PATH.exists() else None
        self.bg_photo: ImageTk.PhotoImage | None = None
        self.font_cache: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.values = {
            "login": "",
            "note": "",
            "todo": "",
            "plan": "",
            "tomorrow": "",
            "date": date.today().isoformat(),
            "mood": MOODS[0],
        }
        self.cursors = {key: len(value) for key, value in self.values.items()}
        self.active_field: str | None = "login"
        self.tomorrow_open = False
        self.calendar_open = False
        self.calendar_month = date.today().replace(day=1)
        self.hover_point: tuple[int, int] | None = None
        self.hovering_control = False
        self.dragging_title = False
        self.always_on_top = False
        self.caret_visible = True
        self.toast_text = ""
        self.buttons: list[tuple[str, tuple[int, int, int, int]]] = []
        self.fields: list[tuple[str, tuple[int, int, int, int]]] = []

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Motion>", self.on_motion)
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
        w = max(self.root.winfo_width(), 760)
        h = max(self.root.winfo_height(), 520)
        img = self.fill_background(w, h)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        self.buttons.clear()
        self.fields.clear()

        self.rounded(draw, (0, 0, w, 24), 0, BAR, LINE)
        self.text(draw, (w // 2, 12), self.app_title(), 13, True, anchor="mm")
        pin_text = "取消" if self.always_on_top else "置顶"
        self.button(draw, "topmost", (w - 124, 3, w - 76, 21), pin_text)
        self.button(draw, "min", (w - 68, 3, w - 40, 21), "—")
        self.button(draw, "close", (w - 34, 3, w - 8, 21), "×")

        if self.login_mode:
            self.draw_login(draw, w, h)
            self.draw_input_text(draw)
            composed = Image.alpha_composite(img.convert("RGBA"), overlay)
            self.bg_photo = ImageTk.PhotoImage(composed)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
            return

        mx, my, mw, mh = 14, 36, w - 28, h - 50
        self.rounded(draw, (mx, my, mx + mw, my + mh), 12, PANEL, LINE)
        self.button(draw, "logout", (mx + 14, my + mh - 42, mx + 78, my + mh - 14), "退出")

        mood_box = (mx + 18, my + 16, mx + mw - 18, my + 64)
        self.rounded(draw, mood_box, 10, BAR, LINE)
        self.text(draw, (mood_box[0] + 24, mood_box[1] + 24), "今日の心情：", 20, True, anchor="lm")
        self.button(draw, "mood", (mood_box[0] + 178, mood_box[1] + 10, mood_box[0] + 310, mood_box[1] + 38), self.values["mood"], fill=(247, 191, 220, 230))
        self.field(draw, "date", (mood_box[2] - 198, mood_box[1] + 10, mood_box[2] - 74, mood_box[1] + 38), single=True)
        self.button(draw, "calendar", (mood_box[2] - 66, mood_box[1] + 10, mood_box[2] - 14, mood_box[1] + 38), "日期")

        top = my + 84
        bottom = my + mh - 62
        left_w = int(mw * 0.32)
        gap = 14
        left_x = mx + 18
        right_x = left_x + left_w + gap
        right_w = mx + mw - 18 - right_x

        plan_h = int((bottom - top) * 0.42)
        self.text(draw, (left_x, top), "今日计划", 17, True, anchor="la")
        self.field(draw, "plan", (left_x, top + 26, left_x + left_w, top + 26 + plan_h))

        todo_y = top + 26 + plan_h + 26
        self.text(draw, (left_x, todo_y), "待解决事项", 17, True, anchor="la")
        self.field(draw, "todo", (left_x, todo_y + 26, left_x + left_w, bottom))

        header_y = top
        self.text(draw, (right_x, header_y), "今日笔记", 18, True, anchor="la")
        self.button(draw, "tomorrow", (right_x + right_w - 142, header_y - 4, right_x + right_w - 76, header_y + 24), "明日")
        self.button(draw, "save", (right_x + right_w - 66, header_y - 4, right_x + right_w, header_y + 24), "保存")
        self.field(draw, "note", (right_x, top + 26, right_x + right_w, bottom))

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
        composed = Image.alpha_composite(img.convert("RGBA"), overlay)
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

    def draw_input_text(self, draw: ImageDraw.ImageDraw) -> None:
        for name, box in self.fields:
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
        w = max(self.root.winfo_width(), 760)
        h = max(self.root.winfo_height(), 520)
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
        point = (event.x, event.y)
        for name, box in reversed(self.buttons):
            if self.inside(point, box):
                self.handle_button(name)
                return
        if event.y <= 24:
            self.start_move(event)
            self.dragging_title = True
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
        point = (event.x, event.y)
        hovering = any(self.inside(point, box) for _, box in self.buttons + self.fields)
        self.canvas.configure(cursor="hand2" if hovering else "")
        self.hover_point = point
        if hovering != self.hovering_control or hovering:
            self.hovering_control = hovering
            self.draw()

    def inside(self, point: tuple[int, int], box: tuple[int, int, int, int]) -> bool:
        x, y = point
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def handle_button(self, name: str) -> None:
        if name == "close":
            self.root.destroy()
        elif name == "min":
            self.minimize_window()
        elif name == "topmost":
            self.toggle_topmost()
        elif name == "login":
            self.login()
        elif name == "logout":
            self.logout()
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
        order = ["login"] if self.login_mode else ["plan", "todo", "note", "tomorrow", "date"]
        if self.active_field not in order:
            self.active_field = order[0]
            return
        self.active_field = order[(order.index(self.active_field) + 1) % len(order)]

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
        self.values.update({"login": "", "note": "", "todo": "", "plan": "", "tomorrow": "", "date": date.today().isoformat(), "mood": MOODS[0]})
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
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.after(200, self.restore_custom_title)

    def toggle_topmost(self) -> None:
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)

    def restore_custom_title(self) -> None:
        if self.root.state() == "normal":
            self.root.overrideredirect(True)
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
