from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import AIMessage, LearningLog
from app.services import file_service
from app.services.log_service import normalize_username
from app.services.profile_service import format_profile_for_prompt

PROJECT_DIR = Path(__file__).resolve().parents[2]
APP_CONFIG_PATH = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PersonalLearningAgent" / "config.json"
LOCAL_CONFIG_PATH = PROJECT_DIR / "config.local.json"
AI_THINKING_REPLY = "别着急，我在努力思考哦~"


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
        "base_url": str(config.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").strip(),
        "model": str(config.get("model") or "qwen-plus").strip(),
        "temperature": float(config.get("temperature", 0.4)),
    }


def call_chat_model(messages: list[dict[str, str]]) -> str:
    config = load_llm_config()
    api_key = str(config["api_key"])
    if not api_key:
        raise RuntimeError("未配置 API Key。请在 config.local.json 或本地应用配置中配置 api_key。")

    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
    }
    request = urllib.request.Request(
        str(config["base_url"]),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
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


def extract_note(content: str) -> str:
    if content.startswith("心情：") and "\n\n" in content:
        return content.split("\n\n", 1)[1]
    return content


def base_log_query(db: Session, username: str):
    return db.query(LearningLog).filter(LearningLog.username == normalize_username(username))


def collect_logs(db: Session, username: str, query: str) -> list[LearningLog]:
    today = date.today()
    logs_query = base_log_query(db, username)
    if "今天" in query:
        return logs_query.filter(LearningLog.date == today).order_by(LearningLog.id.desc()).limit(10).all()
    if "昨天" in query:
        target = today - timedelta(days=1)
        return logs_query.filter(LearningLog.date == target).order_by(LearningLog.id.desc()).limit(10).all()
    if "上周三" in query:
        start_this_week = today - timedelta(days=today.weekday())
        target = start_this_week - timedelta(days=5)
        return logs_query.filter(LearningLog.date == target).order_by(LearningLog.id.desc()).limit(10).all()
    if "这个月" in query or "本月" in query:
        start = today.replace(day=1)
        return logs_query.filter(LearningLog.date.between(start, today)).order_by(LearningLog.date.desc(), LearningLog.id.desc()).limit(40).all()
    if "这周" in query or "本周" in query:
        start = today - timedelta(days=today.weekday())
        return logs_query.filter(LearningLog.date.between(start, today)).order_by(LearningLog.date.desc(), LearningLog.id.desc()).limit(20).all()
    if "最近" in query or "前几天" in query:
        start = today - timedelta(days=6)
        return logs_query.filter(LearningLog.date.between(start, today)).order_by(LearningLog.date.desc(), LearningLog.id.desc()).limit(20).all()

    keyword_hits: list[LearningLog] = []
    for keyword in ("Agent", "agent", "论文", "项目", "计组", "计网", "开题"):
        if keyword in query:
            pattern = f"%{keyword}%"
            keyword_hits.extend(
                logs_query.filter(
                    or_(
                        LearningLog.content.like(pattern),
                        LearningLog.tasks.like(pattern),
                        LearningLog.problems.like(pattern),
                        LearningLog.tomorrow_plan.like(pattern),
                    )
                )
                .order_by(LearningLog.date.desc(), LearningLog.id.desc())
                .limit(10)
                .all()
            )
    if keyword_hits:
        seen: set[int] = set()
        unique: list[LearningLog] = []
        for row in keyword_hits:
            if row.id not in seen:
                seen.add(row.id)
                unique.append(row)
        return unique[:20]

    start = today - timedelta(days=13)
    return logs_query.filter(LearningLog.date.between(start, today)).order_by(LearningLog.date.desc(), LearningLog.id.desc()).limit(25).all()


def format_logs_for_ai(logs: list[LearningLog]) -> str:
    if not logs:
        return "没有检索到相关日志。"
    chunks = []
    for row in reversed(logs):
        chunks.append(
            "\n".join(
                [
                    f"日期：{row.date}",
                    f"今日计划：{row.tasks or '无'}",
                    f"今日笔记：{extract_note(row.content or '') or '无'}",
                    f"待解决事项：{row.problems or '无'}",
                    f"明日计划：{row.tomorrow_plan or '无'}",
                ]
            )
        )
    return "\n\n---\n\n".join(chunks)[-7000:]


def format_ai_history_for_prompt(db: Session, username: str) -> str:
    rows = (
        db.query(AIMessage)
        .filter(AIMessage.username == normalize_username(username))
        .order_by(AIMessage.id.desc())
        .limit(10)
        .all()
    )
    lines = []
    for item in reversed(rows):
        role = "用户" if item.role == "user" else "AI"
        content = (item.content or "").strip()
        if content and content != AI_THINKING_REPLY:
            lines.append(f"{role}：{content}")
    return "\n".join(lines) or "暂无历史聊天。"


def build_ai_messages(db: Session, username: str, query: str, context: str, file_context: str = "") -> list[dict[str, str]]:
    planning = any(word in query for word in ("计划", "规划", "安排", "目标", "这周", "本周"))
    task = (
        "如果用户在请求规划，请根据历史日志、未完成事项和用户目标拆解成具体学习计划。"
        "任务要具体、可执行，并根据轻重缓急安排顺序。"
        "如果用户说的是今天、明天或某个具体日期，必须在回复第一行写【规划日期】YYYY-MM-DD。"
        "规划内容必须用 1. 2. 3. 这样的编号逐条列出，便于应用到计划。"
        if planning
        else "请直接回答用户问题。如果问题和学习日志有关，可以结合日志；如果只是普通聊天或通用知识问题，可以使用你的通用知识回答。只输出回答内容本身，不要额外添加固定小标题。"
    )
    if planning:
        task += (
            "\n规划输出必须方便程序拆成计划项：只输出一组编号任务。"
            "每一条以 `1. `、`2. ` 这样的格式开头，不要使用表格，不要把多个任务写在同一行。"
            "每条任务应包含具体动作、对象和可执行标准。"
        )
    return [
        {
            "role": "system",
            "content": (
                "你是一个可爱的个人学习管理 AI 助手。你既可以陪用户聊天，也可以回答通用知识问题。"
                "当用户询问学习记录、项目进度或计划时，优先结合提供的本地学习日志；"
                "如果日志没有相关信息，要明确说明没有查到对应记录，不要编造日志内容。"
                "回答使用中文，语气温和自然，直接给出内容，不要套用固定格式。"
                "禁止输出任何 emoji 或图形表情符号；如果需要表达语气，只能使用普通文本颜文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"当前日期：{date.today().isoformat()}\n\n"
                f"用户学习数字孪生画像：\n{format_profile_for_prompt(db, username)}\n\n"
                f"最近聊天记忆：\n{format_ai_history_for_prompt(db, username)}\n\n"
                f"用户问题：{query}\n\n"
                f"检索到的本地学习日志：\n{context}\n\n"
                f"用户上传文件上下文：\n{file_context or '本次没有选择上传文件。'}\n\n"
                f"任务要求：{task}"
            ),
        },
    ]


def extract_plan_date(query: str, answer: str, selected_date: date | None) -> str:
    today = date.today()
    if "明天" in query:
        return (today + timedelta(days=1)).isoformat()
    if "今天" in query:
        return today.isoformat()
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", f"{answer}\n{query}")
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass
    return (selected_date or today).isoformat()


def extract_plan_text(answer: str) -> str:
    lines = []
    for raw in answer.splitlines():
        line = raw.strip()
        if not line or line.startswith("【规划日期】"):
            continue
        if re.match(r"^(\d+[\.\、]|[-*])\s*", line):
            lines.append(line)
    return "\n".join(lines) if lines else answer.strip()


def normalize_plan_text(answer: str) -> str:
    lines = []
    for raw in answer.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("【") or line.lower().startswith(("date:", "plan date:")):
            continue
        match = re.match(r"^(\d+)[\.\、\)]\s*(.+)$", line)
        if match:
            lines.append(f"{len(lines) + 1}. {match.group(2).strip()}")
        elif line.startswith(("- ", "* ")):
            lines.append(f"{len(lines) + 1}. {line[2:].strip()}")
    return "\n".join(lines) if lines else extract_plan_text(answer)


def parse_ai_plan(query: str, answer: str, selected_date: date | None) -> tuple[str, str]:
    if not any(word in query for word in ("计划", "规划", "安排", "目标", "这周", "本周")):
        return "", ""
    return extract_plan_date(query, answer, selected_date), normalize_plan_text(answer)


def save_message(
    db: Session,
    username: str,
    role: str,
    content: str,
    plan_date: str = "",
    plan_text: str = "",
    applied: int = 0,
) -> AIMessage:
    message = AIMessage(
        username=normalize_username(username),
        role=role,
        content=content,
        plan_date=plan_date,
        plan_text=plan_text,
        applied=applied,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def chat(
    db: Session,
    username: str,
    query: str,
    selected_date: date | None,
    file_ids: list[int] | None = None,
) -> AIMessage:
    save_message(db, username, "user", query)
    context = format_logs_for_ai(collect_logs(db, username, query))
    selected_files = []
    for file_id in file_ids or []:
        uploaded = file_service.get_file(db, username, file_id)
        if uploaded is not None:
            selected_files.append(file_service.ensure_extracted_text(db, uploaded))
    file_context = file_service.format_files_for_prompt(selected_files)
    answer = remove_emoji(call_chat_model(build_ai_messages(db, username, query, context, file_context)))
    plan_date, plan_text = parse_ai_plan(query, answer, selected_date)
    return save_message(db, username, "assistant", answer, plan_date=plan_date, plan_text=plan_text)
