const messagesEl = document.querySelector("#messages");
const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const statusEl = document.querySelector("#status");
const voiceButton = document.querySelector("#voiceButton");
const ttsToggle = document.querySelector("#ttsToggle");

let conversationId = localStorage.getItem("conversationId");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function speak(text) {
  if (!ttsToggle.checked || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "es-AR";
  window.speechSynthesis.speak(utterance);
}

async function ensureConversation() {
  if (conversationId) return conversationId;
  const response = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: "web_chat" }),
  });
  if (!response.ok) throw new Error("No se pudo crear la conversación");
  const data = await response.json();
  conversationId = String(data.id);
  localStorage.setItem("conversationId", conversationId);
  return conversationId;
}

async function sendMessage(text, inputMode = "text") {
  const trimmed = text.trim();
  if (!trimmed) return;
  addMessage("user", trimmed);
  input.value = "";
  statusEl.textContent = "Procesando...";
  try {
    const id = await ensureConversation();
    const response = await fetch(`/api/conversations/${id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed, input_mode: inputMode }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Error enviando mensaje");
    }
    const data = await response.json();
    addMessage("assistant", data.response);
    speak(data.response);
  } catch (error) {
    addMessage("assistant", "No pude procesar el mensaje. Intentá nuevamente.");
    console.error(error);
  } finally {
    statusEl.textContent = "";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

voiceButton.addEventListener("click", () => {
  if (!SpeechRecognition) {
    statusEl.textContent = "Tu navegador no soporta reconocimiento de voz. Usá el chat escrito.";
    return;
  }
  if (recognition) {
    recognition.stop();
    return;
  }
  recognition = new SpeechRecognition();
  recognition.lang = "es-AR";
  recognition.interimResults = false;
  recognition.continuous = false;
  voiceButton.classList.add("recording");
  statusEl.textContent = "Escuchando...";
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    sendMessage(transcript, "voice");
  };
  recognition.onerror = () => {
    statusEl.textContent = "No pude escuchar bien. Probá otra vez o escribí el mensaje.";
  };
  recognition.onend = () => {
    recognition = null;
    voiceButton.classList.remove("recording");
    if (statusEl.textContent === "Escuchando...") statusEl.textContent = "";
  };
  recognition.start();
});

addMessage(
  "assistant",
  "Hola. Puedo ayudarte a sacar un turno. Para empezar, escribí tu nombre y apellido, DNI, teléfono y especialidad."
);
