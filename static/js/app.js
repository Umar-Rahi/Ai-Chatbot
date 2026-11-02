/**
 * NexusAI — Frontend Application
 * ChatGPT-inspired AI chatbot with streaming, markdown, and persistent history.
 */

"use strict";

// ── marked.js config ───────────────────────────────────────────────────────
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: null,           // we handle highlight ourselves
});

// Custom renderer to wrap code blocks in our styled container
const renderer = new marked.Renderer();
renderer.code = function (code, lang) {
  const language = lang || "plaintext";
  let highlighted;
  try {
    highlighted = hljs.highlight(code, { language, ignoreIllegals: true }).value;
  } catch {
    highlighted = hljs.highlightAuto(code).value;
  }
  return `
<div class="code-block-wrapper">
  <div class="code-block-header">
    <span class="code-lang">${language}</span>
    <button class="copy-code-btn" aria-label="Copy code">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      Copy
    </button>
  </div>
  <pre><code class="hljs language-${language}">${highlighted}</code></pre>
</div>`;
};
marked.use({ renderer });

// ── DOM references ─────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const app = {
  sidebar:             $("sidebar"),
  sidebarToggle:       $("sidebarToggle"),
  mobileSidebarToggle: $("mobileSidebarToggle"),
  sidebarOverlay:      $("sidebarOverlay"),
  newChatBtn:          $("newChatBtn"),
  historySearch:       $("historySearch"),
  conversationList:    $("conversationList"),
  clearAllBtn:         $("clearAllBtn"),
  settingsBtn:         $("settingsBtn"),
  chatContainer:       $("chatContainer"),
  welcomeScreen:       $("welcomeScreen"),
  messagesArea:        $("messagesArea"),
  messageInput:        $("messageInput"),
  sendBtn:             $("sendBtn"),
  charCount:           $("charCount"),
  stopGenBtn:          $("stopGenBtn"),
  stopGeneration:      $("stopGeneration"),
  modelSelector:       $("modelSelector"),
  apiStatusBadge:      $("apiStatusBadge"),
  // Settings modal
  settingsModal:       $("settingsModal"),
  closeSettings:       $("closeSettings"),
  settingsModelSel:    $("settingsModelSelector"),
  settingsApiStatus:   $("settingsApiStatus"),
  refreshStatusBtn:    $("refreshStatusBtn"),
  // Confirm modal
  confirmModal:        $("confirmModal"),
  confirmTitle:        $("confirmTitle"),
  confirmMessage:      $("confirmMessage"),
  confirmOk:           $("confirmOk"),
  confirmCancel:       $("confirmCancel"),
  // Rename modal
  renameModal:         $("renameModal"),
  closeRename:         $("closeRename"),
  renameInput:         $("renameInput"),
  renameConfirmBtn:    $("renameConfirmBtn"),
  renameCancelBtn:     $("renameCancelBtn"),
  toastContainer:      $("toastContainer"),
};

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  conversations:      [],     // [{id, title, updated_at}]
  activeId:           null,   // currently open conversation id
  isGenerating:       false,
  abortController:    null,
  currentModel:       "",     // populated by loadModels() from /api/models
  searchQuery:        "",
};

// ── Toast notifications ────────────────────────────────────────────────────
function showToast(message, type = "info", duration = 3500) {
  const icons = { success: "✓", error: "✕", info: "ℹ" };
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${escapeHtml(message)}</span>`;
  app.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(4px)";
    toast.style.transition = "opacity 0.2s ease, transform 0.2s ease";
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// ── Escape HTML helper ─────────────────────────────────────────────────────
function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// ── Render markdown safely ─────────────────────────────────────────────────
function renderMarkdown(text) {
  const raw = marked.parse(text);
  return DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: [
      "p","br","b","i","em","strong","code","pre","ul","ol","li",
      "h1","h2","h3","h4","h5","h6","blockquote","a","table","thead",
      "tbody","tr","th","td","hr","span","div","button","svg","path",
      "line","polyline","rect","circle","polygon",
    ],
    ALLOWED_ATTR: [
      "href","class","aria-label","viewBox","fill","stroke","stroke-width",
      "stroke-linecap","stroke-linejoin","width","height","x","y","x1","y1",
      "x2","y2","cx","cy","r","rx","ry","d","points",
    ],
    ALLOW_DATA_ATTR: false,
  });
}

// ── Format timestamp ───────────────────────────────────────────────────────
function formatTs(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return d.toLocaleDateString();
  } catch { return ""; }
}

// ── Sidebar toggle (desktop) ───────────────────────────────────────────────
function toggleSidebar() {
  app.sidebar.classList.toggle("collapsed");
  const isCollapsed = app.sidebar.classList.contains("collapsed");
  app.sidebarToggle.setAttribute("aria-label", isCollapsed ? "Expand sidebar" : "Collapse sidebar");
  localStorage.setItem("sidebar-collapsed", isCollapsed ? "1" : "0");
}

// ── Mobile sidebar ─────────────────────────────────────────────────────────
function openMobileSidebar() {
  app.sidebar.classList.add("mobile-open");
  app.sidebarOverlay.classList.add("visible");
  document.body.style.overflow = "hidden";
}
function closeMobileSidebar() {
  app.sidebar.classList.remove("mobile-open");
  app.sidebarOverlay.classList.remove("visible");
  document.body.style.overflow = "";
}

// ── Load conversations from backend ───────────────────────────────────────
async function loadConversations() {
  try {
    const res = await fetch("/api/conversations");
    if (!res.ok) throw new Error("Failed to load conversations");
    state.conversations = await res.json();
    renderConversationList();
  } catch (err) {
    console.error("loadConversations:", err);
  }
}

// ── Render conversation list ───────────────────────────────────────────────
function renderConversationList() {
  const q = state.searchQuery.toLowerCase();
  const list = q
    ? state.conversations.filter(c => c.title.toLowerCase().includes(q))
    : state.conversations;

  if (list.length === 0) {
    app.conversationList.innerHTML = `<div class="empty-history">${
      q ? "No conversations match your search." : "No conversations yet.<br>Start a new chat!"
    }</div>`;
    return;
  }

  // Group by recency
  const groups = { Today: [], "This week": [], Earlier: [] };
  const now = new Date();
  list.forEach(c => {
    const d = new Date(c.updated_at);
    const diffH = (now - d) / 3600000;
    if (diffH < 24) groups["Today"].push(c);
    else if (diffH < 24 * 7) groups["This week"].push(c);
    else groups["Earlier"].push(c);
  });

  let html = "";
  for (const [label, items] of Object.entries(groups)) {
    if (!items.length) continue;
    html += `<div class="conv-group-label">${label}</div>`;
    items.forEach(c => {
      const active = c.id === state.activeId ? " active" : "";
      html += `
        <button class="conv-item${active}" data-id="${c.id}" aria-label="Open conversation: ${escapeHtml(c.title)}">
          <span class="conv-item-title">${escapeHtml(c.title)}</span>
          <span class="conv-item-actions">
            <span class="conv-action-btn rename" data-id="${c.id}" title="Rename" role="button" aria-label="Rename conversation" tabindex="0">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </span>
            <span class="conv-action-btn delete" data-id="${c.id}" title="Delete" role="button" aria-label="Delete conversation" tabindex="0">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </span>
          </span>
        </button>`;
    });
  }
  app.conversationList.innerHTML = html;
}

// ── Show welcome screen ────────────────────────────────────────────────────
function showWelcome() {
  app.welcomeScreen.style.display = "";
  app.messagesArea.innerHTML = "";
  app.messagesArea.style.display = "none";
  state.activeId = null;
  renderConversationList();
}

// ── Show messages area ─────────────────────────────────────────────────────
function showMessages() {
  app.welcomeScreen.style.display = "none";
  app.messagesArea.style.display = "";
}

// ── Scroll to bottom of chat ───────────────────────────────────────────────
function scrollToBottom(force = false) {
  const el = app.chatContainer;
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
  if (force || isNearBottom) {
    el.scrollTop = el.scrollHeight;
  }
}

// ── Create message element ─────────────────────────────────────────────────
function createMessageElement(role, content, ts = null) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  row.dataset.role = role;

  const avatarText = role === "user" ? "You" : "✦";
  const avatar = `<div class="message-avatar" aria-hidden="true">${role === "user" ? "U" : "✦"}</div>`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (role === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
    attachCodeCopyHandlers(bubble);
  } else {
    bubble.textContent = content;
  }

  const actions = document.createElement("div");
  actions.className = "message-actions";

  const timestamp = ts ? `<span class="message-timestamp">${formatTs(ts)}</span>` : "";

  const copyBtn = document.createElement("button");
  copyBtn.className = "msg-action-btn copy-msg";
  copyBtn.setAttribute("aria-label", "Copy message");
  copyBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
  copyBtn.addEventListener("click", () => copyText(content, copyBtn));
  actions.appendChild(copyBtn);

  if (role === "assistant") {
    const regenBtn = document.createElement("button");
    regenBtn.className = "msg-action-btn regen-msg";
    regenBtn.setAttribute("aria-label", "Regenerate response");
    regenBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.77"/></svg> Regenerate`;
    regenBtn.addEventListener("click", () => regenerateLastMessage());
    actions.appendChild(regenBtn);
  }

  const body = document.createElement("div");
  body.className = "message-body";
  body.appendChild(bubble);
  if (timestamp) body.insertAdjacentHTML("beforeend", timestamp);
  body.appendChild(actions);

  row.innerHTML = avatar;
  row.appendChild(body);
  return { row, bubble };
}

// ── Attach copy button handlers to code blocks ─────────────────────────────
function attachCodeCopyHandlers(container) {
  container.querySelectorAll(".copy-code-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const pre = btn.closest(".code-block-wrapper")?.querySelector("pre");
      if (!pre) return;
      copyText(pre.innerText, btn, "Copied!", "Copy");
    });
  });
}

// ── Copy text to clipboard ─────────────────────────────────────────────────
async function copyText(text, btn = null, successLabel = "Copied", defaultLabel = "Copy") {
  try {
    await navigator.clipboard.writeText(text);
    showToast("Copied to clipboard", "success", 2000);
    if (btn) {
      const orig = btn.innerHTML;
      btn.classList.add("copied");
      btn.innerHTML = btn.innerHTML.replace(/Copy\w*/, successLabel);
      setTimeout(() => {
        btn.classList.remove("copied");
        btn.innerHTML = orig;
      }, 2000);
    }
  } catch {
    showToast("Failed to copy", "error");
  }
}

// ── Load a conversation ────────────────────────────────────────────────────
async function loadConversation(id) {
  try {
    const res = await fetch(`/api/conversations/${id}`);
    if (!res.ok) { showToast("Could not load conversation", "error"); return; }
    const conv = await res.json();
    state.activeId = id;
    showMessages();
    app.messagesArea.innerHTML = "";

    conv.messages.forEach(msg => {
      if (msg.role === "system") return;
      const { row } = createMessageElement(msg.role, msg.content, msg.created_at);
      app.messagesArea.appendChild(row);
    });

    scrollToBottom(true);
    renderConversationList();

    // On mobile, close sidebar after selecting
    if (window.innerWidth <= 768) closeMobileSidebar();
  } catch (err) {
    console.error("loadConversation:", err);
    showToast("Failed to load conversation", "error");
  }
}

// ── New chat ───────────────────────────────────────────────────────────────
function startNewChat() {
  if (state.isGenerating) {
    abortGeneration();
  }
  showWelcome();
  app.messageInput.focus();
}

// ── Send message ───────────────────────────────────────────────────────────
async function sendMessage(text) {
  if (state.isGenerating) return;
  text = text.trim();
  if (!text) return;
  // Ensure models have been loaded before sending
  if (!state.currentModel) {
    showToast("Please wait — loading model list…", "info", 2000);
    return;
  }

  // Show messages area
  showMessages();

  // Append user message
  const { row: userRow } = createMessageElement("user", text, new Date().toISOString());
  app.messagesArea.appendChild(userRow);
  scrollToBottom(true);

  // Clear input
  app.messageInput.value = "";
  app.messageInput.style.height = "auto";
  updateSendBtn();

  // Show typing indicator
  const typingRow = createTypingIndicator();
  app.messagesArea.appendChild(typingRow);
  scrollToBottom(true);

  setGenerating(true);

  // SSE streaming
  const body = {
    message: text,
    conversation_id: state.activeId || null,
    model: state.currentModel,
  };

  state.abortController = new AbortController();
  let assistantRow = null;
  let assistantBubble = null;
  let fullText = "";
  // Set to true when the server sends a clean "done" SSE event.
  let streamDone = false;
  // Holds any SSE-level error message so it can be shown after cleanup.
  let sseError = null;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: state.abortController.signal,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Server error");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // Drain the stream.  No awaits other than reader.read() itself — all
    // deferred work (sidebar refresh) happens in finally so the loop exits
    // cleanly and the composer is re-enabled without any extra delay.
    outer: while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep the last potentially-incomplete chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        let payload;
        try { payload = JSON.parse(line.slice(5).trim()); } catch { continue; }

        if (payload.type === "start") {
          state.activeId = payload.conversation_id;
          // Swap typing indicator for the live assistant bubble
          typingRow.remove();
          const created = createMessageElement("assistant", "", new Date().toISOString());
          assistantRow = created.row;
          assistantBubble = created.bubble;
          app.messagesArea.appendChild(assistantRow);
          scrollToBottom();
        }

        if (payload.type === "chunk") {
          if (assistantBubble) {
            fullText += payload.content;
            assistantBubble.innerHTML = renderMarkdown(fullText);
            attachCodeCopyHandlers(assistantBubble);
            scrollToBottom();
          }
        }

        if (payload.type === "done") {
          state.activeId = payload.conversation_id;
          streamDone = true;
          // Break out immediately — no awaits here so finally runs fast.
          break outer;
        }

        if (payload.type === "error") {
          sseError = payload.error || "An error occurred.";
          break outer;
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      // User pressed Stop — annotate the partial response and fall through.
      if (assistantBubble && fullText) {
        assistantBubble.innerHTML = renderMarkdown(fullText + "\n\n*[Generation stopped]*");
        attachCodeCopyHandlers(assistantBubble);
      }
    } else {
      showErrorMessage(err.message || "Network error. Please try again.");
    }
  } finally {
    // ── Single cleanup point — always executes ─────────────────────────
    typingRow.remove();     // safe no-op if already detached
    setGenerating(false);   // re-enables textarea, hides Stop button
    state.abortController = null;
    scrollToBottom();
    app.messageInput.focus();

    // Show any SSE-level error after controls are already re-enabled.
    if (sseError) {
      showErrorMessage(sseError);
    }

    // Refresh sidebar only after the stream is fully drained and the
    // composer is already re-enabled (non-blocking — no await here).
    if (streamDone) {
      loadConversations().then(renderConversationList);
    }
  }
}

// ── Typing indicator ───────────────────────────────────────────────────────
function createTypingIndicator() {
  const row = document.createElement("div");
  row.className = "message-row assistant typing";
  row.innerHTML = `
    <div class="message-avatar" aria-hidden="true">✦</div>
    <div class="message-body">
      <div class="message-bubble">
        <div class="typing-indicator" aria-label="AI is typing">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>`;
  return row;
}

// ── Show error in chat ─────────────────────────────────────────────────────
function showErrorMessage(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="message-avatar" aria-hidden="true">✦</div>
    <div class="message-body">
      <div class="message-bubble" style="border-color: var(--danger); background: var(--danger-dim);">
        <strong>Error:</strong> ${escapeHtml(message)}
      </div>
    </div>`;
  app.messagesArea.appendChild(row);
  scrollToBottom(true);
  showToast(message, "error");
}

// ── Abort generation ───────────────────────────────────────────────────────
function abortGeneration() {
  if (state.abortController) {
    state.abortController.abort();
  }
}

// ── Set generating state ───────────────────────────────────────────────────
function setGenerating(generating) {
  state.isGenerating = generating;
  app.sendBtn.disabled = generating || !app.messageInput.value.trim();
  app.stopGenBtn.hidden = !generating;
  app.messageInput.disabled = generating;
}

// ── Regenerate last message ────────────────────────────────────────────────
async function regenerateLastMessage() {
  if (!state.activeId || state.isGenerating) return;
  try {
    const res = await fetch(`/api/conversations/${state.activeId}`);
    if (!res.ok) return;
    const conv = await res.json();
    const userMsgs = conv.messages.filter(m => m.role === "user");
    if (!userMsgs.length) return;
    const lastUserMsg = userMsgs[userMsgs.length - 1].content;

    // Delete last assistant message from DOM
    const rows = app.messagesArea.querySelectorAll(".message-row.assistant");
    if (rows.length) rows[rows.length - 1].remove();

    // Re-send same user message with existing conversation_id
    await sendMessage(lastUserMsg);
  } catch (err) {
    console.error("regenerate:", err);
    showToast("Could not regenerate response", "error");
  }
}

// ── Input auto-resize ──────────────────────────────────────────────────────
function autoResizeInput() {
  const el = app.messageInput;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 220) + "px";
}

// ── Update send button ─────────────────────────────────────────────────────
function updateSendBtn() {
  const val = app.messageInput.value;
  const len = val.length;
  const max = 4000;
  app.sendBtn.disabled = !val.trim() || state.isGenerating;

  // Character count
  if (len > max * 0.8) {
    const pct = `${len}/${max}`;
    app.charCount.textContent = pct;
    app.charCount.className = "char-count " + (len >= max ? "error" : "warning");
  } else {
    app.charCount.textContent = "";
    app.charCount.className = "char-count";
  }
}

// ── Load models ────────────────────────────────────────────────────────────
async function loadModels() {
  try {
    const res = await fetch("/api/models");
    if (!res.ok) return;
    const data = await res.json();

    // Always start with the server-authoritative default
    state.currentModel = data.default;

    const populateSelect = (sel) => {
      sel.innerHTML = "";
      data.models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === data.default) opt.selected = true;
        sel.appendChild(opt);
      });
    };
    populateSelect(app.modelSelector);
    populateSelect(app.settingsModelSel);

    // Restore saved model only if it is still in the current allowed list;
    // otherwise clear the stale localStorage value so it doesn't persist.
    const saved = localStorage.getItem("nexus-model");
    if (saved && data.models.includes(saved)) {
      state.currentModel = saved;
      app.modelSelector.value = saved;
      app.settingsModelSel.value = saved;
    } else if (saved) {
      localStorage.removeItem("nexus-model");
    }
  } catch (err) {
    console.error("loadModels:", err);
  }
}

// ── Check API status ───────────────────────────────────────────────────────
async function checkApiStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const online = data.ok;
    const badge = app.apiStatusBadge;
    const settingsStatus = app.settingsApiStatus;

    badge.className = "api-badge " + (online ? "online" : "offline");
    badge.querySelector(".status-text").textContent = online ? "Connected" : "Disconnected";

    if (settingsStatus) {
      settingsStatus.className = "api-status-text " + (online ? "online" : "offline");
      settingsStatus.textContent = online ? "✓ Connected" : "✕ " + (data.message || "Disconnected");
    }
  } catch {
    app.apiStatusBadge.className = "api-badge offline";
    app.apiStatusBadge.querySelector(".status-text").textContent = "Offline";
  }
}

// ── Confirm dialog ─────────────────────────────────────────────────────────
let _confirmResolve = null;
function confirm(title, message) {
  return new Promise(resolve => {
    _confirmResolve = resolve;
    app.confirmTitle.textContent = title;
    app.confirmMessage.textContent = message;
    app.confirmModal.hidden = false;
  });
}

// ── Rename conversation ────────────────────────────────────────────────────
let _renameId = null;
function openRenameModal(id, currentTitle) {
  _renameId = id;
  app.renameInput.value = currentTitle;
  app.renameModal.hidden = false;
  setTimeout(() => { app.renameInput.select(); }, 50);
}

async function submitRename() {
  const newTitle = app.renameInput.value.trim();
  if (!newTitle) { showToast("Title cannot be empty", "error"); return; }
  try {
    const res = await fetch(`/api/conversations/${_renameId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
    if (!res.ok) throw new Error((await res.json()).error);
    const c = state.conversations.find(x => x.id === _renameId);
    if (c) c.title = newTitle;
    renderConversationList();
    showToast("Conversation renamed", "success");
  } catch (err) {
    showToast(err.message || "Could not rename", "error");
  } finally {
    app.renameModal.hidden = true;
    _renameId = null;
  }
}

// ── Delete conversation ────────────────────────────────────────────────────
async function deleteConversation(id) {
  const ok = await confirm("Delete conversation", "This conversation will be permanently deleted. Are you sure?");
  if (!ok) return;
  try {
    const res = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error((await res.json()).error);
    state.conversations = state.conversations.filter(c => c.id !== id);
    if (state.activeId === id) startNewChat();
    renderConversationList();
    showToast("Conversation deleted", "success");
  } catch (err) {
    showToast(err.message || "Could not delete", "error");
  }
}

// ── Clear all conversations ────────────────────────────────────────────────
async function clearAllConversations() {
  const ok = await confirm("Clear all history", "All conversations will be permanently deleted. This cannot be undone.");
  if (!ok) return;
  try {
    const res = await fetch("/api/conversations", { method: "DELETE" });
    if (!res.ok) throw new Error("Failed");
    state.conversations = [];
    state.activeId = null;
    showWelcome();
    showToast("All conversations cleared", "success");
  } catch {
    showToast("Could not clear history", "error");
  }
}

// ── Theme ──────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("nexus-theme", theme);
  document.querySelectorAll(".theme-btn").forEach(btn => {
    const active = btn.dataset.theme === theme;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    app.settingsModal.hidden = true;
    app.confirmModal.hidden = true;
    app.renameModal.hidden = true;
    closeMobileSidebar();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    startNewChat();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "/") {
    e.preventDefault();
    app.settingsModal.hidden = false;
    checkApiStatus();
  }
});

// ── Event listeners ────────────────────────────────────────────────────────
function setupEventListeners() {
  // Sidebar
  app.sidebarToggle.addEventListener("click", toggleSidebar);
  app.mobileSidebarToggle.addEventListener("click", openMobileSidebar);
  app.sidebarOverlay.addEventListener("click", closeMobileSidebar);

  // New chat
  app.newChatBtn.addEventListener("click", startNewChat);

  // Conversation list delegation
  app.conversationList.addEventListener("click", e => {
    const convItem = e.target.closest(".conv-item");
    const renameBtn = e.target.closest(".conv-action-btn.rename");
    const deleteBtn = e.target.closest(".conv-action-btn.delete");

    if (renameBtn) {
      e.stopPropagation();
      const id = renameBtn.dataset.id;
      const conv = state.conversations.find(c => c.id === id);
      if (conv) openRenameModal(id, conv.title);
      return;
    }
    if (deleteBtn) {
      e.stopPropagation();
      deleteConversation(deleteBtn.dataset.id);
      return;
    }
    if (convItem) {
      loadConversation(convItem.dataset.id);
    }
  });

  // Also handle keyboard on action buttons
  app.conversationList.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      const btn = e.target.closest(".conv-action-btn");
      if (btn) btn.click();
    }
  });

  // Search
  app.historySearch.addEventListener("input", e => {
    state.searchQuery = e.target.value;
    renderConversationList();
  });

  // Clear all
  app.clearAllBtn.addEventListener("click", clearAllConversations);

  // Settings
  app.settingsBtn.addEventListener("click", () => {
    app.settingsModal.hidden = false;
    checkApiStatus();
  });
  app.closeSettings.addEventListener("click", () => { app.settingsModal.hidden = true; });
  app.settingsModal.addEventListener("click", e => {
    if (e.target === app.settingsModal) app.settingsModal.hidden = true;
  });

  // Theme
  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme));
  });

  // Model selector
  app.modelSelector.addEventListener("change", e => {
    state.currentModel = e.target.value;
    app.settingsModelSel.value = e.target.value;
    localStorage.setItem("nexus-model", state.currentModel);
  });
  app.settingsModelSel.addEventListener("change", e => {
    state.currentModel = e.target.value;
    app.modelSelector.value = e.target.value;
    localStorage.setItem("nexus-model", state.currentModel);
  });

  // API status refresh
  app.refreshStatusBtn.addEventListener("click", checkApiStatus);

  // Confirm modal
  app.confirmOk.addEventListener("click", () => {
    app.confirmModal.hidden = true;
    if (_confirmResolve) { _confirmResolve(true); _confirmResolve = null; }
  });
  app.confirmCancel.addEventListener("click", () => {
    app.confirmModal.hidden = true;
    if (_confirmResolve) { _confirmResolve(false); _confirmResolve = null; }
  });
  app.confirmModal.addEventListener("click", e => {
    if (e.target === app.confirmModal) {
      app.confirmModal.hidden = true;
      if (_confirmResolve) { _confirmResolve(false); _confirmResolve = null; }
    }
  });

  // Rename modal
  app.renameConfirmBtn.addEventListener("click", submitRename);
  app.renameCancelBtn.addEventListener("click", () => { app.renameModal.hidden = true; });
  app.closeRename.addEventListener("click", () => { app.renameModal.hidden = true; });
  app.renameInput.addEventListener("keydown", e => {
    if (e.key === "Enter") submitRename();
    if (e.key === "Escape") { app.renameModal.hidden = true; }
  });
  app.renameModal.addEventListener("click", e => {
    if (e.target === app.renameModal) app.renameModal.hidden = true;
  });

  // Composer input
  app.messageInput.addEventListener("input", () => {
    autoResizeInput();
    updateSendBtn();
  });

  app.messageInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!app.sendBtn.disabled) sendMessage(app.messageInput.value);
    }
  });

  app.sendBtn.addEventListener("click", () => {
    if (!app.sendBtn.disabled) sendMessage(app.messageInput.value);
  });

  // Stop generation
  app.stopGeneration.addEventListener("click", abortGeneration);

  // Suggestion cards
  document.querySelectorAll(".suggestion-card").forEach(card => {
    card.addEventListener("click", () => {
      const prompt = card.dataset.prompt;
      app.messageInput.value = prompt;
      autoResizeInput();
      updateSendBtn();
      app.messageInput.focus();
      // Auto-send if prompt is complete (doesn't end with space)
      if (!prompt.endsWith(" ")) {
        sendMessage(prompt);
      }
    });
  });
}

// ── Initialise ────────────────────────────────────────────────────────────
async function init() {
  // Restore theme
  const theme = localStorage.getItem("nexus-theme") || "dark";
  applyTheme(theme);

  // Restore sidebar state (desktop)
  const sidebarCollapsed = localStorage.getItem("sidebar-collapsed") === "1";
  if (sidebarCollapsed) app.sidebar.classList.add("collapsed");

  // Load models + conversations
  await Promise.all([loadModels(), loadConversations()]);

  // Check API status
  checkApiStatus();

  // Set up all event listeners
  setupEventListeners();

  // Show welcome
  showWelcome();

  // Focus input
  setTimeout(() => app.messageInput.focus(), 100);
}

document.addEventListener("DOMContentLoaded", init);
