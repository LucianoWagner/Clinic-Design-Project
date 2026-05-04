/* ===================================================================
   Consultorio — Chat Frontend
   Todos los selectores con fallback null-safe para evitar crashes.
   El DOM ya está cargado porque este script está al final del <body>.
   =================================================================== */

/* ─── DOM References ─────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

const messagesEl      = $("messages");
const chatForm        = $("chatForm");
const messageInput    = $("messageInput");
const statusBar       = $("statusBar");
const voiceButton     = $("voiceButton");
const ttsToggle       = $("ttsToggle");
const typingIndicator = $("typingIndicator");
const sendButton      = $("sendButton");
const newChatBtn      = $("newChatBtn");

/* Defensive check: log and abort if any critical element is missing */
const criticalEls = { messagesEl, chatForm, messageInput };
for (const [name, el] of Object.entries(criticalEls)) {
  if (!el) { console.error(`[Consultorio] Elemento faltante: #${name}`); }
}

/* ─── App State ─────────────────────────────────────────────────── */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition    = null;
let isLoading      = false;
let conversationId = localStorage.getItem("conversationId");

/* ─── UI Helpers ─────────────────────────────────────────────────── */

/** Agrega una burbuja de mensaje al chat con clases Tailwind */
function addMessage(role, text) {
  if (!messagesEl) return;
  const bubble = document.createElement("div");
  // Base classes
  bubble.classList.add(
    "message", "max-w-[78%]", "px-4", "py-3", "rounded-2xl",
    "text-sm", "leading-relaxed", "whitespace-pre-wrap"
  );
  if (role === "user") {
    bubble.classList.add(
      "self-end",
      "bg-cyan-500/10", "border", "border-cyan-500/25",
      "text-slate-100", "rounded-br-sm"
    );
  } else {
    bubble.classList.add(
      "self-start",
      "bg-slate-800", "border", "border-slate-700",
      "text-slate-200", "rounded-bl-sm",
      "border-l-2", "border-l-cyan-500/50"
    );
  }
  bubble.textContent = text;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/** Muestra/oculta el indicador de typing */
function showTyping() {
  typingIndicator?.classList.remove("hidden");
  if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
}
function hideTyping() {
  typingIndicator?.classList.add("hidden");
}

/** Actualiza la barra de estado (sin sobreescribir clases Tailwind base) */
function setStatus(text, variant = "") {
  if (!statusBar) return;
  statusBar.textContent = text;
  // Solo cambia el color del texto según la variante
  statusBar.classList.remove("text-red-400", "text-cyan-400", "text-slate-500");
  if (variant === "error")     statusBar.classList.add("text-red-400");
  else if (variant === "info") statusBar.classList.add("text-cyan-400");
  else                         statusBar.classList.add("text-slate-500");
}

/** Bloquea/desbloquea la interfaz durante la carga */
function setLoading(loading) {
  isLoading = loading;
  if (messageInput) messageInput.disabled = loading;

  if (sendButton) {
    if (loading) {
      sendButton.classList.add("opacity-50", "cursor-not-allowed");
      sendButton.innerHTML = `
        <svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <path stroke-linecap="round" d="M12 2a10 10 0 0 1 10 10"/>
        </svg>`;
    } else {
      sendButton.classList.remove("opacity-50", "cursor-not-allowed");
      sendButton.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>`;
    }
  }
}

/* ─── TTS ───────────────────────────────────────────────────────── */
function speak(text) {
  if (!ttsToggle?.checked || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u  = new SpeechSynthesisUtterance(text);
  u.lang   = "es-AR";
  u.rate   = 1;
  u.pitch  = 1;
  window.speechSynthesis.speak(u);
}

/* ─── API: Conversation Init ─────────────────────────────────────── */
async function ensureConversation() {
  if (conversationId) return conversationId;
  const res = await fetch("/api/conversations", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ channel: "web_chat" }),
  });
  if (!res.ok) throw new Error(`No se pudo iniciar la conversación (${res.status})`);
  const data     = await res.json();
  conversationId = String(data.id);
  localStorage.setItem("conversationId", conversationId);
  return conversationId;
}

/* ─── Send Message ───────────────────────────────────────────────── */
async function sendMessage(text, inputMode = "text") {
  if (isLoading) return;  // prevent double-sends
  const trimmed = text.trim();
  if (!trimmed) return;

  addMessage("user", trimmed);
  if (messageInput) messageInput.value = "";

  setLoading(true);
  showTyping();
  setStatus("El asistente está procesando tu consulta…", "info");

  try {
    const id  = await ensureConversation();
    const res = await fetch(`/api/conversations/${id}/messages`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ message: trimmed, input_mode: inputMode }),
    });

    hideTyping();

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Error del servidor (${res.status})`);
    }

    const data = await res.json();
    addMessage("assistant", data.response);
    speak(data.response);
    setStatus("");
  } catch (err) {
    hideTyping();
    addMessage("assistant", "Hubo un problema al procesar tu consulta. Por favor intentá de nuevo.");
    setStatus(`⚠ ${err.message}`, "error");
    console.error("[Consultorio]", err);
  } finally {
    setLoading(false);
    messageInput?.focus();
  }
}

/* ─── Form Submit ────────────────────────────────────────────────── */
chatForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(messageInput?.value ?? "");
});

/* ─── Enter key (no Shift) ───────────────────────────────────────── */
messageInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !isLoading) {
    e.preventDefault();
    sendMessage(messageInput.value);
  }
});

/* ─── Voice Recognition ──────────────────────────────────────────── */
voiceButton?.addEventListener("click", () => {
  if (!SpeechRecognition) {
    setStatus("Tu navegador no soporta reconocimiento de voz. Usá Chrome o Edge.", "error");
    return;
  }
  if (recognition) { recognition.stop(); return; }

  recognition = new SpeechRecognition();
  recognition.lang           = "es-AR";
  recognition.interimResults = false;
  recognition.continuous     = false;

  recognition.onstart = () => {
    voiceButton.classList.add("recording");
    voiceButton.setAttribute("aria-label", "Detener micrófono");
    setStatus("🎙 Escuchando… hablá ahora.", "info");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    if (messageInput) messageInput.value = transcript;
    sendMessage(transcript, "voice");
  };

  recognition.onerror = (event) => {
    const msgs = {
      "no-speech":   "No detecté voz. Intentá hablar más cerca del micrófono.",
      "not-allowed": "El micrófono fue bloqueado. Permitilo en la configuración del navegador.",
      "network":     "Error de red durante el reconocimiento de voz.",
    };
    setStatus(msgs[event.error] ?? "Error al procesar el audio. Intentá de nuevo.", "error");
  };

  recognition.onend = () => {
    recognition = null;
    voiceButton.classList.remove("recording");
    voiceButton.setAttribute("aria-label", "Activar micrófono");
    setStatus("");
  };

  recognition.start();
});

/* ─── New Chat ───────────────────────────────────────────────────── */
newChatBtn?.addEventListener("click", () => {
  if (confirm("¿Empezar una nueva consulta y borrar el chat actual?")) {
    localStorage.removeItem("conversationId");
    location.reload();
  }
});

/* ─── Initial Greeting ───────────────────────────────────────────── */
addMessage(
  "assistant",
  "¡Hola! 👋 Soy el asistente virtual del consultorio.\n\n" +
  "Podés pedirme turnos para cardiología, clínica, pediatría y más. " +
  "¿Con qué especialidad o médico querés consultar?"
);
