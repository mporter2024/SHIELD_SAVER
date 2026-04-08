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
    bubble.className = "chat-bubble";
    bubble.textContent = text;

    messageDiv.appendChild(bubble);
    return messageDiv;
}

function renderChatHistory() {
    const chatMessages = document.getElementById("chat-messages");
    if (!chatMessages) return;

    chatMessages.innerHTML = "";

    const history = getChatHistory();
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
        const response = await fetch("http://127.0.0.1:5000/api/ai/chat", {
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
        await fetch("http://127.0.0.1:5000/api/ai/clear-chat", {
            method: "POST",
            credentials: "include"
        });
    } catch (error) {
        console.error("Failed to clear backend chat state:", error);
    }

    appendMessage("bot", "Chat history cleared.", true);
}

function setupChatbot() {
    const sendBtn = document.getElementById("send-chat-btn");
    const clearBtn = document.getElementById("clear-chat-btn");
    const input = document.getElementById("chat-input");

    renderChatHistory();

    if (sendBtn) {
        sendBtn.addEventListener("click", sendChatMessage);
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", clearChatHistory);
    }

    if (input) {
        input.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                sendChatMessage();
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", setupChatbot);