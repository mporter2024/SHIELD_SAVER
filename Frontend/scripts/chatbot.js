const API_BASE = "http://127.0.0.1:5000";
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

function addMessageToHistory(sender, text, meta = null) {
    const history = getChatHistory();
    history.push({
        sender,
        text,
        meta,
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

function appendMessage(sender, text, save = true, meta = null) {
    const chatMessages = document.getElementById("chat-messages");
    if (!chatMessages) return;

    const messageEl = createMessageElement(sender, text);
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    if (save) {
        addMessageToHistory(sender, text, meta);
    }
}

function dispatchAIAction(data) {
    const action = data?.action || "chat_reply";

    window.dispatchEvent(
        new CustomEvent("shield-ai-action", {
            detail: data
        })
    );

    if (action === "event_created" && data.event) {
        localStorage.setItem("shield_last_event_id", String(data.event.id));
        localStorage.setItem("shield_last_action", "event_created");
    }

    if (action === "event_updated" && data.event_id) {
        localStorage.setItem("shield_last_event_id", String(data.event_id));
        localStorage.setItem("shield_last_action", "event_updated");
    }

    if ((action === "task_created" || action === "task_completed") && data.task) {
        localStorage.setItem("shield_last_event_id", String(data.task.event_id));
        localStorage.setItem("shield_last_action", action);
    }
}

async function trySmartRefresh(data) {
    const action = data?.action || "";

    const needsRefresh = [
        "event_created",
        "event_updated",
        "task_created",
        "task_completed"
    ].includes(action);

    if (!needsRefresh) return;

    try {
        if (typeof window.initializeDashboard === "function") {
            await window.initializeDashboard();
            return;
        }

        if (typeof window.initializeCalendar === "function") {
            await window.initializeCalendar();
            return;
        }

        if (typeof window.initializePlanner === "function") {
            await window.initializePlanner();
            return;
        }

        if (typeof window.refreshCalendarData === "function" && typeof window.rerenderCalendarViews === "function") {
            await window.refreshCalendarData();
            window.rerenderCalendarViews();
            return;
        }

        if (typeof window.renderPlanner === "function") {
            window.renderPlanner();
            return;
        }

        if (typeof window.location !== "undefined") {
            const path = window.location.pathname.toLowerCase();

            if (
                path.includes("dashboard") ||
                path.includes("calendar") ||
                path.includes("planner") ||
                path.includes("budget") ||
                path.includes("admin")
            ) {
                window.location.reload();
            }
        }
    } catch (error) {
        console.error("Smart refresh failed:", error);
    }
}

function buildStatusLine(data) {
    const action = data?.action || "";

    if (action === "event_created" && data.event) {
        return `Created event: ${data.event.title}`;
    }

    if (action === "event_updated" && data.event_id) {
        const updatedFields = Object.keys(data.updated_fields || {});
        if (updatedFields.length) {
            return `Updated fields: ${updatedFields.join(", ")}`;
        }
        return `Updated event #${data.event_id}`;
    }

    if (action === "task_created" && data.task) {
        return `Added task: ${data.task.title}`;
    }

    if (action === "task_completed" && data.task) {
        return `Completed task: ${data.task.title}`;
    }

    return "";
}

function showInlineAIStatus(data) {
    const statusEl =
        document.getElementById("chat-status") ||
        document.getElementById("event-message") ||
        document.getElementById("planner-error") ||
        document.getElementById("budget-status");

    if (!statusEl) return;

    const line = buildStatusLine(data);
    if (!line) return;

    statusEl.textContent = line;

    if (statusEl.id === "planner-error") {
        statusEl.style.display = "block";
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
        const response = await fetch(`${API_BASE}/api/ai/chat`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (!response.ok) {
            appendMessage("bot", data.error || "Something went wrong.", true, data);
            return;
        }

        appendMessage("bot", data.reply || "No reply received.", true, data);
        dispatchAIAction(data);
        showInlineAIStatus(data);
        await trySmartRefresh(data);
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

    localStorage.removeItem("shield_last_event_id");
    localStorage.removeItem("shield_last_action");

    try {
        await fetch(`${API_BASE}/api/ai/clear-chat`, {
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

window.sendChatMessage = sendChatMessage;
window.clearChatHistory = clearChatHistory;


document.addEventListener("DOMContentLoaded", setupChatbot);