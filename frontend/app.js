const loginPanel = document.querySelector("#loginPanel");
const diaryPanel = document.querySelector("#diaryPanel");
const loginName = document.querySelector("#loginName");
const loginPassword = document.querySelector("#loginPassword");
const loginButton = document.querySelector("#loginButton");
const logoutButton = document.querySelector("#logoutButton");
const userChip = document.querySelector("#userChip");
const form = document.querySelector("#logForm");
const toast = document.querySelector("#toast");
const logList = document.querySelector("#logList");
const message = document.querySelector("#message");
const aiMessages = document.querySelector("#aiMessages");
const applyPlanButton = document.querySelector("#applyPlanButton");
const exportToggle = document.querySelector("#exportToggle");
const exportStartDate = document.querySelector("#exportStartDate");
const exportEndDate = document.querySelector("#exportEndDate");
const exportConfirm = document.querySelector("#exportConfirm");
const profileToggle = document.querySelector("#profileToggle");
const profileSave = document.querySelector("#profileSave");
const planItems = document.querySelector("#planItems");
const newPlanButton = document.querySelector("#newPlanButton");
const deletePlanButton = document.querySelector("#deletePlanButton");
const aiUpload = document.querySelector("#aiUpload");
const aiFileInput = document.querySelector("#aiFileInput");
const aiFileHint = document.querySelector("#aiFileHint");
const databaseToggle = document.querySelector("#databaseToggle");
const databaseUpload = document.querySelector("#databaseUpload");
const databaseDownload = document.querySelector("#databaseDownload");
const databaseFileInput = document.querySelector("#databaseFileInput");
const databaseDate = document.querySelector("#databaseDate");
const databaseDateSearch = document.querySelector("#databaseDateSearch");
const databaseKeyword = document.querySelector("#databaseKeyword");
const databaseKeywordSearch = document.querySelector("#databaseKeywordSearch");
const databaseClearSearch = document.querySelector("#databaseClearSearch");
const todayFiles = document.querySelector("#todayFiles");
const historyFiles = document.querySelector("#historyFiles");

const profileFields = [
  "professional_identity",
  "research_direction",
  "goal_profile",
  "ability_status",
  "knowledge_mastery",
  "execution_habits",
  "time_constraints",
  "risk_preference",
  "memory_notes",
];

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

let currentUser = "";
let pendingPlanMessageId = null;
let selectedAiFileId = null;
let selectedDatabaseFileId = null;
let selectedPlanRow = null;
let selectedDatabaseDate = "";

function todayText() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function monthStartText() {
  return `${todayText().slice(0, 8)}01`;
}

function nextDateText(value) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + 1);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function showToast(text) {
  toast.textContent = text;
  toast.hidden = false;
  window.setTimeout(() => {
    toast.hidden = true;
  }, 1200);
}

function showMessage(text, type = "info") {
  message.textContent = text;
  message.hidden = false;
  message.classList.toggle("error", type === "error");
  window.setTimeout(() => {
    message.hidden = true;
  }, 2600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function planStatusLabel(status) {
  if (status === "done") return "已完成";
  if (status === "failed") return "未完成";
  return "待执行";
}

function addPlanItem(item = {}) {
  const row = document.createElement("div");
  row.className = `plan-item ${item.status || "pending"}`;
  if (item.id) row.dataset.id = item.id;
  row.innerHTML = `
    <span class="plan-index"></span>
    <textarea placeholder="写下一条具体计划">${escapeHtml(item.content || "")}</textarea>
    <div class="plan-state">
      <button class="soft-button small" data-status="done" type="button">已完成</button>
      <button class="soft-button small" data-status="failed" type="button">未完成</button>
    </div>
  `;
  row.addEventListener("click", () => {
    if (selectedPlanRow) {
      selectedPlanRow.classList.remove("selected");
    }
    selectedPlanRow = row;
    row.classList.add("selected");
  });
  row.querySelectorAll("[data-status]").forEach((button) => {
    button.addEventListener("click", () => {
      row.classList.remove("pending", "done", "failed");
      row.classList.add(button.dataset.status);
      syncTasksText();
      if (row.dataset.id) {
        updatePlanStatus(row.dataset.id, button.dataset.status).catch((error) => showToast(error.message));
      }
    });
  });
  row.querySelector("textarea").addEventListener("input", syncTasksText);
  planItems.appendChild(row);
  updatePlanIndexes();
  syncTasksText();
}

function updatePlanIndexes() {
  planItems.querySelectorAll(".plan-item").forEach((row, index) => {
    row.querySelector(".plan-index").textContent = `${index + 1}`;
  });
}

function deleteSelectedPlanItem() {
  if (!selectedPlanRow) {
    showToast("请先选中一条计划");
    return;
  }
  selectedPlanRow.remove();
  selectedPlanRow = null;
  if (!planItems.querySelector(".plan-item")) {
    addPlanItem();
  }
  updatePlanIndexes();
  syncTasksText();
  savePlanItems().catch((error) => showToast(error.message));
}

function readPlanItems() {
  return Array.from(planItems.querySelectorAll(".plan-item"))
    .map((row, index) => ({
      id: row.dataset.id ? Number(row.dataset.id) : null,
      content: row.querySelector("textarea").value.trim(),
      status: row.classList.contains("done") ? "done" : row.classList.contains("failed") ? "failed" : "pending",
      sort_order: index,
    }))
    .filter((item) => item.content);
}

function syncTasksText() {
  const lines = readPlanItems().map((item, index) => `${index + 1}. [${planStatusLabel(item.status)}] ${item.content}`);
  document.querySelector("#tasks").value = lines.join("\n");
}

function renderPlanItems(items) {
  planItems.innerHTML = "";
  selectedPlanRow = null;
  if (!items.length) {
    addPlanItem();
    return;
  }
  items.forEach(addPlanItem);
}

async function loadPlanItems() {
  const params = withUserParams(new URLSearchParams());
  params.set("date", document.querySelector("#date").value);
  const response = await fetch(`/api/plans?${params}`);
  if (!response.ok) {
    throw new Error("加载计划失败");
  }
  const items = await response.json();
  if (!items.length && document.querySelector("#tasks").value.trim()) {
    renderPlanItems(
      document.querySelector("#tasks").value
        .split("\n")
        .map((line, index) => ({
          content: line.replace(/^\d+[\.\、\)]\s*/, "").replace(/^\[(已完成|未完成|待执行)\]\s*/, ""),
          status: line.includes("[已完成]") ? "done" : line.includes("[未完成]") ? "failed" : "pending",
          sort_order: index,
        }))
        .filter((item) => item.content.trim())
    );
    return;
  }
  renderPlanItems(items);
}

async function savePlanItems() {
  const response = await fetch("/api/plans/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: requireUser(),
      date: document.querySelector("#date").value,
      items: readPlanItems(),
    }),
  });
  if (!response.ok) {
    throw new Error("保存计划失败");
  }
  renderPlanItems(await response.json());
}

async function updatePlanStatus(id, status) {
  const response = await fetch(`/api/plans/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: requireUser(), status }),
  });
  if (!response.ok) {
    throw new Error("更新计划状态失败");
  }
}

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function uploadUserFile(file, targetDate = "") {
  const formData = new FormData();
  formData.append("file", file);
  const params = withUserParams(new URLSearchParams());
  if (targetDate) {
    params.set("date", targetDate);
  }
  const response = await fetch(`/api/files/upload?${params}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error("上传文件失败");
  }
  return response.json();
}

function renderFileList(container, files) {
  if (!files.length) {
    container.innerHTML = `<div class="empty">暂无上传文件</div>`;
    return;
  }
  const groups = files.reduce((result, file) => {
    const key = file.upload_date || "未分类";
    result[key] = result[key] || [];
    result[key].push(file);
    return result;
  }, {});
  container.innerHTML = Object.entries(groups)
    .map(([date, rows]) => `
      <div class="file-date-group ${date === selectedDatabaseDate ? "selected" : ""}" data-file-date="${escapeHtml(date)}">
        <button class="file-date" data-file-date-pick="${escapeHtml(date)}" type="button">${escapeHtml(date)}</button>
        ${rows
          .map((file) => `
            <div class="file-item ${file.id === selectedDatabaseFileId ? "selected" : ""}" data-file-id="${file.id}">
              <button class="file-name" data-file-view="${file.id}" type="button">${escapeHtml(file.original_name)}</button>
              <div class="file-actions">
                <button class="soft-button small" data-file-view="${file.id}" type="button">查看</button>
                <button class="soft-button small" data-file-delete="${file.id}" type="button">删除</button>
              </div>
            </div>
          `)
          .join("")}
      </div>
    `)
    .join("");
  container.querySelectorAll("[data-file-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const fileId = Number(button.dataset.fileId);
      if (selectedDatabaseFileId === fileId) {
        selectedDatabaseFileId = null;
        button.classList.remove("selected");
        return;
      }
      selectedDatabaseFileId = fileId;
      document.querySelectorAll(".file-item").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
    });
  });
  container.querySelectorAll("[data-file-date-pick]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const date = button.dataset.fileDatePick;
      selectedDatabaseDate = selectedDatabaseDate === date ? "" : date;
      if (selectedDatabaseDate) {
        databaseDate.value = selectedDatabaseDate;
      }
      renderFileList(container, files);
    });
  });
  container.querySelectorAll("[data-file-view]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      selectedDatabaseFileId = Number(button.dataset.fileView);
      viewFile(selectedDatabaseFileId);
    });
  });
  container.querySelectorAll("[data-file-delete]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteFile(Number(button.dataset.fileDelete)).catch((error) => showToast(error.message));
    });
  });
}

async function loadDatabaseFiles() {
  const todayParams = withUserParams(new URLSearchParams());
  todayParams.set("scope", "today");
  const historyParams = withUserParams(new URLSearchParams());
  historyParams.set("scope", "history");
  if (databaseDate.value) {
    historyParams.set("date", databaseDate.value);
  }
  if (databaseKeyword.value.trim()) {
    historyParams.set("keyword", databaseKeyword.value.trim());
  }
  const [todayResponse, historyResponse] = await Promise.all([
    fetch(`/api/files?${todayParams}`),
    fetch(`/api/files?${historyParams}`),
  ]);
  if (!todayResponse.ok || !historyResponse.ok) {
    throw new Error("加载文件数据库失败");
  }
  renderFileList(todayFiles, await todayResponse.json());
  renderFileList(historyFiles, await historyResponse.json());
}

function downloadSelectedFile() {
  if (!selectedDatabaseFileId) {
    showToast("请先选择文件");
    return;
  }
  const params = withUserParams(new URLSearchParams());
  window.location.href = `/api/files/${selectedDatabaseFileId}/download?${params}`;
}

function openExportDrawer() {
  exportStartDate.value = monthStartText();
  exportEndDate.value = todayText();
  document.querySelector("#exportDrawer").hidden = false;
}

function exportWord() {
  const start = exportStartDate.value;
  const end = exportEndDate.value;
  if (!start || !end) {
    showToast("请选择起始和终止日期");
    return;
  }
  if (start > end) {
    showToast("起始日期不能晚于终止日期");
    return;
  }
  const params = withUserParams(new URLSearchParams());
  params.set("start_date", start);
  params.set("end_date", end);
  window.location.href = `/api/export/word?${params}`;
}

function viewSelectedFile() {
  if (!selectedDatabaseFileId) {
    showToast("请先选择文件");
    return;
  }
  viewFile(selectedDatabaseFileId);
}

function viewFile(fileId) {
  const params = withUserParams(new URLSearchParams());
  window.open(`/api/files/${fileId}/view?${params}`, "_blank", "noopener");
}

async function deleteFile(fileId) {
  const params = withUserParams(new URLSearchParams());
  const response = await fetch(`/api/files/${fileId}?${params}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("删除文件失败");
  }
  if (selectedDatabaseFileId === fileId) {
    selectedDatabaseFileId = null;
  }
  await loadDatabaseFiles();
  showToast("删除成功");
}

function extractNote(content) {
  if (content.startsWith("心情：") && content.includes("\n\n")) {
    return content.split("\n\n").slice(1).join("\n\n");
  }
  return content;
}

function extractMood(content) {
  if (content.startsWith("心情：") && content.includes("\n\n")) {
    return content.split("\n\n", 1)[0].replace("心情：", "").trim();
  }
  return "";
}

function requireUser() {
  if (!currentUser) {
    throw new Error("请先登录");
  }
  return currentUser;
}

function withUserParams(params = new URLSearchParams()) {
  params.set("username", requireUser());
  return params;
}

function readForm() {
  const payload = { username: requireUser() };
  for (const field of fields) {
    const element = document.querySelector(`#${field}`);
    payload[field] = element.value.trim();
  }
  payload.content = `心情：${document.querySelector("#mood").value}\n\n${payload.content}`;
  payload.duration_minutes = Number(payload.duration_minutes || 0);
  return payload;
}

function fillToday() {
  document.querySelector("#date").value = todayText();
}

function line(label, value) {
  if (!value) {
    return "";
  }
  return `<p><span class="log-label">${label}：</span>${escapeHtml(value)}</p>`;
}

function renderLogs(logs) {
  logs.sort((a, b) => String(b.date).localeCompare(String(a.date)) || (b.id || 0) - (a.id || 0));
  if (logs.length === 0) {
    logList.innerHTML = `<div class="empty">没有搜索到相关记录</div>`;
    return;
  }

  logList.innerHTML = logs
    .map((log) => `
      <article class="log-item">
        <div class="log-item-head">
          <div class="log-date">${escapeHtml(log.date)}</div>
        </div>
        <div class="log-body">
          ${line("今日计划", log.tasks)}
          ${line("今日笔记", extractNote(log.content))}
          ${line("待解决事项", log.problems)}
        </div>
      </article>
    `)
    .join("");
}

function fillFormFromLog(log) {
  document.querySelector("#content").value = extractNote(log.content || "");
  document.querySelector("#tasks").value = log.tasks || "";
  document.querySelector("#problems").value = log.problems || "";
  document.querySelector("#tomorrow_plan").value = log.tomorrow_plan || "";
  document.querySelector("#category").value = log.category || "学习日志";
  document.querySelector("#status").value = log.status || "进行中";
  document.querySelector("#duration_minutes").value = log.duration_minutes || 0;
  document.querySelector("#remark").value = log.remark || "";

  const mood = extractMood(log.content || "");
  if (mood) {
    document.querySelector("#mood").value = mood;
  }
}

function clearFormForDate() {
  document.querySelector("#content").value = "";
  document.querySelector("#tasks").value = "";
  document.querySelector("#problems").value = "";
  document.querySelector("#tomorrow_plan").value = "";
  document.querySelector("#category").value = "学习日志";
  document.querySelector("#status").value = "进行中";
  document.querySelector("#duration_minutes").value = 0;
  document.querySelector("#remark").value = "";
}

function closeDrawers() {
  document.querySelector("#tomorrowDrawer").hidden = true;
  document.querySelector("#historyDrawer").hidden = true;
  document.querySelector("#aiDrawer").hidden = true;
  document.querySelector("#profileDrawer").hidden = true;
  document.querySelector("#databaseDrawer").hidden = true;
  document.querySelector("#exportDrawer").hidden = true;
}

function readProfileForm() {
  const payload = { username: requireUser() };
  for (const field of profileFields) {
    payload[field] = document.querySelector(`#${field}`).value.trim();
  }
  return payload;
}

function fillProfileForm(profile) {
  for (const field of profileFields) {
    document.querySelector(`#${field}`).value = profile?.[field] || "";
  }
}

async function loadProfile() {
  const params = withUserParams(new URLSearchParams());
  const response = await fetch(`/api/profile?${params}`);
  if (!response.ok) {
    throw new Error("加载用户画像失败");
  }
  fillProfileForm(await response.json());
}

async function saveProfile() {
  const response = await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(readProfileForm()),
  });
  if (!response.ok) {
    throw new Error("保存用户画像失败");
  }
  fillProfileForm(await response.json());
  showToast("用户画像已保存！");
}

async function fetchLogs(params = new URLSearchParams()) {
  const urlParams = withUserParams(params);
  const url = `/api/logs?${urlParams}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("加载历史记录失败");
  }
  return response.json();
}

async function loadSelectedDate() {
  const params = new URLSearchParams();
  params.set("date", document.querySelector("#date").value);
  const logs = await fetchLogs(params);
  if (logs.length > 0) {
    fillFormFromLog(logs[0]);
  } else {
    clearFormForDate();
  }
  await loadPlanItems();
}

async function loadLogs() {
  const params = new URLSearchParams();
  const keyword = document.querySelector("#filterKeyword").value.trim();

  if (keyword) {
    params.set("keyword", keyword);
  }

  renderLogs(await fetchLogs(params));
}

async function postLog(payload) {
  const response = await fetch("/api/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("保存失败");
  }
  return response.json();
}

async function saveLog(event) {
  event.preventDefault();
  syncTasksText();
  const payload = readForm();
  if (!document.querySelector("#content").value.trim()) {
    showToast("今日笔记不能为空");
    return;
  }

  await postLog(payload);
  await savePlanItems();
  await loadSelectedDate();
  if (!document.querySelector("#historyDrawer").hidden) {
    await loadLogs();
  }
  showToast("保存成功！");
}

async function saveTomorrowPlan() {
  const tomorrowText = document.querySelector("#tomorrow_plan").value.trim();
  if (!tomorrowText) {
    showToast("明日计划为空");
    return;
  }

  const currentPayload = readForm();
  currentPayload.tomorrow_plan = tomorrowText;
  await postLog(currentPayload);

  const nextDate = nextDateText(currentPayload.date);
  const params = new URLSearchParams();
  params.set("date", nextDate);
  const nextLogs = await fetchLogs(params);
  const old = nextLogs[0];
  await postLog({
    username: requireUser(),
    date: nextDate,
    content: old?.content || "心情：开心 · 小心心\n\n",
    tasks: tomorrowText,
    problems: old?.problems || "",
    tomorrow_plan: old?.tomorrow_plan || "",
    category: old?.category || "学习日志",
    status: old?.status || "进行中",
    duration_minutes: old?.duration_minutes || 0,
    remark: old?.remark || "",
  });

  document.querySelector("#tomorrowDrawer").hidden = true;
  showToast("明日计划已保存！");
}

function renderAiMessages(messages) {
  if (messages.length === 0) {
    aiMessages.innerHTML = `<div class="empty">今天也要元气满满哦！</div>`;
    return;
  }
  aiMessages.innerHTML = messages
    .map((item) => `<div class="ai-bubble ${item.role === "user" ? "user" : "assistant"}">${escapeHtml(item.content)}</div>`)
    .join("");
  aiMessages.scrollTop = aiMessages.scrollHeight;
}

async function loadAiMessages() {
  pendingPlanMessageId = null;
  applyPlanButton.hidden = true;
  aiMessages.innerHTML = `<div class="empty">正在读取 ${escapeHtml(requireUser())} 的会话记忆...</div>`;
  const params = withUserParams(new URLSearchParams());
  const response = await fetch(`/api/ai/messages?${params}`);
  if (!response.ok) {
    throw new Error("加载 AI 会话失败");
  }
  const messages = await response.json();
  const pending = [...messages].reverse().find((item) => item.role === "assistant" && item.plan_text && !item.applied);
  pendingPlanMessageId = pending?.id || null;
  applyPlanButton.hidden = !pendingPlanMessageId;
  renderAiMessages(messages);
}

async function sendAiMessage() {
  const input = document.querySelector("#aiInput");
  const query = input.value.trim();
  if (!query) {
    showToast("先输入想问 AI 的内容");
    return;
  }

  input.value = "";
  renderAiMessages([
    ...Array.from(aiMessages.querySelectorAll(".ai-bubble")).map((node) => ({
      role: node.classList.contains("user") ? "user" : "assistant",
      content: node.textContent,
    })),
    { role: "user", content: query },
    { role: "assistant", content: "别着急，我在努力思考哦~" },
  ]);

  const response = await fetch("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: requireUser(),
      message: query,
      selected_date: document.querySelector("#date").value,
      file_ids: selectedAiFileId ? [selectedAiFileId] : [],
    }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "AI 调用失败");
  }
  selectedAiFileId = null;
  aiFileHint.hidden = true;
  await loadAiMessages();
  await loadPlanItems();
}

async function applyAiPlan() {
  if (!pendingPlanMessageId) {
    showToast("没有可应用的计划");
    return;
  }
  const response = await fetch("/api/ai/apply-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: requireUser(), message_id: pendingPlanMessageId }),
  });
  if (!response.ok) {
    throw new Error("应用计划失败");
  }
  const result = await response.json();
  document.querySelector("#date").value = result.date;
  await loadSelectedDate();
  await loadPlanItems();
  await loadAiMessages();
  showToast("计划已应用！");
}

async function login(username, password) {
  const safeUsername = username.trim();
  if (!safeUsername) {
    showToast("请输入用户名");
    return;
  }
  if (!password) {
    showToast("请输入密码");
    return;
  }

  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: safeUsername, password }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    if (response.status === 405) {
      showToast("登录接口未生效，请重启后端服务");
      return;
    }
    showToast(detail.detail || "登录失败");
    return;
  }
  const result = await response.json();
  currentUser = result.username;
  localStorage.setItem("learningAgentLastUser", currentUser);
  userChip.textContent = currentUser;
  loginPanel.hidden = true;
  diaryPanel.hidden = false;
  pendingPlanMessageId = null;
  applyPlanButton.hidden = true;
  aiMessages.innerHTML = "";
  logList.innerHTML = "";
  document.querySelector("#filterKeyword").value = "";
  document.querySelector("#aiInput").value = "";
  loginPassword.value = "";
  fillToday();
  closeDrawers();
  loadProfile().catch((error) => showToast(error.message));
  loadSelectedDate().catch((error) => showToast(error.message));
  showToast(result.created ? "账号已创建并登录" : "登录成功");
}

function logout() {
  currentUser = "";
  pendingPlanMessageId = null;
  selectedAiFileId = null;
  selectedDatabaseFileId = null;
  closeDrawers();
  clearFormForDate();
  renderPlanItems([]);
  logList.innerHTML = "";
  aiMessages.innerHTML = "";
  fillProfileForm({});
  diaryPanel.hidden = true;
  loginPanel.hidden = false;
  loginPassword.value = "";
  loginPassword.focus();
}

loginButton.addEventListener("click", () => {
  login(loginName.value, loginPassword.value).catch((error) => showToast(error.message));
});

loginName.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    login(loginName.value, loginPassword.value).catch((error) => showToast(error.message));
  }
});

loginPassword.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    login(loginName.value, loginPassword.value).catch((error) => showToast(error.message));
  }
});

logoutButton.addEventListener("click", logout);

document.querySelector("#tomorrowToggle").addEventListener("click", () => {
  document.querySelector("#tomorrowDrawer").hidden = false;
});

document.querySelector("#tomorrowSave").addEventListener("click", () => {
  saveTomorrowPlan().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#historyToggle").addEventListener("click", () => {
  document.querySelector("#historyDrawer").hidden = false;
  loadLogs().catch((error) => showMessage(error.message, "error"));
});

exportToggle.addEventListener("click", openExportDrawer);

exportConfirm.addEventListener("click", exportWord);

profileToggle.addEventListener("click", () => {
  document.querySelector("#profileDrawer").hidden = false;
  loadProfile().catch((error) => showToast(error.message));
});

profileSave.addEventListener("click", () => {
  saveProfile().catch((error) => showToast(error.message));
});

databaseToggle.addEventListener("click", () => {
  document.querySelector("#databaseDrawer").hidden = false;
  selectedDatabaseFileId = null;
  loadDatabaseFiles().catch((error) => showToast(error.message));
});

databaseUpload.addEventListener("click", () => {
  databaseFileInput.click();
});

databaseFileInput.addEventListener("change", () => {
  const file = databaseFileInput.files?.[0];
  if (!file) return;
  uploadUserFile(file, selectedDatabaseDate || databaseDate.value)
    .then(() => loadDatabaseFiles())
    .then(() => showToast("上传成功"))
    .catch((error) => showToast(error.message))
    .finally(() => {
      databaseFileInput.value = "";
    });
});

databaseDownload.addEventListener("click", downloadSelectedFile);

databaseDateSearch.addEventListener("click", () => {
  selectedDatabaseDate = databaseDate.value;
  loadDatabaseFiles().catch((error) => showToast(error.message));
});

databaseKeywordSearch.addEventListener("click", () => {
  loadDatabaseFiles().catch((error) => showToast(error.message));
});

databaseClearSearch.addEventListener("click", () => {
  databaseDate.value = "";
  databaseKeyword.value = "";
  selectedDatabaseDate = "";
  selectedDatabaseFileId = null;
  loadDatabaseFiles().catch((error) => showToast(error.message));
});

newPlanButton.addEventListener("click", () => {
  addPlanItem();
});

deletePlanButton.addEventListener("click", deleteSelectedPlanItem);

aiUpload.addEventListener("click", () => {
  aiFileInput.click();
});

aiFileInput.addEventListener("change", () => {
  const file = aiFileInput.files?.[0];
  if (!file) return;
  uploadUserFile(file)
    .then((uploaded) => {
      selectedAiFileId = uploaded.id;
      aiFileHint.textContent = `已选择文件：${uploaded.original_name}`;
      aiFileHint.hidden = false;
      showToast("上传成功");
    })
    .catch((error) => showToast(error.message))
    .finally(() => {
      aiFileInput.value = "";
    });
});

document.querySelector("#aiToggle").addEventListener("click", () => {
  document.querySelector("#aiDrawer").hidden = false;
  pendingPlanMessageId = null;
  applyPlanButton.hidden = true;
  aiMessages.innerHTML = "";
  loadAiMessages().catch((error) => showMessage(error.message, "error"));
});

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector(`#${button.dataset.close}`).hidden = true;
  });
});

document.querySelector("#searchButton").addEventListener("click", () => {
  loadLogs().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#refreshButton").addEventListener("click", () => {
  document.querySelector("#filterKeyword").value = "";
  loadLogs().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#filterKeyword").addEventListener("input", () => {
  loadLogs().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#date").addEventListener("change", () => {
  loadSelectedDate().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#aiSend").addEventListener("click", () => {
  sendAiMessage().catch((error) => showMessage(error.message, "error"));
});

document.querySelector("#aiInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    sendAiMessage().catch((error) => showMessage(error.message, "error"));
  }
});

applyPlanButton.addEventListener("click", () => {
  applyAiPlan().catch((error) => showMessage(error.message, "error"));
});

form.addEventListener("submit", (event) => {
  saveLog(event).catch((error) => showToast(error.message));
});

const lastUser = localStorage.getItem("learningAgentLastUser");
fillToday();
if (lastUser) {
  loginName.value = lastUser;
}
loginPanel.hidden = false;
diaryPanel.hidden = true;
(lastUser ? loginPassword : loginName).focus();
