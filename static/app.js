let currentDocId = null;
let currentUserRole = "user";
let currentUsername = "";
let appMode = "General Chat";
let isBusy = false;
let activeChatController = null;
let knowledgeCollections = [];

const byId = (id) => document.getElementById(id);
const loginModal = byId("login-modal");
const loginForm = byId("login-form");
const loginError = byId("login-error");
const createUserModal = byId("create-user-modal");
const createUserForm = byId("create-user-form");
const createUserError = byId("create-user-error");
const cancelCreateUserBtn = byId("cancel-create-user-btn");
const logoutBtn = byId("logout-btn");
const userDisplay = byId("user-display");
const adminNavBtn = byId("admin-nav-btn");
const workspaceNavBtn = byId("workspace-nav-btn");
const aiWorkspaceView = byId("ai-workspace-view");
const adminDashboardView = byId("admin-dashboard-view");
const openCreateUserModalBtn = byId("open-create-user-modal-btn");
const userTableBody = byId("user-table-body");
const statTotalUsers = byId("stat-total-users");
const statActiveUsers = byId("stat-active-users");
const statAdminUsers = byId("stat-admin-users");
const adminTabUsersBtn = byId("admin-tab-users-btn");
const adminTabAccountBtn = byId("admin-tab-account-btn");
const adminUsersTab = byId("admin-users-tab");
const adminAccountTab = byId("admin-account-tab");
const accountCurrentUsername = byId("account-current-username");
const changeUsernameForm = byId("change-username-form");
const newUsernameInput = byId("new-username-input");
const usernameChangeMsg = byId("username-change-msg");
const changePasswordForm = byId("change-password-form");
const currentPasswordInput = byId("current-password-input");
const newPasswordInput = byId("new-password-input");
const confirmPasswordInput = byId("confirm-password-input");
const passwordChangeMsg = byId("password-change-msg");
const serverStatusDot = byId("server-status-dot");
const serverStatusText = byId("server-status-text");
const pdfFileInput = byId("pdf-file-input");
const clearBtn = byId("clear-btn");
const autoChatBtn = byId("auto-chat-btn");
const agentTaskBtn = byId("agent-task-btn");
const generalChatBtn = byId("general-chat-btn");
const knowledgeChatBtn = byId("knowledge-chat-btn");
const workspaceBody = document.querySelector(".workspace-body");
const workspaceSidebar = byId("workspace-sidebar");
const knowledgePanel = byId("knowledge-panel");
const knowledgeSidebarTab = byId("knowledge-sidebar-tab");
const sessionSidebarTab = byId("session-sidebar-tab");
const sessionSidebarPanel = byId("session-sidebar-panel");
const sidebarModeDetail = byId("sidebar-mode-detail");
const sidebarSessionMode = byId("sidebar-session-mode");
const sidebarSessionDocument = byId("sidebar-session-document");
const sidebarSessionPages = byId("sidebar-session-pages");
const sidebarSessionContext = byId("sidebar-session-context");
const sidebarSessionMethod = byId("sidebar-session-method");
const knowledgeFileInput = byId("knowledge-file-input");
const knowledgeCollectionSelect = byId("knowledge-collection-select");
const newCollectionInput = byId("new-collection-input");
const createCollectionBtn = byId("create-collection-btn");
const refreshKnowledgeBtn = byId("refresh-knowledge-btn");
const knowledgeStatus = byId("knowledge-status");
const knowledgeDocumentBody = byId("knowledge-document-body");
const currentDocBadge = byId("current-doc-badge");
const modeBadge = byId("mode-badge");
const metricPages = byId("metric-pages");
const metricText = byId("metric-text");
const metricContext = byId("metric-context");
const metricMethod = byId("metric-method");
const metricLlm = byId("metric-llm");
const metricHost = byId("metric-host");
const chatMessages = byId("chat-messages");
const chatInput = byId("chat-input");
const sendBtn = byId("send-btn");
const uploadProgress = byId("upload-progress");
const uploadStatusText = byId("upload-status-text");
const footerStatus = byId("footer-status");

async function responseError(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (_) {
    return fallback;
  }
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (response.status === 401 && url !== "/api/auth/login") {
    showLogin();
  }
  return response;
}

function showLogin() {
  loginModal.style.display = "flex";
  userDisplay.textContent = "Not logged in";
}

document.addEventListener("DOMContentLoaded", async () => {
  await checkHealth();
  await initSession();
  window.setInterval(checkHealth, 10000);
});

async function checkHealth() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Server unavailable");
    const data = await response.json();
    serverStatusDot.className = data.services.llm_ready ? "status-dot online" : "status-dot offline";
    serverStatusText.textContent = data.services.llm_ready ? "Local model ready" : "Model unavailable";

    if (loginModal.style.display === "none") {
      const metricsResponse = await apiFetch("/api/metrics");
      if (metricsResponse.ok) {
        const metrics = await metricsResponse.json();
        metricHost.textContent = `Host: CPU ${metrics.metrics.cpu_percent}% | RAM ${metrics.metrics.memory_percent}%`;
      }
    }
  } catch (_) {
    serverStatusDot.className = "status-dot offline";
    serverStatusText.textContent = "Server offline";
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.style.display = "none";
  const username = byId("username").value.trim();
  const password = byId("password").value;
  try {
    const response = await apiFetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw new Error(await responseError(response, "Authentication failed"));
    byId("password").value = "";
    loginModal.style.display = "none";
    await initSession();
  } catch (error) {
    loginError.textContent = error.message;
    loginError.style.display = "block";
  }
});

logoutBtn.addEventListener("click", async () => {
  if (activeChatController) activeChatController.abort();
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } finally {
    location.reload();
  }
});

async function initSession() {
  try {
    const profileResponse = await apiFetch("/api/auth/me");
    if (!profileResponse.ok) {
      showLogin();
      return;
    }
    const profile = await profileResponse.json();
    currentUserRole = profile.role;
    currentUsername = profile.username;
    userDisplay.textContent = `${profile.username} (${profile.role.toUpperCase()})`;
    loginModal.style.display = "none";
    adminNavBtn.classList.toggle("hidden", currentUserRole !== "admin");
    if (currentUserRole !== "admin") showWorkspaceView();

    const sessionResponse = await apiFetch("/api/session");
    if (sessionResponse.ok) updateSessionUI(await sessionResponse.json());
    await loadKnowledgeData();
  } catch (_) {
    showLogin();
  }
}

adminNavBtn.addEventListener("click", showAdminDashboard);
workspaceNavBtn.addEventListener("click", showWorkspaceView);

function showAdminDashboard() {
  aiWorkspaceView.classList.add("hidden");
  adminDashboardView.classList.remove("hidden");
  adminNavBtn.classList.add("hidden");
  workspaceNavBtn.classList.remove("hidden");
  footerStatus.textContent = "Admin panel active.";
  loadAdminUsers();
}

function showWorkspaceView() {
  adminDashboardView.classList.add("hidden");
  aiWorkspaceView.classList.remove("hidden");
  adminNavBtn.classList.toggle("hidden", currentUserRole !== "admin");
  workspaceNavBtn.classList.add("hidden");
  footerStatus.textContent = "Ready. Inference remains on the host machine.";
}

function setChatMode(mode) {
  appMode = mode;
  modeBadge.textContent = mode;
  const showSidebar = mode === "Knowledge Chat" || mode === "Auto";
  workspaceBody.classList.toggle("sidebar-open", showSidebar);
  workspaceSidebar.classList.toggle("hidden", !showSidebar);
  sidebarModeDetail.textContent = mode;
  sidebarSessionMode.textContent = mode;
  if (showSidebar) setSidebarTab("knowledge");
  if (mode === "General Chat" || mode === "Knowledge Chat") {
    currentDocId = null;
    currentDocBadge.textContent = "No document selected";
    resetMetrics();
  }
  chatInput.placeholder = mode === "Knowledge Chat"
    ? "Ask across your indexed documents... (Shift+Enter for newline, Enter to send)"
    : mode === "Auto"
    ? "Ask anything; Auto will choose the safest local capability... (Shift+Enter for newline, Enter to send)"
    : "Type your message here... (Shift+Enter for newline, Enter to send)";
}

function setSidebarTab(tabName) {
  const showKnowledge = tabName === "knowledge";
  knowledgePanel.classList.toggle("hidden", !showKnowledge);
  sessionSidebarPanel.classList.toggle("hidden", showKnowledge);
  knowledgeSidebarTab.classList.toggle("active", showKnowledge);
  sessionSidebarTab.classList.toggle("active", !showKnowledge);
  knowledgeSidebarTab.setAttribute("aria-selected", String(showKnowledge));
  sessionSidebarTab.setAttribute("aria-selected", String(!showKnowledge));
}

autoChatBtn.addEventListener("click", () => {
  setChatMode("Auto");
  loadKnowledgeData();
  chatInput.focus();
});
generalChatBtn.addEventListener("click", () => setChatMode("General Chat"));
agentTaskBtn.addEventListener("click", () => {
  setChatMode("Agent Task");
  workspaceSidebar.classList.add("hidden");
  workspaceBody.classList.remove("sidebar-open");
  chatInput.placeholder = "Describe a bounded local task... (Shift+Enter for newline, Enter to send)";
  chatInput.focus();
});
knowledgeChatBtn.addEventListener("click", async () => {
  setChatMode("Knowledge Chat");
  await loadKnowledgeData();
  chatInput.focus();
});
knowledgeSidebarTab.addEventListener("click", () => setSidebarTab("knowledge"));
sessionSidebarTab.addEventListener("click", () => setSidebarTab("session"));

function tableMessage(message, color = "#8b949e") {
  userTableBody.replaceChildren();
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 6;
  cell.style.textAlign = "center";
  cell.style.color = color;
  cell.textContent = message;
  row.appendChild(cell);
  userTableBody.appendChild(row);
}

function badge(text, className) {
  const item = document.createElement("span");
  item.className = className;
  item.textContent = text;
  return item;
}

async function loadAdminUsers() {
  tableMessage("Loading users...");
  try {
    const response = await apiFetch("/api/admin/users");
    if (!response.ok) throw new Error(await responseError(response, "Failed to fetch users"));
    const data = await response.json();
    statTotalUsers.textContent = data.summary.total_users;
    statActiveUsers.textContent = data.summary.active_users;
    statAdminUsers.textContent = data.summary.admin_users;
    userTableBody.replaceChildren();
    if (!data.users.length) {
      tableMessage("No users found.");
      return;
    }

    for (const user of data.users) {
      const row = document.createElement("tr");
      const values = [
        user.username,
        null,
        null,
        new Date(user.created_at * 1000).toLocaleString(),
        user.last_login ? new Date(user.last_login * 1000).toLocaleString() : "Never",
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        if (index === 0) {
          const strong = document.createElement("strong");
          strong.textContent = value;
          cell.appendChild(strong);
        } else if (index === 1) {
          cell.appendChild(badge(user.role.toUpperCase(), user.role === "admin" ? "badge-role-admin" : "badge-role-user"));
        } else if (index === 2) {
          cell.appendChild(badge(user.is_active ? "ACTIVE" : "INACTIVE", user.is_active ? "badge-status-active" : "badge-status-inactive"));
        } else {
          cell.textContent = value;
        }
        row.appendChild(cell);
      });

      const actionCell = document.createElement("td");
      if (user.username.toLowerCase() === currentUsername.toLowerCase()) {
        actionCell.textContent = "Current account";
        actionCell.className = "muted-cell";
      } else {
        const removeButton = document.createElement("button");
        removeButton.className = "btn btn-danger btn-sm";
        removeButton.textContent = "Remove";
        removeButton.addEventListener("click", () => removeUser(user.id, user.username));
        actionCell.appendChild(removeButton);
      }
      row.appendChild(actionCell);
      userTableBody.appendChild(row);
    }
  } catch (error) {
    tableMessage(`Error: ${error.message}`, "#f87171");
  }
}

openCreateUserModalBtn.addEventListener("click", () => {
  createUserForm.reset();
  createUserError.style.display = "none";
  createUserModal.classList.remove("hidden");
});
cancelCreateUserBtn.addEventListener("click", () => createUserModal.classList.add("hidden"));

createUserForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  createUserError.style.display = "none";
  try {
    const response = await apiFetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: byId("new-username").value.trim(),
        password: byId("new-password").value,
      }),
    });
    if (!response.ok) throw new Error(await responseError(response, "Failed to create user"));
    createUserModal.classList.add("hidden");
    await loadAdminUsers();
  } catch (error) {
    createUserError.textContent = error.message;
    createUserError.style.display = "block";
  }
});

async function removeUser(userId, username) {
  if (!confirm(`Remove user "${username}"?`)) return;
  const response = await apiFetch(`/api/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
  if (!response.ok) {
    alert(await responseError(response, "Failed to remove user"));
    return;
  }
  await loadAdminUsers();
}

adminTabUsersBtn.addEventListener("click", () => switchAdminTab("users"));
adminTabAccountBtn.addEventListener("click", () => switchAdminTab("account"));

function switchAdminTab(tabName) {
  const usersSelected = tabName === "users";
  adminTabUsersBtn.classList.toggle("active", usersSelected);
  adminTabAccountBtn.classList.toggle("active", !usersSelected);
  adminUsersTab.classList.toggle("hidden", !usersSelected);
  adminAccountTab.classList.toggle("hidden", usersSelected);
  if (usersSelected) loadAdminUsers();
  else loadAccountProfile();
}

async function loadAccountProfile() {
  const response = await apiFetch("/api/auth/me");
  if (response.ok) {
    const user = await response.json();
    accountCurrentUsername.textContent = user.username;
    newUsernameInput.value = "";
  }
}

function showFormMessage(element, message, kind) {
  element.textContent = message;
  element.className = `form-msg ${kind}`;
}

changeUsernameForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await apiFetch("/api/admin/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: newUsernameInput.value.trim() }),
  });
  if (!response.ok) {
    showFormMessage(usernameChangeMsg, await responseError(response, "Update failed"), "error");
    return;
  }
  const data = await response.json();
  currentUsername = data.user.username;
  accountCurrentUsername.textContent = currentUsername;
  userDisplay.textContent = `${currentUsername} (${data.user.role.toUpperCase()})`;
  newUsernameInput.value = "";
  showFormMessage(usernameChangeMsg, "Username updated.", "success");
});

changePasswordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    current_password: currentPasswordInput.value,
    new_password: newPasswordInput.value,
    confirm_password: confirmPasswordInput.value,
  };
  if (payload.new_password !== payload.confirm_password) {
    showFormMessage(passwordChangeMsg, "New password and confirmation do not match.", "error");
    return;
  }
  const response = await apiFetch("/api/admin/me/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    showFormMessage(passwordChangeMsg, await responseError(response, "Password change failed"), "error");
    return;
  }
  changePasswordForm.reset();
  showFormMessage(passwordChangeMsg, "Password changed.", "success");
});

function updateSessionUI(session) {
  setChatMode(session.mode);
  const active = session.uploaded_documents.find((doc) => doc.document_id === session.current_document_id);
  if (!active) {
    currentDocId = null;
    currentDocBadge.textContent = "No document selected";
    sidebarSessionDocument.textContent = "No document selected";
    resetMetrics();
    return;
  }
  currentDocId = active.document_id;
  currentDocBadge.textContent = `Document: ${active.filename}`;
  sidebarSessionDocument.textContent = active.filename;
  metricPages.textContent = `Pages: ${active.page_count}`;
  metricText.textContent = `Text: ${active.extracted_chars.toLocaleString()} chars`;
  metricMethod.textContent = `Method: ${active.method_summary}`;
  sidebarSessionPages.textContent = String(active.page_count);
  sidebarSessionMethod.textContent = active.method_summary || "-";
  if (session.current_document_context) {
    const context = session.current_document_context;
    metricContext.textContent = `Context: ${context.included_pages}/${context.total_text_pages} pages`;
    sidebarSessionContext.textContent = `${context.included_pages}/${context.total_text_pages} pages`;
  }
}

function resetMetrics() {
  metricPages.textContent = "Pages: -";
  metricText.textContent = "Text: -";
  metricContext.textContent = "Context: -";
  metricMethod.textContent = "Method: -";
  metricLlm.textContent = "LLM: -";
  sidebarSessionPages.textContent = "-";
  sidebarSessionContext.textContent = "-";
  sidebarSessionMethod.textContent = "-";
}

function appendMessage(role, content) {
  const message = document.createElement("div");
  message.className = `message ${role}`;
  const header = document.createElement("div");
  header.className = "msg-header";
  header.textContent = role === "user" ? "You" : role === "assistant" ? "Assistant" : "System";
  const body = document.createElement("div");
  body.className = "msg-content";
  body.textContent = content;
  message.append(header, body);
  chatMessages.appendChild(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return body;
}

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!isBusy) sendMessage();
  }
});

sendBtn.addEventListener("click", () => {
  if (activeChatController) activeChatController.abort();
  else sendMessage();
});

function handleStreamEvent(rawEvent, state) {
  const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
  if (!dataLine) return;
  const data = JSON.parse(dataLine.slice(5).trimStart());
  if (data.type === "sources") {
    state.sources = data.sources || [];
  } else if (data.type === "routing") {
    state.routing = data.routing || null;
    if (state.routing && !state.routingNoticeShown) {
      state.routingNoticeShown = true;
      appendMessage("system", `Capability: ${state.routing.display_name}. ${state.routing.reason}`);
    }
  } else if (data.type === "agent_started") {
    footerStatus.textContent = "Planning bounded local task...";
  } else if (data.type === "plan_created") {
    footerStatus.textContent = `Plan created: ${data.steps.length} registered step${data.steps.length === 1 ? "" : "s"}.`;
  } else if (data.type === "tool_started") {
    footerStatus.textContent = `Running ${data.tool_id}...`;
  } else if (data.type === "tool_completed") {
    footerStatus.textContent = `${data.tool_id} completed.`;
  } else if (data.type === "verification_completed") {
    footerStatus.textContent = data.passed ? "Verified tool result." : "Tool verification failed.";
  } else if (data.type === "approval_required") {
    appendMessage("system", "Approval Required. This task is paused before the requested tool runs.");
    footerStatus.textContent = "Approval required.";
  } else if (data.type === "final_result") {
    appendMessage("assistant", data.message || "Agent task finished.");
    for (const file of data.generated_files || []) {
      const line = document.createElement("div");
      line.className = "message system";
      const link = document.createElement("a");
      link.href = file.download_url;
      link.textContent = `Download ${file.filename}`;
      link.target = "_blank";
      line.appendChild(link);
      chatMessages.appendChild(line);
    }
    footerStatus.textContent = data.status === "COMPLETED" ? "Agent task completed." : `Agent task ${String(data.status).toLowerCase()}.`;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } else if (data.type === "chunk") {
    if (!state.body) state.body = appendMessage("assistant", "");
    state.text += data.content;
    state.body.textContent = state.text;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } else if (data.type === "done") {
    metricLlm.textContent = `LLM: ${data.latency_seconds}s`;
    appendSources(state.sources || []);
    footerStatus.textContent = state.routing
      ? `Ready. Routed to ${state.routing.display_name}.`
      : "Ready.";
  } else if (data.type === "error") {
    appendMessage("system", `Inference error: ${data.error}`);
    footerStatus.textContent = "Generation failed.";
  }
}

function appendSources(sources) {
  if (!sources.length) return;
  const container = document.createElement("div");
  container.className = "message-sources";
  const title = document.createElement("div");
  title.className = "sources-title";
  title.textContent = "Sources";
  container.appendChild(title);
  for (const source of sources) {
    const item = document.createElement("div");
    item.className = "source-item";
    item.textContent = `${source.filename} - Page ${source.page_number} (${source.extraction_method})`;
    container.appendChild(item);
  }
  chatMessages.appendChild(container);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
  const prompt = chatInput.value.trim();
  if (!prompt || isBusy) return;
  chatInput.value = "";
  appendMessage("user", prompt);
  setBusy(true, "chat");
  footerStatus.textContent = "Generating locally...";
  activeChatController = new AbortController();
  const endpoint = appMode === "Knowledge Chat"
    ? "/api/rag/chat"
    : appMode === "Document Analysis" && currentDocId
    ? `/api/documents/${encodeURIComponent(currentDocId)}/chat`
    : "/api/chat";
  const requestBody = { message: prompt, mode: appMode, stream: true };
  if ((appMode === "Knowledge Chat" || appMode === "Auto") && knowledgeCollectionSelect.value) {
    requestBody.collection_id = knowledgeCollectionSelect.value;
  }

  try {
    const response = await apiFetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
      signal: activeChatController.signal,
    });
    if (!response.ok) throw new Error(await responseError(response, "Request failed"));
    if (!response.body) throw new Error("Streaming is not supported by this browser.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const state = { body: null, text: "", sources: [], routing: null };
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const event = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (event.trim()) handleStreamEvent(event, state);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (buffer.trim()) handleStreamEvent(buffer, state);
  } catch (error) {
    if (error.name === "AbortError") {
      appendMessage("system", "Generation stopped.");
      footerStatus.textContent = "Generation stopped.";
    } else {
      appendMessage("system", error.message);
      footerStatus.textContent = "Local model request failed.";
    }
  } finally {
    activeChatController = null;
    setBusy(false);
    chatInput.focus();
  }
}

function setupPdfDropZone(zoneId, input) {
  const zone = byId(zoneId);
  if (!zone || !input) return;

  const hasFiles = (event) => event.dataTransfer && Array.from(event.dataTransfer.types || []).includes("Files");
  const setDragState = (active) => zone.classList.toggle("drag-over", active);

  zone.addEventListener("dragenter", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    setDragState(true);
  });
  zone.addEventListener("dragover", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragState(true);
  });
  zone.addEventListener("dragleave", (event) => {
    if (event.relatedTarget && zone.contains(event.relatedTarget)) return;
    setDragState(false);
  });
  zone.addEventListener("drop", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    setDragState(false);
    const file = Array.from(event.dataTransfer.files || []).find((item) => item.name.toLowerCase().endsWith(".pdf"));
    if (!file) {
      appendMessage("system", "Only PDF files are supported.");
      return;
    }
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

document.addEventListener("dragover", (event) => {
  if (event.dataTransfer && Array.from(event.dataTransfer.types || []).includes("Files")) event.preventDefault();
});
document.addEventListener("drop", (event) => {
  if (event.dataTransfer && Array.from(event.dataTransfer.types || []).includes("Files")) event.preventDefault();
});

pdfFileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    appendMessage("system", "Only PDF files are supported.");
    pdfFileInput.value = "";
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    appendMessage("system", "The PDF exceeds the 25 MB limit.");
    pdfFileInput.value = "";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  uploadProgress.classList.remove("hidden");
  uploadStatusText.textContent = `Processing ${file.name} with local OCR...`;
  footerStatus.textContent = "Validating and extracting PDF...";
  setBusy(true, "upload");
  try {
    const response = await apiFetch("/api/documents", { method: "POST", body: formData });
    if (!response.ok) throw new Error(await responseError(response, "PDF processing failed"));
    const data = await response.json();
    currentDocId = data.document.document_id;
    setChatMode(data.mode);
    currentDocBadge.textContent = `Document: ${data.document.filename}`;
    metricPages.textContent = `Pages: ${data.document.page_count}`;
    metricText.textContent = `Text: ${data.document.extracted_chars.toLocaleString()} chars`;
    metricMethod.textContent = `Method: ${data.document.method_summary}`;
    metricContext.textContent = `Context: ${data.context.included_pages}/${data.context.total_text_pages} pages`;
    appendMessage("system", `Loaded ${data.document.filename}. Document Analysis is active.`);
    footerStatus.textContent = "Document ready.";
  } catch (error) {
    appendMessage("system", `PDF upload error: ${error.message}`);
    footerStatus.textContent = "Failed to load PDF.";
  } finally {
    uploadProgress.classList.add("hidden");
    pdfFileInput.value = "";
    setBusy(false);
  }
});

setupPdfDropZone("direct-pdf-drop-zone", pdfFileInput);

clearBtn.addEventListener("click", async () => {
  if (isBusy) return;
  const response = await apiFetch("/api/chat/clear", { method: "POST" });
  if (!response.ok) {
    appendMessage("system", await responseError(response, "Could not clear the session."));
    return;
  }
  chatMessages.replaceChildren();
  appendMessage("system", "Cleared. General Chat is active.");
  setChatMode("General Chat");
  currentDocBadge.textContent = "No document selected";
  resetMetrics();
  footerStatus.textContent = "Ready.";
});

function setBusy(busy, kind = "") {
  isBusy = busy;
  clearBtn.disabled = busy;
  pdfFileInput.disabled = busy;
  chatInput.disabled = busy;
  knowledgeFileInput.disabled = busy;
  createCollectionBtn.disabled = busy;
  refreshKnowledgeBtn.disabled = busy;
  if (busy && kind === "chat") {
    sendBtn.disabled = false;
    sendBtn.textContent = "Stop";
    sendBtn.classList.add("stop-btn");
  } else {
    sendBtn.disabled = busy;
    sendBtn.textContent = "Send";
    sendBtn.classList.remove("stop-btn");
  }
}

async function loadKnowledgeData() {
  if (!knowledgeDocumentBody) return;
  try {
    const collectionsResponse = await apiFetch("/api/rag/collections");
    if (!collectionsResponse.ok) throw new Error(await responseError(collectionsResponse, "Knowledge base unavailable"));
    knowledgeCollections = (await collectionsResponse.json()).collections;
    const selected = knowledgeCollectionSelect.value;
    knowledgeCollectionSelect.replaceChildren();
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "All my collections";
    knowledgeCollectionSelect.appendChild(all);
    for (const collection of knowledgeCollections) {
      const option = document.createElement("option");
      option.value = collection.collection_id;
      option.textContent = collection.name;
      knowledgeCollectionSelect.appendChild(option);
    }
    if ([...knowledgeCollectionSelect.options].some((option) => option.value === selected)) {
      knowledgeCollectionSelect.value = selected;
    }
    const query = knowledgeCollectionSelect.value ? `?collection_id=${encodeURIComponent(knowledgeCollectionSelect.value)}` : "";
    const docsResponse = await apiFetch(`/api/rag/documents${query}`);
    if (!docsResponse.ok) throw new Error(await responseError(docsResponse, "Could not load indexed documents"));
    renderKnowledgeDocuments((await docsResponse.json()).documents);
    knowledgeStatus.textContent = `${knowledgeCollections.length} collection${knowledgeCollections.length === 1 ? "" : "s"} available.`;
  } catch (error) {
    knowledgeStatus.textContent = error.message;
    knowledgeDocumentBody.replaceChildren();
  }
}

function renderKnowledgeDocuments(documents) {
  knowledgeDocumentBody.replaceChildren();
  const collectionNames = new Map(knowledgeCollections.map((item) => [item.collection_id, item.name]));
  if (!documents.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "table-loading";
    cell.textContent = "No indexed documents in this view.";
    row.appendChild(cell);
    knowledgeDocumentBody.appendChild(row);
    return;
  }
  for (const item of documents) {
    const row = document.createElement("tr");
    for (const value of [item.filename, collectionNames.get(item.collection_id) || "Restricted", item.status, item.page_count || "-", item.chunk_count || "-"]) {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.appendChild(cell);
    }
    const actions = document.createElement("td");
    const reindex = document.createElement("button");
    reindex.className = "btn btn-secondary btn-sm";
    reindex.textContent = "Re-index";
    reindex.addEventListener("click", () => reindexKnowledgeDocument(item.document_id));
    const remove = document.createElement("button");
    remove.className = "btn btn-danger btn-sm";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => deleteKnowledgeDocument(item.document_id, item.filename));
    actions.append(reindex, remove);
    row.appendChild(actions);
    knowledgeDocumentBody.appendChild(row);
  }
}

knowledgeCollectionSelect.addEventListener("change", loadKnowledgeData);
refreshKnowledgeBtn.addEventListener("click", loadKnowledgeData);

createCollectionBtn.addEventListener("click", async () => {
  const name = newCollectionInput.value.trim();
  if (!name) return;
  createCollectionBtn.disabled = true;
  try {
    const response = await apiFetch("/api/rag/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) throw new Error(await responseError(response, "Collection creation failed"));
    const data = await response.json();
    newCollectionInput.value = "";
    await loadKnowledgeData();
    knowledgeCollectionSelect.value = data.collection.collection_id;
    await loadKnowledgeData();
  } catch (error) {
    knowledgeStatus.textContent = error.message;
  } finally {
    createCollectionBtn.disabled = false;
  }
});

knowledgeFileInput.addEventListener("change", async () => {
  const file = knowledgeFileInput.files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    knowledgeStatus.textContent = "Only PDF files are supported.";
    knowledgeFileInput.value = "";
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    knowledgeStatus.textContent = "The PDF exceeds the 25 MB limit.";
    knowledgeFileInput.value = "";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  if (knowledgeCollectionSelect.value) formData.append("collection_id", knowledgeCollectionSelect.value);
  setBusy(true, "upload");
  knowledgeStatus.textContent = `Indexing ${file.name} with local embeddings...`;
  try {
    const response = await apiFetch("/api/rag/documents", { method: "POST", body: formData });
    if (!response.ok) throw new Error(await responseError(response, "Document indexing failed"));
    const data = await response.json();
    knowledgeStatus.textContent = `${data.document.filename} indexed in ${data.collection.name}.`;
    await loadKnowledgeData();
  } catch (error) {
    knowledgeStatus.textContent = error.message;
  } finally {
    knowledgeFileInput.value = "";
    setBusy(false);
  }
});

setupPdfDropZone("knowledge-pdf-drop-zone", knowledgeFileInput);

async function reindexKnowledgeDocument(documentId) {
  knowledgeStatus.textContent = "Re-indexing document...";
  const response = await apiFetch(`/api/rag/documents/${encodeURIComponent(documentId)}/reindex`, { method: "POST" });
  knowledgeStatus.textContent = response.ok ? "Document re-indexed." : await responseError(response, "Re-index failed");
  await loadKnowledgeData();
}

async function deleteKnowledgeDocument(documentId, filename) {
  if (!confirm(`Delete indexed document "${filename}"?`)) return;
  const response = await apiFetch(`/api/rag/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
  knowledgeStatus.textContent = response.ok ? "Document deleted." : await responseError(response, "Delete failed");
  await loadKnowledgeData();
}
