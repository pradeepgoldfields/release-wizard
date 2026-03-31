/* ── Conduit AI Chat Widget ────────────────────────────────────────── */

// ── Drag to move ─────────────────────────────────────────────────────────────
(function () {
  let _dragging = false, _ox = 0, _oy = 0;

  document.addEventListener("DOMContentLoaded", () => {
    const panel  = document.getElementById("chat-panel");
    const header = document.getElementById("chat-header");
    if (!panel || !header) return;

    header.addEventListener("mousedown", e => {
      if (e.target.closest("button")) return;
      if (!panel.classList.contains("open")) return;

      e.preventDefault();

      // Neutralise transform so getBoundingClientRect() gives true pixel position
      panel.style.transition = "none";
      panel.style.transform  = "none";

      const rect = panel.getBoundingClientRect();
      panel.style.bottom = "auto";
      panel.style.right  = "auto";
      panel.style.top    = rect.top  + "px";
      panel.style.left   = rect.left + "px";

      _dragging = true;
      panel.classList.add("dragging");
      _ox = e.clientX - rect.left;
      _oy = e.clientY - rect.top;
    });

    document.addEventListener("mousemove", e => {
      if (!_dragging) return;
      let x = e.clientX - _ox;
      let y = e.clientY - _oy;
      // Keep within viewport
      x = Math.max(0, Math.min(x, window.innerWidth  - panel.offsetWidth));
      y = Math.max(0, Math.min(y, window.innerHeight - panel.offsetHeight));
      panel.style.left = x + "px";
      panel.style.top  = y + "px";
    });

    document.addEventListener("mouseup", () => {
      if (!_dragging) return;
      _dragging = false;
      panel.classList.remove("dragging");
      panel.style.transition = "";  // restore CSS transition
    });
  });
})();

let _chatOpen = false;
let _chatHistory = [];   // Anthropic message format
let _chatBusy = false;
let _recognition = null;
let _isRecording = false;

// ── Panel toggle ─────────────────────────────────────────────────────────────

function toggleChat() {
  _chatOpen = !_chatOpen;
  const panel = document.getElementById("chat-panel");
  panel.classList.toggle("open", _chatOpen);
  document.getElementById("chat-fab").classList.toggle("open", _chatOpen);
  if (_chatOpen) {
    if (_chatHistory.length === 0) _renderWelcome();
    setTimeout(() => document.getElementById("chat-input").focus(), 180);
  }
}

function clearChat() {
  _chatHistory = [];
  _chatBusy = false;
  const msgs = document.getElementById("chat-messages");
  msgs.innerHTML = "";
  _renderWelcome();
  _setSendEnabled(true);
}

function _renderWelcome() {
  const msgs = document.getElementById("chat-messages");
  msgs.innerHTML = `<div class="chat-empty">
    <div style="font-size:28px;margin-bottom:8px">✨</div>
    <strong>Conduit AI</strong><br>
    Ask me about your products, pipelines, releases, compliance status, or audit events.
    <br><br>
    <em>Try: "Show me all products" · "What's the compliance score?" · "List recent pipeline runs"</em>
  </div>`;
}

// ── Send message ──────────────────────────────────────────────────────────────

async function sendChatMessage() {
  if (_chatBusy) return;
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "auto";
  _appendUserMsg(text);
  _chatHistory.push({ role: "user", content: text });

  _setSendEnabled(false);
  _chatBusy = true;
  _setStatus("Thinking…");

  const thinking = _appendThinking();

  try {
    const result = await request("POST", "/chat", { messages: _chatHistory });
    thinking.remove();

    const reply = result.reply || "(no response)";
    _chatHistory.push({ role: "assistant", content: reply });
    _appendAssistantMsg(reply, result.tool_calls || []);
    _setStatus("Ask me anything");
  } catch (e) {
    thinking.remove();
    _appendAssistantMsg(`Sorry, something went wrong: ${e.message}`, []);
    _setStatus("Ask me anything");
  } finally {
    _chatBusy = false;
    _setSendEnabled(true);
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

function _clearWelcome() {
  const msgs = document.getElementById("chat-messages");
  const empty = msgs.querySelector(".chat-empty");
  if (empty) empty.remove();
}

function _appendUserMsg(text) {
  _clearWelcome();
  const msgs = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "chat-msg user";
  div.textContent = text;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function _appendThinking() {
  const msgs = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "chat-msg thinking";
  div.innerHTML = `<span style="animation:pulse-dot 1s infinite;display:inline-block">●</span> Querying platform data…`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function _appendAssistantMsg(markdown, toolCalls) {
  const msgs = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "chat-msg assistant";

  // Render tool badges
  if (toolCalls && toolCalls.length > 0) {
    const badgesDiv = document.createElement("div");
    badgesDiv.style.marginBottom = "6px";
    const unique = [...new Set(toolCalls)];
    badgesDiv.innerHTML = unique.map(t => `<span class="chat-tool-badge">⚙ ${t.replace(/_/g," ")}</span>`).join("");
    div.appendChild(badgesDiv);
  }

  // Simple markdown to HTML
  const html = _mdToHtml(markdown);
  const content = document.createElement("div");
  content.innerHTML = html;
  div.appendChild(content);

  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function _setStatus(text) {
  const el = document.getElementById("chat-status");
  if (el) el.textContent = text;
}

function _setSendEnabled(enabled) {
  const btn = document.getElementById("chat-send-btn");
  if (btn) btn.disabled = !enabled;
}

// ── Minimal markdown renderer ─────────────────────────────────────────────────

function _mdToHtml(md) {
  if (!md) return "";
  let html = md
    // Escape HTML first
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    // Code blocks
    .replace(/```[\w]*\n?([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
    // Inline code
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Headers
    .replace(/^### (.+)$/gm, "<h4 style='margin:8px 0 4px;font-size:13px'>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3 style='margin:8px 0 4px;font-size:14px'>$1</h3>")
    .replace(/^# (.+)$/gm, "<h2 style='margin:8px 0 4px;font-size:15px'>$1</h2>")
    // Horizontal rule
    .replace(/^---$/gm, "<hr style='border:none;border-top:1px solid var(--gray-200);margin:8px 0'>")
    // Unordered lists
    .replace(/^\s*[-*] (.+)$/gm, "<li>$1</li>")
    // Numbered lists
    .replace(/^\s*\d+\. (.+)$/gm, "<li>$1</li>")
    // Paragraphs / line breaks
    .replace(/\n\n/g, "</p><p style='margin:6px 0'>")
    .replace(/\n/g, "<br>");

  // Wrap li items in ul
  html = html.replace(/(<li>.*?<\/li>(\s*<br>)*)+/g, (m) => `<ul style='margin:4px 0 4px 16px;padding:0'>${m.replace(/<br>/g,"")}</ul>`);

  return `<p style='margin:0'>${html}</p>`;
}

// ── Auto-resize textarea ──────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-input");
  if (!input) return;

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 100) + "px";
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
});

// ── Voice input (Web Speech API) ─────────────────────────────────────────────

function toggleVoice() {
  if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
    alert("Voice input is not supported in this browser. Try Chrome or Edge.");
    return;
  }

  if (_isRecording) {
    _stopRecording();
  } else {
    _startRecording();
  }
}

function _startRecording() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  _recognition = new SpeechRecognition();
  _recognition.lang = "en-US";
  _recognition.interimResults = true;
  _recognition.maxAlternatives = 1;

  const micBtn = document.getElementById("chat-mic-btn");
  const voiceIndicator = document.getElementById("chat-voice-indicator");
  const input = document.getElementById("chat-input");

  _recognition.onstart = () => {
    _isRecording = true;
    micBtn.classList.add("recording");
    micBtn.textContent = "🔴";
    voiceIndicator.style.display = "flex";
  };

  _recognition.onresult = (e) => {
    let transcript = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    input.value = transcript;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 100) + "px";
  };

  _recognition.onend = () => {
    _isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.textContent = "🎤";
    voiceIndicator.style.display = "none";
    // Auto-send if there's text
    if (input.value.trim()) sendChatMessage();
  };

  _recognition.onerror = (e) => {
    _isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.textContent = "🎤";
    voiceIndicator.style.display = "none";
    if (e.error !== "aborted") {
      _appendAssistantMsg(`Voice input error: ${e.error}`, []);
    }
  };

  _recognition.start();
}

function _stopRecording() {
  if (_recognition) {
    _recognition.stop();
    _recognition = null;
  }
}
