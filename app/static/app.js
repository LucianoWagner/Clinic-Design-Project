/* ===================================================================
   Consultorio — Chat Frontend v4
   Incluye: modo texto (REST) + modo llamada de voz (WebSocket streaming)
   =================================================================== */

/* ─── DOM References ─────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

const messagesEl = $("messages");
const chatForm = $("chatForm");
const messageInput = $("messageInput");
const statusBar = $("statusBar");
const voiceButton = $("voiceButton");
const ttsToggle = $("ttsToggle");
const typingIndicator = $("typingIndicator");
const sendButton = $("sendButton");
const newChatBtn = $("newChatBtn");
const callBtn = $("callBtn");
const callBtnLabel = $("callBtnLabel");
const callStatus = $("callStatus");
const headerSubtitle = $("headerSubtitle");
const authView = $("authView");
const appShell = $("appShell");
const loginTab = $("loginTab");
const registerTab = $("registerTab");
const loginForm = $("loginForm");
const registerForm = $("registerForm");
const loginEmail = $("loginEmail");
const loginPassword = $("loginPassword");
const registerFullName = $("registerFullName");
const registerEmail = $("registerEmail");
const registerDocument = $("registerDocument");
const registerPhone = $("registerPhone");
const registerPassword = $("registerPassword");
const authStatus = $("authStatus");
const logoutBtn = $("logoutBtn");
const userNameLabel = $("userNameLabel");
const userEmailLabel = $("userEmailLabel");

const criticalEls = { messagesEl, chatForm, messageInput };
for (const [name, el] of Object.entries(criticalEls)) {
  if (!el) console.error(`[Consultorio] Elemento faltante: #${name}`);
}

/* ─── App State ─────────────────────────────────────────────────── */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;  // STT de un solo turno (modo texto)
let isLoading = false;
let authToken = localStorage.getItem("accessToken");
let currentUser = null;
let conversationId = null;

function _conversationStorageKey() {
  return currentUser ? `conversationId:${currentUser.id}` : "conversationId";
}

function _loadConversationId() {
  conversationId = localStorage.getItem(_conversationStorageKey());
}

function _saveConversationId(id) {
  conversationId = String(id);
  localStorage.setItem(_conversationStorageKey(), conversationId);
}

function _clearConversationId() {
  if (currentUser) localStorage.removeItem(_conversationStorageKey());
  localStorage.removeItem("conversationId");
  conversationId = null;
}

/* ─── Message Bubbles ────────────────────────────────────────────── */
function _createBubble(role) {
  const bubble = document.createElement("div");
  bubble.classList.add(
    "message", "max-w-[78%]", "px-4", "py-3", "rounded-2xl",
    "text-sm", "leading-relaxed", "whitespace-pre-wrap"
  );
  if (role === "user") {
    bubble.classList.add("self-end", "bg-cyan-500/10", "border", "border-cyan-500/25",
      "text-slate-100", "rounded-br-sm");
  } else {
    bubble.classList.add("self-start", "bg-slate-800", "border", "border-slate-700",
      "text-slate-200", "rounded-bl-sm", "border-l-2", "border-l-cyan-500/50");
  }
  return bubble;
}

function addMessage(role, text) {
  if (!messagesEl) return;
  const bubble = _createBubble(role);
  bubble.textContent = text;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* Crea una burbuja vacía para ir llenando con tokens (streaming) */
function createStreamingBubble() {
  const bubble = _createBubble("assistant");
  if (messagesEl) {
    messagesEl.appendChild(bubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
  return bubble;
}

function appendTokenToBubble(bubble, token) {
  if (!bubble) return;
  bubble.textContent += token;
  if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ─── Typing Indicator ──────────────────────────────────────────── */
function showTyping() {
  typingIndicator?.classList.remove("hidden");
  if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
}
function hideTyping() { typingIndicator?.classList.add("hidden"); }

/* ─── Status Bar ─────────────────────────────────────────────────── */
function setStatus(text, variant = "") {
  if (!statusBar) return;
  statusBar.textContent = text;
  statusBar.classList.remove("text-red-400", "text-cyan-400", "text-slate-500");
  if (variant === "error") statusBar.classList.add("text-red-400");
  else if (variant === "info") statusBar.classList.add("text-cyan-400");
  else statusBar.classList.add("text-slate-500");
}

function setAuthStatus(text, variant = "") {
  if (!authStatus) return;
  authStatus.textContent = text;
  authStatus.classList.remove("text-red-400", "text-cyan-400", "text-slate-400");
  if (variant === "error") authStatus.classList.add("text-red-400");
  else if (variant === "info") authStatus.classList.add("text-cyan-400");
  else authStatus.classList.add("text-slate-400");
}

async function authFetch(url, options = {}) {
  if (!authToken) throw new Error("Necesitás iniciar sesión.");
  const headers = {
    ...(options.headers || {}),
    Authorization: `Bearer ${authToken}`,
  };
  return fetch(url, { ...options, headers });
}

function showAuth() {
  appShell?.classList.add("hidden");
  appShell?.classList.remove("flex");
  authView?.classList.remove("hidden");
  authView?.classList.add("flex");
}

function showApp() {
  authView?.classList.add("hidden");
  authView?.classList.remove("flex");
  appShell?.classList.remove("hidden");
  appShell?.classList.add("flex");
  if (userNameLabel) userNameLabel.textContent = currentUser?.full_name ?? "";
  if (userEmailLabel) userEmailLabel.textContent = currentUser?.email ?? "";
}

function setAuthMode(mode) {
  const isLogin = mode === "login";
  loginForm?.classList.toggle("hidden", !isLogin);
  registerForm?.classList.toggle("hidden", isLogin);
  loginTab?.classList.toggle("bg-slate-800", isLogin);
  loginTab?.classList.toggle("text-white", isLogin);
  loginTab?.classList.toggle("text-slate-400", !isLogin);
  registerTab?.classList.toggle("bg-slate-800", !isLogin);
  registerTab?.classList.toggle("text-white", !isLogin);
  registerTab?.classList.toggle("text-slate-400", isLogin);
  setAuthStatus("");
}

function setSession(data) {
  authToken = data.access_token;
  currentUser = data.user;
  localStorage.setItem("accessToken", authToken);
  _loadConversationId();
  showApp();
}

function logout() {
  if (VoiceCall.isActive) VoiceCall.stop();
  _clearConversationId();
  localStorage.removeItem("accessToken");
  authToken = null;
  currentUser = null;
  messagesEl && (messagesEl.innerHTML = "");
  showAuth();
}

async function initAuth() {
  if (!authToken) {
    showAuth();
    return;
  }

  try {
    const res = await authFetch("/api/auth/me");
    if (!res.ok) throw new Error("Sesión expirada.");
    currentUser = await res.json();
    _loadConversationId();
    showApp();
  } catch {
    localStorage.removeItem("accessToken");
    authToken = null;
    currentUser = null;
    showAuth();
  }
}

/* ─── Loading State (modo texto) ─────────────────────────────────── */
function setLoading(loading) {
  isLoading = loading;
  if (messageInput) messageInput.disabled = loading;
  if (!sendButton) return;
  if (loading) {
    sendButton.classList.add("opacity-50", "cursor-not-allowed");
    sendButton.innerHTML = `<svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" d="M12 2a10 10 0 0 1 10 10"/></svg>`;
  } else {
    sendButton.classList.remove("opacity-50", "cursor-not-allowed");
    sendButton.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;
  }
}

/* ─── TTS Helpers (ElevenLabs proxy + Audio queue) ───────────────── */
async function fetchTtsAudioUrl(text) {
  const response = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Error en síntesis de voz");
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

const TextTtsQueue = (() => {
  let queue = [];
  let currentAudio = null;

  function speak(text) {
    if (!ttsToggle?.checked || !text?.trim()) return;
    stop();
    _enqueue(text.trim());
  }

  async function _enqueue(text) {
    try {
      const url = await fetchTtsAudioUrl(text);
      queue.push(url);
      if (!currentAudio) _playNext();
    } catch (err) {
      console.error("[ElevenLabs TTS Error]", err);
      setStatus(`Voz: ${err.message}`, "error");
    }
  }

  function _playNext() {
    if (queue.length === 0) {
      currentAudio = null;
      return;
    }

    const url = queue.shift();
    currentAudio = new Audio(url);
    currentAudio.onended = () => {
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNext();
    };
    currentAudio.onerror = () => {
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNext();
    };
    currentAudio.play().catch((err) => {
      console.warn("[Audio Play Blocked]", err);
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNext();
    });
  }

  function stop() {
    if (currentAudio) {
      currentAudio.pause();
      if (currentAudio.src) URL.revokeObjectURL(currentAudio.src);
      currentAudio = null;
    }
    queue.forEach((url) => URL.revokeObjectURL(url));
    queue = [];
  }

  return { speak, stop };
})();

function speak(text) {
  TextTtsQueue.speak(text);
}

/* ─── API Helpers ────────────────────────────────────────────────── */
async function ensureConversation() {
  if (!currentUser) throw new Error("Necesitás iniciar sesión.");
  if (conversationId) return conversationId;
  const res = await authFetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: "web_chat" }),
  });
  if (!res.ok) throw new Error(`No se pudo iniciar la conversación (${res.status})`);
  const data = await res.json();
  _saveConversationId(data.id);
  return conversationId;
}

/* ─── Send Message via REST (modo texto) ─────────────────────────── */
async function sendMessage(text, inputMode = "text") {
  if (isLoading || VoiceCall.isActive) return;
  const trimmed = text.trim();
  if (!trimmed) return;

  addMessage("user", trimmed);
  if (messageInput) messageInput.value = "";
  setLoading(true);
  showTyping();
  setStatus("El asistente está procesando tu consulta…", "info");

  try {
    const id = await ensureConversation();
    const res = await authFetch(`/api/conversations/${id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed, input_mode: inputMode }),
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

/* ─── Form Submit & Enter Key ────────────────────────────────────── */
chatForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(messageInput?.value ?? "");
});

messageInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !isLoading) {
    e.preventDefault();
    sendMessage(messageInput.value);
  }
});

loginTab?.addEventListener("click", () => setAuthMode("login"));
registerTab?.addEventListener("click", () => setAuthMode("register"));
logoutBtn?.addEventListener("click", logout);

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthStatus("Ingresando…", "info");
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: loginEmail?.value ?? "",
        password: loginPassword?.value ?? "",
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "No se pudo iniciar sesión.");
    setSession(data);
    setAuthStatus("");
  } catch (err) {
    setAuthStatus(err.message, "error");
  }
});

registerForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthStatus("Creando cuenta…", "info");
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: registerFullName?.value ?? "",
        email: registerEmail?.value ?? "",
        document_number: registerDocument?.value ?? "",
        phone: registerPhone?.value ?? "",
        password: registerPassword?.value ?? "",
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "No se pudo crear la cuenta.");
    setSession(data);
    setAuthStatus("");
  } catch (err) {
    setAuthStatus(err.message, "error");
  }
});

/* ─── One-shot Voice (modo texto) ────────────────────────────────── */
voiceButton?.addEventListener("click", () => {
  if (VoiceCall.isActive) return; // La llamada maneja el STT
  if (!SpeechRecognition) {
    setStatus("Tu navegador no soporta reconocimiento de voz. Usá Chrome o Edge.", "error");
    return;
  }
  if (recognition) { recognition.stop(); return; }

  recognition = new SpeechRecognition();
  recognition.lang = "es-AR";
  recognition.interimResults = false;
  recognition.continuous = false;

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
      "no-speech": "No detecté voz. Intentá hablar más cerca del micrófono.",
      "not-allowed": "El micrófono fue bloqueado. Permitilo en la configuración del navegador.",
      "network": "Error de red durante el reconocimiento de voz.",
    };
    setStatus(msgs[event.error] ?? "Error al procesar el audio.", "error");
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
  if (VoiceCall.isActive) VoiceCall.stop();
  if (confirm("¿Empezar una nueva consulta y borrar el chat actual?")) {
    _clearConversationId();
    location.reload();
  }
});

/* ===================================================================
   VOICE CALL MANAGER  (push-to-talk edition)
   Patrón IIFE: solo expone start(), stop(), isActive.
   El usuario controla cuándo hablar con el botón #speakBtn.
   El STT nunca se auto-activa para evitar captar ruido de fondo.
   =================================================================== */
const VoiceCall = (() => {
  /* ── Private state ─────────────────────────────────────────────── */
  let ws = null;
  let active = false;
  let botSpeaking = false;  // true mientras el TTS habla → speakBtn bloqueado
  let listening = false;  // true mientras el STT está activo
  let speechBuffer = "";     // buffer de tokens para sentence chunking
  let streamBubble = null;   // burbuja DOM que se llena con tokens del stream
  let callRecog = null;   // instancia SpeechRecognition
  let awaitingBotResponse = false;

  /* DOM extra para el panel de llamada */
  const chatFormEl = $("chatForm");
  const callPanelEl = $("callPanel");
  const speakBtnEl = $("speakBtn");
  const speakLblEl = $("speakBtnLabel");

  /* Etiquetas amigables para tool events */
  const TOOL_LABELS = {
    search_availability: "Buscando disponibilidad…",
    hold_slot: "Reservando turno…",
    confirm_appointment: "Confirmando turno…",
  };

  /* ── speakBtn state machine ────────────────────────────────────── */
  // Estados: "waiting" | "ready" | "listening"
  function _setSpeakState(state) {
    if (!speakBtnEl || !speakLblEl) return;
    speakBtnEl.disabled = (state === "waiting");

    const styles = {
      waiting: "text-slate-500 border-slate-700 bg-slate-900",
      ready: "text-emerald-400 border-emerald-600 bg-emerald-900/30 hover:bg-emerald-900/50 cursor-pointer",
      listening: "text-red-400 border-red-600 bg-red-900/30 animate-pulse",
    };
    // Reset classes
    speakBtnEl.className = speakBtnEl.className.replace(
      /text-\w+-\d+\s+border-\w+-\d+\s+bg-\w+-\d+\/?\d*(?:\s+hover:\S+)?(?:\s+cursor-pointer)?(?:\s+animate-pulse)?/g, ""
    );
    speakBtnEl.className += " " + styles[state];

    const labels = {
      waiting: "Esperando…",
      ready: "Hablar",
      listening: "Detener",
    };
    speakLblEl.textContent = labels[state];
    speakBtnEl.setAttribute("aria-label", state === "listening" ? "Detener" : "Hablar ahora");
  }

  /* ── Call-mode UI (header + panels) ───────────────────────────── */
  function _setCallUI(isActive) {
    if (!callBtn || !callBtnLabel || !callStatus || !headerSubtitle) return;

    if (isActive) {
      // Header: botón "Colgar" rojo + indicador de llamada
      callBtnLabel.textContent = "Colgar";
      callBtn.title = "Colgar llamada";
      callBtn.setAttribute("aria-label", "Colgar llamada");
      callBtn.classList.replace("text-emerald-400", "text-red-400");
      callBtn.classList.replace("border-emerald-700\\/50", "border-red-700/50");
      callBtn.classList.replace("bg-emerald-900\\/20", "bg-red-900/20");

      callStatus.classList.remove("hidden");
      headerSubtitle.classList.add("hidden");

      // Panel: mostrar call panel, ocultar chat form
      chatFormEl?.classList.add("hidden");
      callPanelEl?.classList.remove("hidden");
      callPanelEl?.classList.add("flex");
      _setSpeakState("waiting");

      if (voiceButton) voiceButton.disabled = true;
    } else {
      // Restaurar header
      callBtnLabel.textContent = "Llamar";
      callBtn.title = "Iniciar llamada de voz con el asistente";
      callBtn.setAttribute("aria-label", "Iniciar llamada");
      callBtn.classList.replace("text-red-400", "text-emerald-400");
      callBtn.classList.replace("border-red-700\\/50", "border-emerald-700/50");
      callBtn.classList.replace("bg-red-900\\/20", "bg-emerald-900/20");

      callStatus.classList.add("hidden");
      headerSubtitle.classList.remove("hidden");

      // Panel: restaurar chat form
      callPanelEl?.classList.add("hidden");
      callPanelEl?.classList.remove("flex");
      chatFormEl?.classList.remove("hidden");

      if (voiceButton) voiceButton.disabled = false;
    }
  }

  /* ── STT (solo activado manualmente por speakBtn) ─────────────── */
  function _startListening() {
    if (!SpeechRecognition || !active || botSpeaking || listening) return;

    callRecog = new SpeechRecognition();
    callRecog.lang = "es-AR";
    callRecog.interimResults = false;
    callRecog.continuous = false;

    callRecog.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      if (transcript && active) _sendUserMessage(transcript);
    };

    callRecog.onerror = (e) => {
      listening = false;
      if (e.error !== "no-speech" && e.error !== "aborted") {
        setStatus(`Micrófono: ${e.error}`, "error");
        _setSpeakState("ready");
        return;
      }
      _setSpeakState("ready");
      setStatus("No detecté voz. Presioná Hablar e intentá de nuevo.", "info");
    };

    callRecog.onend = () => {
      callRecog = null;
      listening = false;
      // Solo volver a "ready" si no estamos esperando respuesta del bot
      if (active && !botSpeaking && !streamBubble && !awaitingBotResponse) {
        _setSpeakState("ready");
        setStatus("Tu turno — presioná Hablar.", "info");
      }
    };

    try {
      callRecog.start();
      listening = true;
      _setSpeakState("listening");
      setStatus("🎙 Escuchando… hablá ahora.", "info");
    } catch (err) {
      callRecog = null;
      listening = false;
      _setSpeakState("ready");
      setStatus("No se pudo iniciar el micrófono. Revisá permisos del navegador.", "error");
      console.error("[SpeechRecognition start error]", err);
    }
  }

  function _stopListening() {
    if (callRecog) {
      callRecog.stop();
    }
    listening = false;
  }

  /* ── TTS con ElevenLabs (Cola de Audio) ────────────────────────── */
  let audioQueue = [];
  let isPlayingAudio = false;
  let currentAudio = null;

  function _processToken(token) {
    speechBuffer += token;
    const sentenceRegex = /[^.!?\n]+[.!?\n]+/g;
    (speechBuffer.match(sentenceRegex) || []).forEach(s => _speakSentence(s.trim()));
    speechBuffer = speechBuffer.replace(sentenceRegex, "");
  }

  function _flushBuffer() {
    if (speechBuffer.trim()) {
      _speakSentence(speechBuffer.trim());
      speechBuffer = "";
    }
  }

  async function _speakSentence(text) {
    if (!text) return;

    // Bloquear UI mientras el bot "habla" o prepara el audio
    botSpeaking = true;
    _stopListening();
    _setSpeakState("waiting");
    setStatus("💬 Asistente hablando…", "info");

    try {
      const url = await fetchTtsAudioUrl(text);
      audioQueue.push(url);

      if (!isPlayingAudio) {
        _playNextInQueue();
      }
    } catch (err) {
      console.error("[ElevenLabs TTS Error]", err);
      // Si falla ElevenLabs, liberamos el turno para no trabar la UI
      _checkIfFinished();
    }
  }

  function _playNextInQueue() {
    if (audioQueue.length === 0) {
      isPlayingAudio = false;
      _checkIfFinished();
      return;
    }

    isPlayingAudio = true;
    const url = audioQueue.shift();
    currentAudio = new Audio(url);

    currentAudio.onended = () => {
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNextInQueue();
    };

    currentAudio.onerror = () => {
      console.error("[Audio Playback Error]");
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNextInQueue();
    };

    currentAudio.play().catch(e => {
      console.warn("[Audio Play Blocked] Necesita interacción previa:", e);
      URL.revokeObjectURL(url);
      currentAudio = null;
      _playNextInQueue();
    });
  }

  function _checkIfFinished() {
    // El turno termina si:
    // 1. No hay audios reproduciéndose ni en cola
    // 2. El backend ya terminó de mandar tokens (streamBubble == null)
    if (!isPlayingAudio && audioQueue.length === 0 && !streamBubble) {
      botSpeaking = false;
      if (active) {
        _setSpeakState("ready");
        setStatus("Tu turno — presioná Hablar.", "info");
      }
    }
  }

  /* ── WebSocket message routing ─────────────────────────────────── */
  function _onWsMessage(event) {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }

    switch (data.type) {

      case "token":
        if (!streamBubble) {
          hideTyping();
          streamBubble = createStreamingBubble();
        }
        appendTokenToBubble(streamBubble, data.text);
        _processToken(data.text);
        break;

      case "tool_start":
        // Mostrar qué herramienta está corriendo (ej: "Buscando disponibilidad…")
        setStatus(TOOL_LABELS[data.name] || "Procesando…", "info");
        if (!streamBubble) showTyping();
        break;

      case "tool_end":
        break; // El próximo token o done actualizarán el estado

      case "done":
        hideTyping();
        _flushBuffer();
        streamBubble = null;
        awaitingBotResponse = false;
        _checkIfFinished();
        break;

      case "error":
        hideTyping();
        streamBubble = null;
        awaitingBotResponse = false;
        addMessage("assistant", data.message || "Error desconocido.");
        setStatus(`⚠ ${data.message}`, "error");
        _checkIfFinished();
        break;
    }
  }

  /* ── Enviar mensaje del usuario ────────────────────────────────── */
  function _sendUserMessage(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    addMessage("user", text);
    showTyping();
    setStatus("Procesando…", "info");
    streamBubble = null;
    awaitingBotResponse = true;
    _setSpeakState("waiting"); // Deshabilitar speakBtn hasta que responda el bot
    ws.send(JSON.stringify({ type: "user_message", text, input_mode: "voice" }));
  }

  /* ── Public API ──────────────────────────────────────────────── */
  function start(convId) {
    if (active) return;

    const protocol = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${protocol}://${location.host}/api/ws/conversations/${convId}`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", token: authToken }));
      active = true;
      _setCallUI(true);
      setStatus("Llamada conectada. Presioná Hablar cuando quieras.", "info");
      // NO auto-activamos el STT — el usuario presiona cuando quiere hablar
      setTimeout(() => { if (active) _setSpeakState("ready"); }, 500);
    };

    ws.onmessage = _onWsMessage;

    ws.onerror = () => {
      setStatus("Error de conexión en la llamada.", "error");
      stop();
    };

    ws.onclose = () => {
      if (active) stop();
    };
  }

  function stop() {
    active = false;
    _stopListening();
    if (currentAudio) {
      currentAudio.pause();
      if (currentAudio.src) URL.revokeObjectURL(currentAudio.src);
      currentAudio = null;
    }
    audioQueue.forEach((url) => URL.revokeObjectURL(url));
    audioQueue = [];
    isPlayingAudio = false;
    botSpeaking = false;
    awaitingBotResponse = false;
    speechBuffer = "";
    streamBubble = null;

    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    ws = null;

    _setCallUI(false);
    setStatus("");
  }

  /* speakBtn toggle: presionar activa/desactiva el STT manualmente */
  speakBtnEl?.addEventListener("click", () => {
    if (!active) return;
    if (listening) {
      // Si ya está escuchando → parar (el usuario cambió de idea)
      _stopListening();
      _setSpeakState("ready");
      setStatus("Tu turno — presioná Hablar.", "info");
    } else {
      _startListening();
    }
  });

  return {
    start,
    stop,
    get isActive() { return active; },
  };
})();

/* ─── Call Button ────────────────────────────────────────────────── */
callBtn?.addEventListener("click", async () => {
  if (VoiceCall.isActive) { VoiceCall.stop(); return; }
  if (!SpeechRecognition) {
    setStatus("Tu navegador no soporta reconocimiento de voz. Usá Chrome o Edge.", "error");
    return;
  }
  try {
    const id = await ensureConversation();
    VoiceCall.start(id);
  } catch (err) {
    setStatus(`No se pudo iniciar la llamada: ${err.message}`, "error");
  }
});

/* ─── Initial Greeting ───────────────────────────────────────────── */
addMessage(
  "assistant",
  "¡Hola! 👋 Soy el asistente virtual del consultorio.\n\n" +
  "Podés escribirme o presionar 📞 Llamar para hablar directamente. " +
  "¿Con qué especialidad o médico querés consultar?"
);

initAuth();
