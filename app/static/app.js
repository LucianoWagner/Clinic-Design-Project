/* ===================================================================
   Consultorio — Chat Frontend v4
   Incluye: modo texto (REST) + modo llamada de voz (WebSocket streaming)
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
const callBtn         = $("callBtn");
const callBtnLabel    = $("callBtnLabel");
const callStatus      = $("callStatus");
const headerSubtitle  = $("headerSubtitle");

const criticalEls = { messagesEl, chatForm, messageInput };
for (const [name, el] of Object.entries(criticalEls)) {
  if (!el) console.error(`[Consultorio] Elemento faltante: #${name}`);
}

/* ─── App State ─────────────────────────────────────────────────── */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition    = null;  // STT de un solo turno (modo texto)
let isLoading      = false;
let conversationId = localStorage.getItem("conversationId");

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
  if (variant === "error")     statusBar.classList.add("text-red-400");
  else if (variant === "info") statusBar.classList.add("text-cyan-400");
  else                         statusBar.classList.add("text-slate-500");
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

/* ─── TTS (modo texto, respuesta completa) ───────────────────────── */
function speak(text) {
  if (!ttsToggle?.checked || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "es-AR";
  window.speechSynthesis.speak(u);
}

/* ─── API Helpers ────────────────────────────────────────────────── */
async function ensureConversation() {
  if (conversationId) return conversationId;
  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: "web_chat" }),
  });
  if (!res.ok) throw new Error(`No se pudo iniciar la conversación (${res.status})`);
  const data = await res.json();
  conversationId = String(data.id);
  localStorage.setItem("conversationId", conversationId);
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
    const id  = await ensureConversation();
    const res = await fetch(`/api/conversations/${id}/messages`, {
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

/* ─── One-shot Voice (modo texto) ────────────────────────────────── */
voiceButton?.addEventListener("click", () => {
  if (VoiceCall.isActive) return; // La llamada maneja el STT
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
    localStorage.removeItem("conversationId");
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
  let ws           = null;
  let active       = false;
  let botSpeaking  = false;  // true mientras el TTS habla → speakBtn bloqueado
  let listening    = false;  // true mientras el STT está activo
  let speechBuffer = "";     // buffer de tokens para sentence chunking
  let streamBubble = null;   // burbuja DOM que se llena con tokens del stream
  let callRecog    = null;   // instancia SpeechRecognition

  /* DOM extra para el panel de llamada */
  const chatFormEl  = $("chatForm");
  const callPanelEl = $("callPanel");
  const speakBtnEl  = $("speakBtn");
  const speakLblEl  = $("speakBtnLabel");

  /* Etiquetas amigables para tool events */
  const TOOL_LABELS = {
    search_availability:        "Buscando disponibilidad…",
    identify_or_create_patient: "Registrando paciente…",
    hold_slot:                  "Reservando turno…",
    confirm_appointment:        "Confirmando turno…",
  };

  /* ── speakBtn state machine ────────────────────────────────────── */
  // Estados: "waiting" | "ready" | "listening"
  function _setSpeakState(state) {
    if (!speakBtnEl || !speakLblEl) return;
    speakBtnEl.disabled = (state !== "ready");

    const styles = {
      waiting:   "text-slate-500 border-slate-700 bg-slate-900",
      ready:     "text-emerald-400 border-emerald-600 bg-emerald-900/30 hover:bg-emerald-900/50 cursor-pointer",
      listening: "text-red-400 border-red-600 bg-red-900/30 animate-pulse",
    };
    // Reset classes
    speakBtnEl.className = speakBtnEl.className.replace(
      /text-\w+-\d+\s+border-\w+-\d+\s+bg-\w+-\d+\/?\d*(?:\s+hover:\S+)?(?:\s+cursor-pointer)?(?:\s+animate-pulse)?/g, ""
    );
    speakBtnEl.className += " " + styles[state];

    const labels = {
      waiting:   "Esperando…",
      ready:     "Hablar",
      listening: "Escuchando…",
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
    callRecog.lang           = "es-AR";
    callRecog.interimResults = false;
    callRecog.continuous     = false;

    callRecog.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      if (transcript && active) _sendUserMessage(transcript);
    };

    callRecog.onerror = (e) => {
      listening = false;
      _setSpeakState("ready");
      if (e.error !== "no-speech" && e.error !== "aborted") {
        setStatus(`Micrófono: ${e.error}`, "error");
      }
    };

    callRecog.onend = () => {
      callRecog = null;
      listening = false;
      // Solo volver a "ready" si no estamos esperando respuesta del bot
      if (active && !botSpeaking && !streamBubble) {
        _setSpeakState("ready");
        setStatus("Tu turno — presioná Hablar.", "info");
      }
    };

    callRecog.start();
    listening = true;
    _setSpeakState("listening");
    setStatus("🎙 Escuchando… hablá ahora.", "info");
  }

  function _stopListening() {
    if (callRecog) {
      callRecog.onend = null;
      callRecog.stop();
      callRecog = null;
    }
    listening = false;
  }

  /* ── TTS con sentence chunking ────────────────────────────────── */
  function _processToken(token) {
    speechBuffer += token;
    const sentenceRegex = /[^.!?\n]+[.!?\n]+/g;
    (speechBuffer.match(sentenceRegex) || []).forEach(s => _speakSentence(s.trim()));
    speechBuffer = speechBuffer.replace(sentenceRegex, "");
  }

  function _flushBuffer() {
    if (speechBuffer.trim()) { _speakSentence(speechBuffer.trim()); speechBuffer = ""; }
  }

  // Mantener referencia global para evitar que el garbage collector mate el utterance antes del onend (Chrome bug)
  window._ttsUtterances = window._ttsUtterances || [];

  function _speakSentence(text) {
    if (!text || !window.speechSynthesis) return;
    botSpeaking = true;
    _stopListening();
    _setSpeakState("waiting");
    setStatus("💬 Asistente hablando…", "info");

    const u = new SpeechSynthesisUtterance(text);
    u.lang  = "es-AR";
    u.rate  = 1.05;
    
    window._ttsUtterances.push(u);

    u.onend = () => {
      window._ttsUtterances = window._ttsUtterances.filter(utt => utt !== u);
      _onBotSentenceDone();
    };
    
    // Timeout de seguridad en caso de que el TTS se congele (ej. texto impronunciable)
    // Asumimos que nadie habla más de 100ms por caracter + 3 segundos de buffer
    const maxDuration = (text.length * 100) + 3000;
    setTimeout(() => {
      if (window._ttsUtterances.includes(u)) {
        console.warn("[TTS] onend timeout trigger");
        window._ttsUtterances = window._ttsUtterances.filter(utt => utt !== u);
        _onBotSentenceDone();
      }
    }, maxDuration);

    window.speechSynthesis.speak(u);
  }

  function _onBotSentenceDone() {
    // Solo habilitar el turno del usuario si la cola de TTS está vacía
    if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
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
        // _onBotSentenceDone habilitará speakBtn cuando el TTS termine
        if (!window.speechSynthesis.speaking) {
          botSpeaking = false;
          _setSpeakState("ready");
          setStatus("Tu turno — presioná Hablar.", "info");
        }
        break;

      case "error":
        hideTyping();
        streamBubble = null;
        addMessage("assistant", data.message || "Error desconocido.");
        setStatus(`⚠ ${data.message}`, "error");
        botSpeaking = false;
        _setSpeakState("ready");
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
    _setSpeakState("waiting"); // Deshabilitar speakBtn hasta que responda el bot
    ws.send(JSON.stringify({ type: "user_message", text, input_mode: "voice" }));
  }

  /* ── Public API ──────────────────────────────────────────────── */
  function start(convId) {
    if (active) return;

    const protocol = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${protocol}://${location.host}/api/ws/conversations/${convId}`);

    ws.onopen = () => {
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
    window.speechSynthesis?.cancel();
    botSpeaking  = false;
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
