const form = document.querySelector("#logForm");
const resetButton = document.querySelector("#resetButton");
const refreshButton = document.querySelector("#refreshButton");
const searchButton = document.querySelector("#searchButton");
const logList = document.querySelector("#logList");
const message = document.querySelector("#message");
const totalCount = document.querySelector("#totalCount");
const totalMinutes = document.querySelector("#totalMinutes");
const serviceStatus = document.querySelector("#serviceStatus");

const fields = [
  "date",
  "content",
  "tasks",
  "problems",
  "tomorrow_plan",
  "category",
  "status",
  "duration_minutes",
  "remark",
];

function todayText() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function showMessage(text, type = "info") {
  message.textContent = text;
  message.hidden = false;
  message.classList.toggle("error", type === "error");
  window.setTimeout(() => {
    message.hidden = true;
  }, 2600);
}

function readForm() {
  const payload = {};
  for (const field of fields) {
    const element = document.querySelector(`#${field}`);
    payload[field] = element.value.trim();
  }
  payload.duration_minutes = Number(payload.duration_minutes || 0);
  return payload;
}

function resetForm() {
  form.reset();
  document.querySelector("#date").value = todayText();
  document.querySelector("#duration_minutes").value = 60;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function line(label, value) {
  if (!value) {
    return "";
  }
  return `<p><span class="log-label">${label}：</span>${escapeHtml(value)}</p>`;
}

function renderLogs(logs) {
  totalCount.textContent = logs.length;
  totalMinutes.textContent = logs.reduce((sum, log) => sum + Number(log.duration_minutes || 0), 0);

  if (logs.length === 0) {
    logList.innerHTML = `<div class="empty">暂无学习日志。先在左侧保存一条记录。</div>`;
    return;
  }

  logList.innerHTML = logs
    .map((log) => {
      const category = log.category || "未分类";
      const minutes = Number(log.duration_minutes || 0);
      return `
        <article class="log-item">
          <div class="log-item-head">
            <div>
              <div class="log-date">${escapeHtml(log.date)}</div>
              <div class="log-meta">
                <span class="tag">${escapeHtml(category)}</span>
                <span class="tag">${escapeHtml(log.status)}</span>
                <span class="tag">${minutes} 分钟</span>
              </div>
            </div>
            <button class="delete-button" type="button" data-id="${log.id}">删除</button>
          </div>
          <div class="log-body">
            ${line("原始记录", log.content)}
            ${line("今日任务", log.tasks)}
            ${line("遇到问题", log.problems)}
            ${line("明日计划", log.tomorrow_plan)}
            ${line("备注", log.remark)}
          </div>
        </article>
      `;
    })
    .join("");
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error("服务异常");
    }
    serviceStatus.textContent = "服务正常";
    serviceStatus.classList.add("ok");
    serviceStatus.classList.remove("bad");
  } catch (error) {
    serviceStatus.textContent = "服务未连接";
    serviceStatus.classList.add("bad");
    serviceStatus.classList.remove("ok");
  }
}

async function loadLogs() {
  const params = new URLSearchParams();
  const date = document.querySelector("#filterDate").value;
  const keyword = document.querySelector("#filterKeyword").value.trim();

  if (date) {
    params.set("date", date);
  }
  if (keyword) {
    params.set("keyword", keyword);
  }

  const url = params.toString() ? `/api/logs?${params}` : "/api/logs";
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("加载日志失败");
  }
  renderLogs(await response.json());
}

async function saveLog(event) {
  event.preventDefault();
  const payload = readForm();

  const response = await fetch("/api/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "保存失败");
  }

  resetForm();
  await loadLogs();
  showMessage("学习日志已保存");
}

async function deleteLog(id) {
  const response = await fetch(`/api/logs/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("删除失败");
  }
  await loadLogs();
  showMessage("学习日志已删除");
}

form.addEventListener("submit", (event) => {
  saveLog(event).catch((error) => showMessage(error.message, "error"));
});

resetButton.addEventListener("click", resetForm);
refreshButton.addEventListener("click", () => {
  document.querySelector("#filterDate").value = "";
  document.querySelector("#filterKeyword").value = "";
  loadLogs().catch((error) => showMessage(error.message, "error"));
});
searchButton.addEventListener("click", () => {
  loadLogs().catch((error) => showMessage(error.message, "error"));
});

logList.addEventListener("click", (event) => {
  const button = event.target.closest(".delete-button");
  if (!button) {
    return;
  }
  deleteLog(button.dataset.id).catch((error) => showMessage(error.message, "error"));
});

resetForm();
checkHealth();
loadLogs().catch((error) => showMessage(error.message, "error"));
