/* ===================================================================

   Consultorio â€” Chat Frontend v4

   Incluye: modo texto (REST) + modo llamada de voz (WebSocket streaming)

   =================================================================== */



/* â”€â”€â”€ DOM References â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

const sidebarNewChatBtn = $("sidebarNewChatBtn");

const conversationList = $("conversationList");

const conversationEmpty = $("conversationEmpty");



const criticalEls = { messagesEl, chatForm, messageInput };

for (const [name, el] of Object.entries(criticalEls)) {

  if (!el) console.error(`[Consultorio] Elemento faltante: #${name}`);

}



/* â”€â”€â”€ App State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition = null;  // STT de un solo turno (modo texto)

let isLoading = false;

let authToken = localStorage.getItem("accessToken");

let currentUser = null;

let conversationId = null;

let conversations = [];



const INITIAL_GREETING =

  "¡Hola! 👋 Soy el asistente virtual del consultorio.\n\n" +

  "Podés escribirme o presionar 📞 Llamar para hablar directamente. " +

  "¿Con qué especialidad o médico querés consultar?";



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



/* â”€â”€â”€ Message Bubbles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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



function renderInitialGreeting() {

  if (!messagesEl) return;

  messagesEl.innerHTML = "";

  addMessage("assistant", INITIAL_GREETING);

}



function renderMessages(messages) {

  if (!messagesEl) return;

  messagesEl.innerHTML = "";

  if (!messages?.length) {

    renderInitialGreeting();

    return;

  }

  messages.forEach((message) => addMessage(message.role, message.content));

}



function _formatConversationTime(value) {

  if (!value) return "";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });

}



function renderConversationList() {

  if (!conversationList || !conversationEmpty) return;

  conversationList.innerHTML = "";

  conversationEmpty.classList.toggle("hidden", conversations.length > 0);



  conversations.forEach((conversation) => {
    const container = document.createElement("div");
    container.className = "relative group";

    const button = document.createElement("button");
    button.type = "button";
    button.dataset.conversationId = conversation.id;
    const selected = String(conversation.id) === String(conversationId);
    button.className = [
      "w-full text-left rounded-xl border px-3 py-3 transition-colors pr-9",
      selected
        ? "bg-cyan-500/10 border-cyan-600/50 text-slate-100"
        : "bg-slate-800/50 border-slate-700/60 text-slate-300 hover:border-slate-600 hover:bg-slate-800",
    ].join(" ");
    button.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <span class="min-w-0 flex-1 truncate text-sm font-medium">${_escapeHtml(conversation.title || "Nueva consulta")}</span>
        <span class="flex-shrink-0 text-[10px] text-slate-500">${_escapeHtml(_formatConversationTime(conversation.updated_at))}</span>
      </div>
      <p class="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">${_escapeHtml(conversation.preview || "Sin mensajes todavia")}</p>
    `;
    button.addEventListener("click", () => selectConversation(conversation.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "absolute top-2 right-2 p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all";
    deleteBtn.title = "Eliminar conversación";
    deleteBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18"></path>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
      </svg>
    `;
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm("¿Estás seguro de que querés eliminar esta conversación?")) {
        await deleteConversation(conversation.id);
      }
    });

    container.appendChild(button);
    container.appendChild(deleteBtn);
    conversationList.appendChild(container);
  });

}



function _escapeHtml(value) {

  return String(value ?? "")

    .replaceAll("&", "&amp;")

    .replaceAll("<", "&lt;")

    .replaceAll(">", "&gt;")

    .replaceAll('"', "&quot;")

    .replaceAll("'", "&#039;");

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



/* â”€â”€â”€ Typing Indicator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

function showTyping() {

  typingIndicator?.classList.remove("hidden");

  if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;

}

function hideTyping() { typingIndicator?.classList.add("hidden"); }



/* â”€â”€â”€ Status Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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



async function loadConversationList() {

  const res = await authFetch("/api/conversations");

  if (!res.ok) throw new Error(`No se pudo cargar el historial (${res.status})`);

  conversations = await res.json();

  renderConversationList();

  return conversations;

}



async function loadConversationMessages(id) {

  const res = await authFetch(`/api/conversations/${id}/messages`);

  if (!res.ok) throw new Error(`No se pudo cargar la conversacion (${res.status})`);

  const messages = await res.json();

  renderMessages(messages);

}



async function deleteConversation(id) {
  try {
    const res = await authFetch(`/api/conversations/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error("No se pudo eliminar la conversación");
    
    conversations = conversations.filter(c => String(c.id) !== String(id));
    
    if (String(id) === String(conversationId)) {
      _clearConversationId();
      renderInitialGreeting();
    }
    
    renderConversationList();
  } catch (err) {
    console.error(err);
    setStatus("Error al eliminar conversación", "error");
  }
}

async function selectConversation(id) {

  if (VoiceCall.isActive) VoiceCall.stop();

  _saveConversationId(id);

  renderConversationList();

  try {

    await loadConversationMessages(id);

    setStatus("");

  } catch (err) {

    _clearConversationId();

    renderConversationList();

    renderInitialGreeting();

    setStatus(err.message, "error");

  }

}



async function hydrateConversations() {

  await loadConversationList();

  const storedId = conversationId;

  const storedExists = storedId && conversations.some((item) => String(item.id) === String(storedId));

  if (storedExists) {

    await loadConversationMessages(storedId);

    renderConversationList();

  } else {

    _clearConversationId();

    renderConversationList();

    renderInitialGreeting();

  }

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



async function setSession(data) {

  authToken = data.access_token;

  currentUser = data.user;

  localStorage.setItem("accessToken", authToken);

  _loadConversationId();

  showApp();

  await hydrateConversations();

}



function logout() {

  if (VoiceCall.isActive) VoiceCall.stop();

  _clearConversationId();

  localStorage.removeItem("accessToken");

  authToken = null;

  currentUser = null;

  conversations = [];

  renderConversationList();

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

    await hydrateConversations();

  } catch {

    localStorage.removeItem("accessToken");

    authToken = null;

    currentUser = null;

    showAuth();

  }

}



/* â”€â”€â”€ Loading State (modo texto) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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



/* â”€â”€â”€ TTS Helpers (ElevenLabs proxy + Audio queue) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

async function fetchTtsAudioUrl(text, options = {}) {

  const response = await fetch("/api/tts", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify({ text }),

    signal: options.signal,

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



function stopTextTts() {

  TextTtsQueue.stop();

}



/* â”€â”€â”€ API Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

  await loadConversationList();

  return conversationId;

}



/* â”€â”€â”€ Send Message via REST (modo texto) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

async function sendMessage(text, inputMode = "text") {

  if (isLoading || VoiceCall.isActive) return;

  const trimmed = text.trim();

  if (!trimmed) return;



  addMessage("user", trimmed);

  if (messageInput) messageInput.value = "";

  setLoading(true);

  showTyping();

  setStatus("El asistente está procesando tu consultaâ€¦", "info");



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

    await loadConversationList();

    setStatus("");

  } catch (err) {

    hideTyping();

    addMessage("assistant", "Hubo un problema al procesar tu consulta. Por favor intentá de nuevo.");

    setStatus(`âš  ${err.message}`, "error");

    console.error("[Consultorio]", err);

  } finally {

    setLoading(false);

    messageInput?.focus();

  }

}



/* â”€â”€â”€ Form Submit & Enter Key â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

  setAuthStatus("Ingresandoâ€¦", "info");

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

    await setSession(data);

    setAuthStatus("");

  } catch (err) {

    setAuthStatus(err.message, "error");

  }

});



registerForm?.addEventListener("submit", async (e) => {

  e.preventDefault();

  setAuthStatus("Creando cuentaâ€¦", "info");

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

    await setSession(data);

    setAuthStatus("");

  } catch (err) {

    setAuthStatus(err.message, "error");

  }

});



/* â”€â”€â”€ One-shot Voice (modo texto) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

    setStatus("ðŸŽ™ Escuchandoâ€¦ hablá ahora.", "info");

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



/* â”€â”€â”€ New Chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

newChatBtn?.addEventListener("click", () => {

  if (VoiceCall.isActive) VoiceCall.stop();

  _clearConversationId();

  renderConversationList();

  renderInitialGreeting();

  messageInput?.focus();

  setStatus("");

});

sidebarNewChatBtn?.addEventListener("click", () => newChatBtn?.click());



/* ===================================================================

   VOICE CALL MANAGER  (push-to-talk edition)

   Patrón IIFE: solo expone start(), stop(), isActive.

   El usuario controla cuándo hablar con el botón #speakBtn.

   El STT nunca se auto-activa para evitar captar ruido de fondo.

   =================================================================== */

const VoiceCall = (() => {

  /* â”€â”€ Private state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  let ws = null;

  let active = false;

  let botSpeaking = false;  // true mientras el TTS habla â†’ speakBtn bloqueado

  let listening = false;  // true mientras el STT está activo

  let speechBuffer = "";     // buffer de tokens para sentence chunking

  let streamBubble = null;   // burbuja DOM que se llena con tokens del stream

  let callRecog = null;   // instancia SpeechRecognition

  let awaitingBotResponse = false;

  let callTranscript = "";
  let callMessageSent = false;
  let audioRunId = 0;



  /* DOM extra para el panel de llamada */

  const chatFormEl = $("chatForm");

  const callPanelEl = $("callPanel");

  const speakBtnEl = $("speakBtn");

  const speakLblEl = $("speakBtnLabel");



  /* Etiquetas amigables para tool events */

  const TOOL_LABELS = {

    search_availability: "Buscando disponibilidadâ€¦",

    hold_slot: "Reservando turnoâ€¦",

    confirm_appointment: "Confirmando turnoâ€¦",

  };



  /* â”€â”€ speakBtn state machine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

      waiting: "Esperandoâ€¦",

      ready: "Hablar",

      listening: "Detener",

    };

    speakLblEl.textContent = labels[state];

    speakBtnEl.setAttribute("aria-label", state === "listening" ? "Detener" : "Hablar ahora");

  }



  /* â”€â”€ Call-mode UI (header + panels) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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



  /* â”€â”€ STT (solo activado manualmente por speakBtn) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  function _startListening() {

    if (!SpeechRecognition || !active || botSpeaking || listening) return;



    callRecog = new SpeechRecognition();

    callRecog.lang = "es-AR";

    callRecog.interimResults = true;

    callRecog.continuous = false;

    callTranscript = "";
    callMessageSent = false;


    callRecog.onresult = (event) => {
      let transcript = "";
      let hasFinalResult = false;
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript;
        hasFinalResult = hasFinalResult || event.results[i].isFinal;
      }
      callTranscript = transcript.trim() || callTranscript;
      if (callTranscript) {
        setStatus(`Escuchando: ${callTranscript}`, "info");
      }
      if (hasFinalResult) {
        _finishListeningWithTranscript();
      }
    };


    callRecog.onerror = (e) => {

      listening = false;

      if (e.error === "aborted") return;
      if (e.error !== "no-speech") {
        callTranscript = "";
        setStatus(`Micrófono: ${e.error}`, "error");

        _setSpeakState("ready");

        return;

      }

      if (!callTranscript.trim()) {
        _setSpeakState("ready");
        setStatus("No detecté voz. Presioná Hablar e intentá de nuevo.", "info");

      }
    };

    callRecog.onend = () => {
      callRecog = null;
      listening = false;
      if (_finishListeningWithTranscript()) return;
      // Solo volver a "ready" si no estamos esperando respuesta del bot
      if (active && !botSpeaking && !streamBubble && !awaitingBotResponse) {

        _setSpeakState("ready");

        setStatus("Tu turno â€” presioná Hablar.", "info");

      }

    };



    try {

      callRecog.start();

      listening = true;

      _setSpeakState("listening");

      setStatus("ðŸŽ™ Escuchandoâ€¦ hablá ahora.", "info");

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

  function _finishListeningWithTranscript() {
    if (callMessageSent) return false;

    const transcript = callTranscript.trim();
    if (!transcript || !active || awaitingBotResponse) return false;

    callMessageSent = true;
    callTranscript = "";
    _stopListening();
    _sendUserMessage(transcript);
    return true;
  }


  /* â”€â”€ TTS con ElevenLabs (Cola de Audio) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  let audioQueue = [];

  let isPlayingAudio = false;

  let currentAudio = null;

  let ttsTextQueue = [];

  let isGeneratingAudio = false;

  let ttsDrainTimer = null;

  const ttsAbortControllers = new Set();



  function _abortPendingTtsRequests() {

    if (ttsDrainTimer) {

      clearTimeout(ttsDrainTimer);

      ttsDrainTimer = null;

    }

    for (const controller of ttsAbortControllers) {

      controller.abort();

    }

    ttsAbortControllers.clear();

    ttsTextQueue = [];

    isGeneratingAudio = false;

  }



  // Flag que bloquea el TTS cuando el agente entra en modo lista/datos estructurados
  let _ttsListMode = false;

  // Acumula TODOS los tokens de la respuesta actual sin vaciarse nunca.
  // Necesario porque speechBuffer se vacía con cada oración detectada,
  // lo que hace que el \n previo a "1." desaparezca y el patrón no se detecte.
  let _fullResponseBuffer = "";

  // Detecta contenido estructurado: listas numeradas, con guión, doble salto de línea o negrita de sección
  const LIST_PATTERN = /(\n[-*•]\s|\n\d+[.)]\s|\n\s*\n|\*\*[^*]+\*\*.*\n)/;

  function _processToken(token) {
    _fullResponseBuffer += token; // acumulador permanente (no se vacía con sentence regex)
    speechBuffer += token;

    // Si ya detectamos lista, descartar el resto para TTS
    if (_ttsListMode) return;

    // Revisar el buffer COMPLETO (no el speechBuffer que puede estar vacío)
    if (LIST_PATTERN.test(_fullResponseBuffer)) {
      _ttsListMode = true;
      // Hablar solo lo que queda en speechBuffer antes del item de lista (si es conversacional)
      const pre = speechBuffer.trim();
      if (pre && pre.length > 10 && !/^\d+[.)]/.test(pre)) {
        _queueSpeechText(pre);
      }
      speechBuffer = "";
      return;
    }

    const sentenceRegex = /[^.!?\n]+[.!?\n]+/g;
    (speechBuffer.match(sentenceRegex) || [])
      // Ignorar fragmentos muy cortos — suelen ser prefijos de lista como "1." o "2."
      .filter(s => s.trim().length > 8 && !/^\s*\d+[.)]\s/.test(s.trim()))
      .forEach(s => _queueSpeechText(s.trim()));
    speechBuffer = speechBuffer.replace(sentenceRegex, "");
  }



  function _flushBuffer() {

    if (speechBuffer.trim()) {

      _queueSpeechText(speechBuffer.trim());

      speechBuffer = "";

    }

  }



  function _queueSpeechText(text) {

    if (!text) return;

    botSpeaking = true;

    _stopListening();

    _setSpeakState("waiting");

    setStatus("Asistente hablando...", "info");

    ttsTextQueue.push(text);

    _scheduleTtsDrain();

  }



  function _scheduleTtsDrain() {

    if (isGeneratingAudio || ttsDrainTimer) return;

    ttsDrainTimer = setTimeout(() => {

      ttsDrainTimer = null;

      _drainTtsTextQueue();

    }, 250);

  }



  async function _drainTtsTextQueue() {

    if (isGeneratingAudio) return;

    isGeneratingAudio = true;

    const runId = audioRunId;



    try {

      while (active && runId === audioRunId && ttsTextQueue.length > 0) {

        const text = _nextTtsBatch();

        const controller = new AbortController();

        ttsAbortControllers.add(controller);



        try {

          const url = await fetchTtsAudioUrl(text, { signal: controller.signal });

          if (!active || runId !== audioRunId) {

            URL.revokeObjectURL(url);

            return;

          }

          audioQueue.push(url);

          if (!isPlayingAudio) _playNextInQueue();

        } catch (err) {

          if (err.name === "AbortError") return;

          console.error("[ElevenLabs TTS Error]", err);

        } finally {

          ttsAbortControllers.delete(controller);

        }

      }

    } finally {

      isGeneratingAudio = false;

      if (active && ttsTextQueue.length > 0) _scheduleTtsDrain();

      _checkIfFinished();

    }

  }



  function _nextTtsBatch() {
    let text = ttsTextQueue.shift() || "";
    while (ttsTextQueue.length > 0) {
      const next = ttsTextQueue[0];

      const combined = `${text} ${next}`.trim();

      if (text.length >= 220 || combined.length > 450) break;

      text = combined;

      ttsTextQueue.shift();

    }
    return text;
  }

  function _playNextInQueue() {
    if (!active) {

      isPlayingAudio = false;

      return;

    }

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

    if (

      !isGeneratingAudio &&

      !isPlayingAudio &&

      audioQueue.length === 0 &&

      ttsTextQueue.length === 0 &&

      !streamBubble

    ) {

      botSpeaking = false;

      if (active) {

        _setSpeakState("ready");

        setStatus("Tu turno â€” presioná Hablar.", "info");

      }

    }

  }



  /* â”€â”€ WebSocket message routing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  function _onWsMessage(event) {

    let data;

    try { data = JSON.parse(event.data); } catch { return; }



    switch (data.type) {



      case "token":
        // Solo actualizar el chat bubble — el TTS se maneja via tts_text
        if (!streamBubble) {
          hideTyping();
          streamBubble = createStreamingBubble();
        }
        appendTokenToBubble(streamBubble, data.text);
        break;

      case "tts_text":
        // Texto resumido enviado por el backend para síntesis de voz.
        // Se recibe una vez, sobre el texto completo ya procesado (más fiable que tokens).
        if (data.text) _queueSpeechText(data.text);
        break;



      case "tool_start":

        // Mostrar qué herramienta está corriendo (ej: "Buscando disponibilidadâ€¦")

        setStatus(TOOL_LABELS[data.name] || "Procesandoâ€¦", "info");

        if (!streamBubble) showTyping();

        break;



      case "tool_end":

        break; // El próximo token o done actualizarán el estado



      case "done":
        hideTyping();
        streamBubble = null;
        awaitingBotResponse = false;
        loadConversationList().catch((err) => console.error("[Conversation List]", err));
        _checkIfFinished();
        break;



      case "error":

        hideTyping();

        streamBubble = null;

        awaitingBotResponse = false;

        addMessage("assistant", data.message || "Error desconocido.");

        setStatus(`âš  ${data.message}`, "error");

        _checkIfFinished();

        break;

    }

  }



  /* â”€â”€ Enviar mensaje del usuario â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  function _sendUserMessage(text) {
    const trimmedText = text.trim();
    if (!trimmedText) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setStatus("La llamada no esta conectada. Volve a iniciarla.", "error");
      _setSpeakState("ready");
      return;
    }
    addMessage("user", trimmedText);
    showTyping();

    setStatus("Procesandoâ€¦", "info");

    streamBubble = null;

    awaitingBotResponse = true;
    _ttsListMode = false;          // ← resetear barrera TTS para el nuevo turno
    _fullResponseBuffer = "";      // ← resetear acumulador de detección de listas
    _setSpeakState("waiting"); // Deshabilitar speakBtn hasta que responda el bot

    ws.send(JSON.stringify({ type: "user_message", text: trimmedText, input_mode: "voice" }));
  }



  /* â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

  function start(convId) {

    if (active) return;



    const protocol = location.protocol === "https:" ? "wss" : "ws";

    ws = new WebSocket(`${protocol}://${location.host}/api/ws/conversations/${convId}`);



    ws.onopen = () => {

      ws.send(JSON.stringify({ type: "auth", token: authToken }));

      active = true;

      _setCallUI(true);

      setStatus("Llamada conectada. Presioná Hablar cuando quieras.", "info");

      // NO auto-activamos el STT â€” el usuario presiona cuando quiere hablar

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

    audioRunId += 1;

    _stopListening();

    _abortPendingTtsRequests();

    stopTextTts();

    if (ttsToggle) ttsToggle.checked = false;

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
    callTranscript = "";
    callMessageSent = false;
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

      // Si ya está escuchando â†’ parar (el usuario cambió de idea)

      _stopListening();

      _setSpeakState("ready");

      setStatus("Tu turno â€” presioná Hablar.", "info");

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



/* â”€â”€â”€ Call Button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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



/* â”€â”€â”€ Initial Greeting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

addMessage(

  "assistant",

  "¡Hola! 👋 Soy el asistente virtual del consultorio.\n\n" +

  "Podés escribirme o presionar 📞 Llamar para hablar directamente. " +

  "¿Con qué especialidad o médico querés consultar?"

);



initAuth();

