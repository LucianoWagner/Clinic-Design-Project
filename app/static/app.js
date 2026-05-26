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



function parseApiDate(dateStr) {
  if (!dateStr) return null;
  if (dateStr instanceof Date) return dateStr;
  return new Date(dateStr);
}

function _formatConversationTime(value) {

  if (!value) return "";

  const date = parseApiDate(value);

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

  const doctorShell = $("doctorShell");
  if (currentUser?.role === "doctor") {
    appShell?.classList.add("hidden");
    appShell?.classList.remove("flex");
    doctorShell?.classList.remove("hidden");
    doctorShell?.classList.add("flex");
    doctorPortal.init();
  } else {
    doctorShell?.classList.add("hidden");
    doctorShell?.classList.remove("flex");
  }

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
  const doctorShell = $("doctorShell");
  doctorShell?.classList.add("hidden");
  doctorShell?.classList.remove("flex");

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



/* ─── Appointments View Logic ────────────────────────────────────────────── */

const userDropdownContainer = $("userDropdownContainer");
const userDropdownBtn = $("userDropdownBtn");
const userDropdownMenu = $("userDropdownMenu");
const viewAppointmentsBtn = $("viewAppointmentsBtn");
const appointmentsView = $("appointmentsView");
const backToChatBtn = $("backToChatBtn");
const appointmentsList = $("appointmentsList");
const appointmentFilters = document.querySelectorAll(".appointment-filter");
const chatComposerArea = $("chatComposerArea");

let userAppointments = [];
let currentAppointmentFilter = 'all';

userDropdownBtn?.addEventListener("click", () => {
  userDropdownMenu?.classList.toggle("hidden");
});

document.addEventListener("click", (e) => {
  if (userDropdownContainer && !userDropdownContainer.contains(e.target)) {
    userDropdownMenu?.classList.add("hidden");
  }
});

function showAppointmentsView() {
  userDropdownMenu?.classList.add("hidden");
  messagesEl?.classList.add("hidden");
  chatComposerArea?.classList.add("hidden");
  appointmentsView?.classList.remove("hidden");
  appointmentsView?.classList.add("flex");
  loadAppointments();
}

function hideAppointmentsView() {
  appointmentsView?.classList.add("hidden");
  appointmentsView?.classList.remove("flex");
  messagesEl?.classList.remove("hidden");
  chatComposerArea?.classList.remove("hidden");
}

viewAppointmentsBtn?.addEventListener("click", showAppointmentsView);
backToChatBtn?.addEventListener("click", hideAppointmentsView);

async function loadAppointments() {
  if (!appointmentsList) return;
  appointmentsList.innerHTML = '<p class="text-slate-400 text-sm">Cargando turnos...</p>';
  try {
    const res = await authFetch("/api/appointments/me");
    if (!res.ok) throw new Error("Error al cargar turnos");
    userAppointments = await res.json();
    renderAppointments();
  } catch (err) {
    appointmentsList.innerHTML = `<p class="text-red-400 text-sm">${err.message}</p>`;
  }
}

function renderAppointments() {
  if (!appointmentsList) return;
  appointmentsList.innerHTML = "";
  const filtered = userAppointments.filter(app => {
    if (currentAppointmentFilter === "all") return true;
    return app.status === currentAppointmentFilter;
  });

  if (filtered.length === 0) {
    appointmentsList.innerHTML = '<p class="text-slate-400 text-sm py-4">No se encontraron turnos.</p>';
    return;
  }

  filtered.forEach(app => {
    const date = parseApiDate(app.starts_at).toLocaleString("es-AR", {
      weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'
    });
    
    let statusColor = "bg-slate-700 text-slate-300";
    let statusLabel = app.status;
    if (app.status === "confirmed") {
        statusColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        statusLabel = "Confirmado";
    } else if (app.status === "cancelled") {
        statusColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
        statusLabel = "Cancelado";
    } else if (app.status === "finished") {
        statusColor = "bg-slate-500/10 text-slate-400 border-slate-500/20";
        statusLabel = "Finalizado";
    }

    const card = document.createElement("div");
    card.className = "p-4 rounded-xl border border-slate-700 bg-slate-800/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4";
    card.innerHTML = `
      <div>
        <p class="font-semibold text-slate-200">${app.doctor_name}</p>
        <p class="text-sm text-cyan-400">${app.specialty_name}</p>
        <div class="flex items-center gap-2 mt-2 text-sm text-slate-400">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          <span class="capitalize">${date}</span>
        </div>
      </div>
      <div class="flex-shrink-0">
        <span class="px-3 py-1 text-xs font-medium border rounded-full ${statusColor}">
          ${statusLabel}
        </span>
      </div>
    `;
    appointmentsList.appendChild(card);
  });
}

appointmentFilters.forEach(btn => {
  btn.addEventListener("click", (e) => {
    appointmentFilters.forEach(b => b.classList.remove("active", "bg-slate-700", "text-white"));
    appointmentFilters.forEach(b => b.classList.add("text-slate-400"));
    
    e.target.classList.remove("text-slate-400");
    e.target.classList.add("active", "bg-slate-700", "text-white");
    
    currentAppointmentFilter = e.target.dataset.filter;
    renderAppointments();
  });
});


// ===================================================================
// Doctor Portal Module
// ===================================================================
const doctorPortal = {
  activeTab: "appointments", // or slots
  appointments: [],
  slots: [],
  currentFilter: "all",
  isInitialized: false,

  init() {
    // Show user info
    const nameLabel = $("doctorNameLabel");
    const emailLabel = $("doctorEmailLabel");
    if (nameLabel) nameLabel.textContent = currentUser?.full_name ?? "Médico";
    if (emailLabel) emailLabel.textContent = currentUser?.email ?? "";

    if (this.isInitialized) {
      this.switchTab(this.activeTab);
      return;
    }

    // Setup tab listeners
    $("doctorTabAppointments")?.addEventListener("click", () => this.switchTab("appointments"));
    $("doctorTabSlots")?.addEventListener("click", () => this.switchTab("slots"));
    $("doctorLogoutBtn")?.addEventListener("click", () => logout());

    // Setup filter listeners
    document.querySelectorAll(".doctor-app-filter").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".doctor-app-filter").forEach(b => {
          b.classList.remove("active", "bg-slate-800", "text-white", "shadow-sm");
          b.classList.add("text-slate-400");
        });
        e.target.classList.remove("text-slate-400");
        e.target.classList.add("active", "bg-slate-800", "text-white", "shadow-sm");
        this.currentFilter = e.target.dataset.filter;
        this.renderAppointments();
      });
    });

    // Setup slot form listener
    $("doctorSlotForm")?.addEventListener("submit", (e) => this.handleSlotSubmit(e));
    $("cancelSlotEditBtn")?.addEventListener("click", () => this.cancelSlotEdit());

    this.isInitialized = true;
    this.switchTab(this.activeTab);
  },

  switchTab(tab) {
    this.activeTab = tab;
    
    // Toggle sidebar class names
    const btnApp = $("doctorTabAppointments");
    const btnSlot = $("doctorTabSlots");
    
    if (tab === "appointments") {
      btnApp?.classList.add("bg-slate-800/80", "text-white");
      btnApp?.classList.remove("text-slate-400", "hover:bg-slate-800/40");
      btnSlot?.classList.remove("bg-slate-800/80", "text-white");
      btnSlot?.classList.add("text-slate-400", "hover:bg-slate-800/40");
      
      $("doctorAppointmentsView")?.classList.remove("hidden");
      $("doctorSlotsView")?.classList.add("hidden");
      
      this.loadAppointments();
    } else {
      btnSlot?.classList.add("bg-slate-800/80", "text-white");
      btnSlot?.classList.remove("text-slate-400", "hover:bg-slate-800/40");
      btnApp?.classList.remove("bg-slate-800/80", "text-white");
      btnApp?.classList.add("text-slate-400", "hover:bg-slate-800/40");
      
      $("doctorSlotsView")?.classList.remove("hidden");
      $("doctorSlotsView")?.classList.add("flex");
      $("doctorAppointmentsView")?.classList.add("hidden");
      
      this.loadSlots();
    }
  },

  async loadAppointments() {
    const listEl = $("doctorAppointmentsList");
    if (listEl) listEl.innerHTML = '<p class="text-slate-400 text-sm p-4 col-span-full">Cargando turnos...</p>';
    
    try {
      const res = await authFetch("/api/doctor/appointments");
      if (!res.ok) throw new Error("Error al obtener los turnos.");
      this.appointments = await res.json();
      this.renderAppointments();
    } catch (err) {
      if (listEl) listEl.innerHTML = `<p class="text-red-400 text-sm p-4 col-span-full">${err.message}</p>`;
    }
  },

  renderAppointments() {
    const listEl = $("doctorAppointmentsList");
    if (!listEl) return;
    listEl.innerHTML = "";

    const filtered = this.appointments.filter(app => {
      if (this.currentFilter === "all") return true;
      return app.status === this.currentFilter;
    });

    if (filtered.length === 0) {
      listEl.innerHTML = '<p class="text-slate-400 text-sm p-4 col-span-full">No se encontraron turnos.</p>';
      return;
    }

    filtered.forEach(app => {
      const startsStr = parseApiDate(app.starts_at).toLocaleString("es-AR", {
        weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'
      });
      
      let statusColor = "bg-slate-700 text-slate-300";
      let statusLabel = app.status;
      if (app.status === "confirmed") {
        statusColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        statusLabel = "Confirmado";
      } else if (app.status === "cancelled") {
        statusColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
        statusLabel = "Cancelado";
      } else if (app.status === "finished") {
        statusColor = "bg-slate-500/10 text-slate-400 border-slate-500/20";
        statusLabel = "Finalizado";
      }

      const card = document.createElement("div");
      card.className = "p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex flex-col justify-between gap-4 hover:border-slate-700 transition animate-msg-in";
      card.innerHTML = `
        <div class="flex justify-between items-start">
          <div>
            <h4 class="font-semibold text-slate-100 text-base">${app.patient_name}</h4>
            <p class="text-xs text-slate-400 mt-0.5">${app.patient_email}</p>
            <div class="flex items-center gap-2 mt-3 text-sm text-slate-300">
              <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
              <span class="capitalize font-medium text-xs sm:text-sm">${startsStr}</span>
            </div>
          </div>
          <span class="px-2.5 py-1 text-xs font-semibold border rounded-lg ${statusColor}">
            ${statusLabel}
          </span>
        </div>
        
        <div class="flex items-center gap-2 pt-3 border-t border-slate-800/60 justify-end">
          <button class="doctor-action-btn px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg hover:text-white transition" data-id="${app.id}" data-action="confirmed" ${app.status === 'confirmed' ? 'disabled' : ''}>
            Confirmar
          </button>
          <button class="doctor-action-btn px-3 py-1.5 text-xs font-medium bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg transition" data-id="${app.id}" data-action="cancelled" ${app.status === 'cancelled' ? 'disabled' : ''}>
            Cancelar
          </button>
          <button class="doctor-action-btn px-3 py-1.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition" data-id="${app.id}" data-action="finished" ${app.status === 'finished' ? 'disabled' : ''}>
            Finalizar
          </button>
        </div>
      `;
      listEl.appendChild(card);
    });

    // Action button listeners
    listEl.querySelectorAll(".doctor-action-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const action = btn.dataset.action;
        this.updateAppointmentStatus(id, action);
      });
    });
  },

  async updateAppointmentStatus(id, status) {
    try {
      const res = await authFetch(`/api/doctor/appointments/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status })
      });
      if (!res.ok) throw new Error("No se pudo actualizar el estado del turno.");
      
      // Update local array
      const updated = await res.json();
      const idx = this.appointments.findIndex(a => String(a.id) === String(id));
      if (idx !== -1) {
        this.appointments[idx] = updated;
      }
      this.renderAppointments();
    } catch (err) {
      alert(err.message);
    }
  },

  async loadSlots() {
    const listEl = $("doctorSlotsList");
    if (listEl) listEl.innerHTML = '<p class="text-slate-400 text-sm p-4">Cargando horarios...</p>';
    
    try {
      const res = await authFetch("/api/doctor/slots");
      if (!res.ok) throw new Error("Error al obtener los horarios.");
      this.slots = await res.json();
      this.renderSlots();
    } catch (err) {
      if (listEl) listEl.innerHTML = `<p class="text-red-400 text-sm p-4">${err.message}</p>`;
    }
  },

  renderSlots() {
    const listEl = $("doctorSlotsList");
    if (!listEl) return;
    listEl.innerHTML = "";

    if (this.slots.length === 0) {
      listEl.innerHTML = '<p class="text-slate-400 text-sm py-4">No hay horarios configurados.</p>';
      return;
    }

    this.slots.forEach(slot => {
      const startsStr = parseApiDate(slot.starts_at).toLocaleString("es-AR", {
        weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'
      });
      
      let statusColor = "bg-slate-700 text-slate-300";
      let statusLabel = slot.status;
      let canEditDelete = slot.status !== "booked";
      
      if (slot.status === "available") {
        statusColor = "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
        statusLabel = "Disponible";
      } else if (slot.status === "booked") {
        statusColor = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        statusLabel = "Reservado (Booked)";
      } else if (slot.status === "cancelled") {
        statusColor = "bg-rose-500/10 text-rose-400 border-rose-500/20";
        statusLabel = "Cancelado";
      }

      const card = document.createElement("div");
      card.className = "p-4 rounded-xl border border-slate-800 bg-slate-900/40 flex items-center justify-between gap-4 hover:border-slate-700 transition animate-msg-in";
      card.innerHTML = `
        <div>
          <div class="flex items-center gap-2 text-sm text-slate-200">
            <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span class="capitalize font-medium">${startsStr}</span>
          </div>
          <div class="mt-2 flex items-center gap-2">
            <span class="px-2 py-0.5 text-[10px] font-semibold border rounded-md ${statusColor}">
              ${statusLabel}
            </span>
          </div>
        </div>
        
        <div class="flex items-center gap-2 flex-shrink-0">
          ${canEditDelete ? `
            <button class="doctor-slot-edit-btn px-2.5 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition" data-id="${slot.id}" data-starts="${slot.starts_at}">
              Editar
            </button>
            <button class="doctor-slot-delete-btn px-2.5 py-1.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg transition" data-id="${slot.id}">
              Eliminar
            </button>
          ` : '<span class="text-xs text-slate-500 font-medium px-2">Turno agendado</span>'}
        </div>
      `;
      listEl.appendChild(card);
    });

    // Slot listeners
    listEl.querySelectorAll(".doctor-slot-edit-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const starts = btn.dataset.starts;
        this.startSlotEdit(id, starts);
      });
    });
    
    listEl.querySelectorAll(".doctor-slot-delete-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        if (confirm("¿Estás seguro de que querés eliminar este horario disponible?")) {
          this.deleteSlot(id);
        }
      });
    });
  },

  setFormStatus(text, variant = "") {
    const el = $("slotFormStatus");
    if (!el) return;
    el.textContent = text;
    el.className = "text-xs mt-2";
    if (variant === "error") el.classList.add("text-red-400");
    else if (variant === "success") el.classList.add("text-emerald-400");
    else el.classList.add("text-slate-400");
  },

  async handleSlotSubmit(e) {
    e.preventDefault();
    this.setFormStatus("");
    
    const editId = $("editSlotId").value;
    const startsAtVal = $("slotStartsAt").value;
    const durationVal = parseInt($("slotDuration").value, 10);
    
    if (!startsAtVal) {
      this.setFormStatus("Por favor ingresá una fecha y hora.", "error");
      return;
    }

    const starts_at = startsAtVal;

    const isEdit = !!editId;
    const url = isEdit ? `/api/doctor/slots/${editId}` : "/api/doctor/slots";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starts_at, duration_minutes: durationVal })
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Error al guardar el horario.");
      }
      
      this.setFormStatus(isEdit ? "Horario actualizado con éxito." : "Horario creado con éxito.", "success");
      $("doctorSlotForm").reset();
      this.cancelSlotEdit();
      this.loadSlots();
    } catch (err) {
      this.setFormStatus(err.message, "error");
    }
  },

  startSlotEdit(id, startsAt) {
    $("editSlotId").value = id;
    
    // Parse to datetime-local format (YYYY-MM-DDTHH:mm)
    const date = parseApiDate(startsAt);
    const tzOffset = date.getTimezoneOffset() * 60000; // offset in milliseconds
    const localISOTime = (new Date(date - tzOffset)).toISOString().slice(0, 16);
    
    $("slotStartsAt").value = localISOTime;
    $("slotFormTitle").textContent = "Editar Horario";
    $("slotSubmitBtn").textContent = "Guardar Cambios";
    $("cancelSlotEditBtn").classList.remove("hidden");
  },

  cancelSlotEdit() {
    $("editSlotId").value = "";
    $("doctorSlotForm").reset();
    $("slotFormTitle").textContent = "Agregar Nuevo Horario";
    $("slotSubmitBtn").textContent = "Agregar Slot";
    $("cancelSlotEditBtn").classList.add("hidden");
  },

  async deleteSlot(id) {
    try {
      const res = await authFetch(`/api/doctor/slots/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "No se pudo eliminar el horario.");
      }
      this.loadSlots();
    } catch (err) {
      alert(err.message);
    }
  }
};

initAuth();
