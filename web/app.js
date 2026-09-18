const el = (id) => document.getElementById(id);

const ui = {
  topicList: el("topic-list"),
  messages: el("messages"),
  input: el("input"),
  send: el("send"),
  composer: el("composer"),
  newSession: el("new-session"),
  topicTitle: el("topic-title"),
  topicSub: el("topic-sub"),
  pill: el("session-pill"),
  statusText: el("status-text"),
  statusDot: el("status-dot"),
  turnCount: el("turn-count"),
  progressFill: el("progress-fill"),
};

const STEPS = ["step-start", "step-explain", "step-deep", "step-refine", "step-done"];
const TARGET_TURNS = 5;

const state = {
  topics: [],
  topicId: null,
  sessionId: null,
  status: null,
  busy: false,
  reactionIndex: 0,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = `Lỗi ${response.status}`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      /* giữ nguyên thông báo mặc định */
    }
    throw new Error(detail);
  }
  return response.json();
}

function renderTopics() {
  ui.topicList.innerHTML = "";
  for (const topic of state.topics) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.textContent = topic.title;
    button.className = topic.topic_id === state.topicId ? "is-active" : "";
    button.addEventListener("click", () => selectTopic(topic.topic_id));
    li.append(button);
    ui.topicList.append(li);
  }
}

/** Ảnh icon riêng cho chủ đề; thiếu file thì giữ icon mặc định. */
function topicIconFile(topicId) {
  if (topicId.includes("kafka")) return "kafka.png";
  if (topicId.includes("database") || topicId.includes("sql")) return "database.png";
  if (topicId.includes("docker")) return "docker.png";
  if (topicId.includes("kubernetes")) return "kubernates.png";
  return null;
}

function selectTopic(topicId) {
  const topic = state.topics.find((item) => item.topic_id === topicId);
  if (!topic) return;
  state.topicId = topicId;
  ui.topicTitle.textContent = topic.title;
  ui.topicSub.textContent = "Bạn là người dạy — hãy giải thích theo cách hiểu của bạn nhé!";
  ui.newSession.disabled = false;

  const icon = document.querySelector(".topic-icon");
  if (icon) {
    if (!icon.dataset.fallback) icon.dataset.fallback = icon.innerHTML;
    icon.innerHTML = icon.dataset.fallback;
    const file = topicIconFile(topicId);
    if (file) withAsset(icon, file, topic.title);
  }

  renderTopics();
}

const AI_AVATAR = `<svg viewBox="0 0 46 46">
  <rect width="46" height="46" rx="15" fill="#dbe8ff"/>
  <rect x="9" y="12" width="28" height="23" rx="9" fill="#fff" stroke="#9fc0f5" stroke-width="2"/>
  <circle cx="18" cy="23" r="3.6" fill="#2f6df0"/><circle cx="28" cy="23" r="3.6" fill="#6f52ea"/>
  <circle cx="19.1" cy="21.6" r="1.3" fill="#fff"/><circle cx="29.1" cy="21.6" r="1.3" fill="#fff"/>
  <path d="M20 29.5q3 2.6 6 0" stroke="#5b7cc0" stroke-width="1.8" stroke-linecap="round" fill="none"/>
  <path d="M23 12V8" stroke="#9fc0f5" stroke-width="2" stroke-linecap="round"/>
  <circle cx="23" cy="6.6" r="2.1" fill="#7a5cf0"/>
  <rect x="4" y="19" width="5" height="10" rx="2.5" fill="#bcd3f8"/>
  <rect x="37" y="19" width="5" height="10" rx="2.5" fill="#bcd3f8"/>
</svg>`;

const ME_AVATAR = `<svg viewBox="0 0 46 46">
  <rect width="46" height="46" rx="15" fill="#d9ecdd"/>
  <circle cx="23" cy="19" r="8" fill="#f6c8a0"/>
  <path d="M14.5 16q8.5-6.8 17 0Q29.8 8.6 23 8.6T14.5 16Z" fill="#4a3728"/>
  <path d="M7 42q3.4-10 16-10t16 10Z" fill="#6ea8f0"/>
</svg>`;

const AI_REACTIONS = ["Mình đang học nè! 📚", "Câu hỏi hay quá! 🤔", "Bạn giải thích rất rõ ràng! ✨"];

/** Dùng ảnh trong /assets nếu có, nếu thiếu thì giữ SVG dựng sẵn. */
function withAsset(container, file, alt) {
  const image = new Image();
  image.src = `/assets/${file}`;
  image.alt = alt;
  image.addEventListener("load", () => {
    container.innerHTML = "";
    container.append(image);
  });
}

function timeNow() {
  return new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function addMessage(role, content, options = {}) {
  const isAi = role === "ai_student";
  const row = document.createElement("div");
  row.className = `row ${isAi ? "ai" : "me"}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.innerHTML = isAi ? AI_AVATAR : ME_AVATAR;
  withAsset(avatar, isAi ? "logo_robot.png" : "avatar_user.png", isAi ? "AI học sinh" : "Bạn");

  const body = document.createElement("div");

  const meta = document.createElement("div");
  meta.className = "meta";
  const who = document.createElement("span");
  who.textContent = isAi ? "AI Học sinh" : "Bạn";
  const time = document.createElement("span");
  time.className = "time";
  time.textContent = options.time || timeNow();
  meta.append(who, time);

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  body.append(meta, bubble);

  if (isAi && !options.plain) {
    const reaction = document.createElement("div");
    reaction.className = "reaction";
    reaction.textContent = AI_REACTIONS[state.reactionIndex % AI_REACTIONS.length];
    state.reactionIndex += 1;
    body.append(reaction);
  }

  row.append(avatar, body);
  ui.messages.append(row);
  scrollToBottom();
  return row;
}

function addBanner(text, kind) {
  const banner = document.createElement("div");
  banner.className = `banner ${kind}`;
  banner.textContent = text;
  ui.messages.append(banner);
  scrollToBottom();
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "row ai";
  row.dataset.typing = "true";
  row.innerHTML =
    `<div class="avatar">${AI_AVATAR}</div><div><div class="meta"><span>AI Học sinh</span></div>` +
    '<div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div></div>';
  ui.messages.append(row);
  scrollToBottom();
  return row;
}

function scrollToBottom() {
  ui.messages.scrollTop = ui.messages.scrollHeight;
}

function renderProgress(turnCount, status) {
  ui.turnCount.textContent = String(turnCount);
  const ratio = Math.min(turnCount / TARGET_TURNS, 1);
  ui.progressFill.style.width = `${status === "completed" ? 100 : ratio * 100}%`;

  // Steps mirror observable conversation progress only. Concept coverage is
  // deliberately hidden by the API so the learner cannot read the answer off
  // the UI.
  const reached = status === "completed" ? STEPS.length : Math.min(turnCount + 1, STEPS.length);
  STEPS.forEach((id, index) => {
    const node = el(id);
    node.classList.toggle("is-done", index < reached - (status === "completed" ? 0 : 1));
    node.classList.toggle("is-current", status !== "completed" && index === reached - 1);
  });
}

function setBusy(busy) {
  state.busy = busy;
  const active = state.status === "active";
  ui.input.disabled = busy || !active;
  ui.send.disabled = busy || !active;
  ui.newSession.disabled = busy || !state.topicId;
}

function applySession(session) {
  state.sessionId = session.session_id;
  state.status = session.status;

  if (session.status === "active") {
    ui.pill.className = "pill";
    ui.pill.innerHTML = "<i></i>Phiên đang diễn ra";
    ui.statusText.textContent = "Trạng thái: Đang học";
    ui.statusDot.className = "dot";
  } else {
    ui.pill.className = "pill is-idle";
    ui.pill.innerHTML = `<i></i>${session.status === "completed" ? "Đã hoàn thành" : "Đã dừng"}`;
    ui.statusText.textContent = "Trạng thái: Sẵn sàng";
    ui.statusDot.className = "dot is-idle";
  }

  renderProgress(session.turn_count, session.status);
  setBusy(false);
}

async function startSession() {
  if (!state.topicId) return;
  setBusy(true);
  ui.messages.innerHTML = "";
  state.reactionIndex = 0;
  try {
    const session = await api(`/topics/${state.topicId}/sessions`, { method: "POST" });
    for (const message of session.messages) {
      addMessage(message.role, message.content, { plain: true });
    }
    applySession(session);
    ui.input.focus();
  } catch (error) {
    addBanner(`Không bắt đầu được phiên: ${error.message}`, "error");
    setBusy(false);
  }
}

async function sendMessage(text) {
  addMessage("human_teacher", text);
  setBusy(true);
  const typing = showTyping();

  try {
    const session = await api(`/sessions/${state.sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content: text }),
    });
    typing.remove();

    const latest = session.messages[session.messages.length - 1];
    if (latest && latest.role === "ai_student") {
      addMessage(latest.role, latest.content);
    }
    applySession(session);

    if (session.status === "completed") {
      addBanner("🎉 AI đã hiểu chủ đề này. Bạn dạy tốt lắm!", "done");
    }
  } catch (error) {
    typing.remove();
    addBanner(error.message, "error");
    setBusy(false);
  }
}

ui.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = ui.input.value.trim();
  if (!text || state.busy || state.status !== "active") return;
  ui.input.value = "";
  ui.input.style.height = "auto";
  sendMessage(text);
});

ui.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    ui.composer.requestSubmit();
  }
});

ui.input.addEventListener("input", () => {
  ui.input.style.height = "auto";
  ui.input.style.height = `${Math.min(ui.input.scrollHeight, 140)}px`;
});

ui.newSession.addEventListener("click", startSession);

function applyStaticAssets() {
  const slots = [
    [".brand-mark", "logo_robot.png", "TeachBack"],
    [".user-avatar", "avatar_user.png", "Ảnh đại diện"],
    [".mascot-art-slot", "robot_teach.png", "Robot đang đọc sách"],
    [".empty-art", "empty_chat.png", "Bắt đầu cuộc trò chuyện"],
  ];
  for (const [selector, file, alt] of slots) {
    const node = document.querySelector(selector);
    if (node) withAsset(node, file, alt);
  }
}

(async function init() {
  applyStaticAssets();
  ui.newSession.disabled = true;
  try {
    state.topics = await api("/topics");
    renderTopics();
    if (state.topics.length) selectTopic(state.topics[0].topic_id);
  } catch (error) {
    ui.topicList.innerHTML = `<li class="topic-skeleton">Không tải được chủ đề: ${error.message}</li>`;
  }
})();
