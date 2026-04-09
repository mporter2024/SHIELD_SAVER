const CHATBOT_API_BASE = "http://127.0.0.1:5000";
const CHAT_STORAGE_KEY = "shieldSaverChatHistory";

function getChatHistory() {
    try {
        return JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY)) || [];
    } catch (error) {
        console.error("Failed to parse chat history:", error);
        return [];
    }
}

function saveChatHistory(history) {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
}

function addMessageToHistory(sender, text) {
    const history = getChatHistory();
    history.push({
        sender,
        text,
        timestamp: Date.now()
    });
    saveChatHistory(history);
}

function clearStoredChatHistory() {
    localStorage.removeItem(CHAT_STORAGE_KEY);
}

function createMessageElement(sender, text) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `chat-message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.textContent = text;

    messageDiv.appendChild(bubble);
    return messageDiv;
}

function getDefaultGreeting() {
    const path = window.location.pathname.toLowerCase();

    if (path.includes("budget")) {
        return "Hi! I can help you think through budget categories, event costs, and next planning steps.";
    }

    if (path.includes("planner")) {
        return "Hi! I’m your planning assistant. I can help create events, update details, and manage tasks.";
    }

    return "Hi! I’m your event planning assistant. Ask me about budgeting, venues, catering, timelines, or creating an event.";
}

function renderChatHistory() {
    const chatMessages = document.getElementById("chat-messages");
    if (!chatMessages) return;

    const history = getChatHistory();

    if (!history.length) {
        if (!chatMessages.children.length) {
            const greetingEl = createMessageElement("bot", getDefaultGreeting());
            chatMessages.appendChild(greetingEl);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return;
    }

    chatMessages.innerHTML = "";

    history.forEach((msg) => {
        const messageEl = createMessageElement(msg.sender, msg.text);
        chatMessages.appendChild(messageEl);
    });

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendMessage(sender, text, save = true) {
    const chatMessages = document.getElementById("chat-messages");
    if (!chatMessages) return;

    const messageEl = createMessageElement(sender, text);
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (save) {
        addMessageToHistory(sender, text);
    }
}

async function sendChatMessage() {
    const input = document.getElementById("chat-input");
    if (!input) return;

    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", message, true);
    input.value = "";

    try {
        const response = await fetch(`${CHATBOT_API_BASE}/api/ai/chat`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (!response.ok) {
            appendMessage("bot", data.error || "Something went wrong.", true);
            return;
        }

        appendMessage("bot", data.reply || "No reply received.", true);
        if (data.event) {
            localStorage.setItem("last_ai_event_id", data.event.id);
        }

        if (data.event_id) {
            localStorage.setItem("last_ai_event_id", data.event_id);
        }

        if (
            data.action === "event_created" ||
            data.action === "event_updated" ||
            data.action === "task_created" ||
            data.action === "task_completed"
        ) {
            window.dispatchEvent(
                new CustomEvent("shield-ai-action", { detail: data })
            );
        }
    } catch (error) {
        console.error("Chat request failed:", error);
        appendMessage("bot", "Unable to reach the assistant right now.", true);
    }
}

async function clearChatHistory() {
    clearStoredChatHistory();

    const chatMessages = document.getElementById("chat-messages");
    if (chatMessages) {
        chatMessages.innerHTML = "";
    }

    try {
        await fetch(`${CHATBOT_API_BASE}/api/ai/clear-chat`, {
            method: "POST",
            credentials: "include"
        });
    } catch (error) {
        console.error("Failed to clear backend chat state:", error);
    }

    renderChatHistory();
}

function setupChatbot() {
    const sendBtn = document.getElementById("send-chat-btn");
    const clearBtn = document.getElementById("clear-chat-btn");
    const input = document.getElementById("chat-input");
    const chatForm = document.getElementById("chat-form");

    renderChatHistory();

    if (sendBtn) {
        sendBtn.addEventListener("click", sendChatMessage);
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", clearChatHistory);
    }

    if (chatForm) {
        chatForm.addEventListener("submit", (event) => {
            event.preventDefault();
            sendChatMessage();
        });
    }

    if (input) {
        input.addEventListener("keypress", (event) => {
            if (event.key === "Enter" && !chatForm) {
                event.preventDefault();
                sendChatMessage();
            }
        });
    }
}

window.sendChatMessage = sendChatMessage;
window.clearChatHistory = clearChatHistory;

document.addEventListener("DOMContentLoaded", setupChatbot);