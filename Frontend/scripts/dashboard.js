const API_BASE = "http://127.0.0.1:5000";

let currentEvents = [];
let allTasks = [];

const logoutBtn = document.getElementById("logout-btn");
const refreshBtn = document.getElementById("refresh-btn");
const eventForm = document.getElementById("event-form");
const chatForm = document.getElementById("chat-form");

logoutBtn.addEventListener("click", logout);
refreshBtn.addEventListener("click", initializeDashboard);
eventForm.addEventListener("submit", createEvent);
chatForm.addEventListener("submit", handleChatSubmit);

async function initializeDashboard() {
    try {
        const user = await fetchCurrentUser();
        document.getElementById("welcome-message").textContent = user.name;
        document.getElementById("user-email").textContent = user.email;
        localStorage.setItem("user", JSON.stringify(user));
        const adminLink = document.getElementById("admin-nav-link");
        if (adminLink) adminLink.style.display = user.role === "admin" ? "block" : "none";

        const [events, tasks] = await Promise.all([
            fetchMyEvents(),
            fetchMyTasks()
        ]);

        currentEvents = events;
        allTasks = tasks;

        updateStats(events, tasks);
        renderEvents(events, tasks);
    } catch (error) {
        console.error("Dashboard initialization failed:", error);
        window.location.href = "index.html";
    }
}

async function fetchCurrentUser() {
    const response = await fetch(`${API_BASE}/api/users/me`, {
        method: "GET",
        credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Not logged in");
    return data.user;
}

async function fetchMyEvents() {
    const response = await fetch(`${API_BASE}/api/events/mine`, {
        method: "GET",
        credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load events");
    return data;
}

async function fetchMyTasks() {
    const response = await fetch(`${API_BASE}/api/tasks/mine`, {
        method: "GET",
        credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load tasks");
    return data;
}

function updateStats(events, tasks) {
    const completed = tasks.filter(task => Number(task.completed) === 1).length;
    const pending = tasks.length - completed;

    document.getElementById("total-events").textContent = events.length;
    document.getElementById("total-tasks").textContent = tasks.length;
    document.getElementById("completed-tasks").textContent = completed;
    document.getElementById("pending-tasks").textContent = pending;
}

function renderEvents(events, tasks) {
    const container = document.getElementById("events-container");

    if (!events.length) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No events yet</h3>
                <p>Create your first event to start building out your planner.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = events.map((event) => {
        const eventTasks = tasks.filter(task => Number(task.event_id) === Number(event.id));
        const completedCount = eventTasks.filter(task => Number(task.completed) === 1).length;

        return `
            <div class="event-card">
                <div class="event-card-top">
                    <div>
                        <h3>${escapeHtml(event.title)}</h3>
                        <p><strong>When:</strong> ${formatDateTimeRange(event.start_datetime, event.end_datetime, event.date)}</p>
                        <p><strong>Location:</strong> ${escapeHtml(event.location || "Not set")}</p>
                        <p><strong>Budget:</strong> ${formatCurrency(Number(event.budget_total || 0))}</p>
                        <p><strong>Task Progress:</strong> ${completedCount} / ${eventTasks.length} complete</p>
                    </div>
                    <div class="event-card-actions">
                        <button class="secondary-btn small-action-btn" onclick="openPlanner(${event.id})">Open Planner</button>
                        <button class="small-danger-btn" onclick="deleteEvent(${event.id})">Delete</button>
                    </div>
                </div>

                <p class="event-description">${escapeHtml(event.description)}</p>
            </div>
        `;
    }).join("");
}

async function createEvent(event) {
    event.preventDefault();

    const messageEl = document.getElementById("event-message");
    messageEl.textContent = "Creating event...";

    const payload = {
        title: document.getElementById("event-title").value.trim(),
        start_datetime: document.getElementById("event-start").value,
        end_datetime: document.getElementById("event-end").value,
        location: document.getElementById("event-location").value.trim(),
        description: document.getElementById("event-description").value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/events/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            messageEl.textContent = data.error || "Could not create event.";
            return;
        }

        document.getElementById("event-form").reset();
        messageEl.textContent = "Event created successfully.";
        await initializeDashboard();
    } catch (error) {
        console.error("Create event error:", error);
        messageEl.textContent = "Server error while creating event.";
    }
}

function openPlanner(eventId) {
    localStorage.setItem("selectedEventId", eventId);
    window.location.href = `planner.html?event_id=${eventId}`;
}

async function deleteEvent(eventId) {
    const confirmed = confirm("Delete this event and all its tasks?");
    if (!confirmed) return;

    try {
        const response = await fetch(`${API_BASE}/api/events/${eventId}`, {
            method: "DELETE",
            credentials: "include"
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not delete event.");
            return;
        }

        await initializeDashboard();
    } catch (error) {
        console.error("Delete event error:", error);
        alert("Server error while deleting event.");
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/api/users/logout`, {
            method: "POST",
            credentials: "include"
        });
    } catch (error) {
        console.error("Logout error:", error);
    }

    localStorage.removeItem("user");
    localStorage.removeItem("selectedEventId");
    window.location.href = "index.html";
}

function formatDate(dateString) {
    if (!dateString) return "No date";
    const date = new Date(`${dateString}T00:00:00`);
    return date.toLocaleDateString();
}

function formatDateTime(dateTimeString) {
    if (!dateTimeString) return "";
    const date = new Date(dateTimeString);
    if (Number.isNaN(date.getTime())) return dateTimeString;
    return date.toLocaleString();
}

function formatDateTimeRange(startDateTime, endDateTime, fallbackDate) {
    if (startDateTime && endDateTime) return `${formatDateTime(startDateTime)} - ${formatDateTime(endDateTime)}`;
    if (startDateTime) return formatDateTime(startDateTime);
    if (fallbackDate) return formatDate(fallbackDate);
    return "No date";
}

function formatCurrency(amount) {
    return `$${Number(amount || 0).toFixed(2)}`;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function sendMessage(message) {
    const response = await fetch(`${API_BASE}/api/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Chat request failed");
    return data;
}

async function handleChatSubmit(event) {
    event.preventDefault();

    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message) return;

    appendChatMessage("user", message);
    input.value = "";

    try {
        const result = await sendMessage(message);
        appendChatMessage("bot", result.reply || "I couldn't generate a reply.");
        if (result.action === "task_created" || result.action === "task_completed") {
            await initializeDashboard();
        }
    } catch (error) {
        console.error("Chat error:", error);
        appendChatMessage("bot", "There was a problem reaching the chatbot.");
    }
}

function appendChatMessage(sender, text) {
    const container = document.getElementById("chat-messages");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.textContent = text;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

const plannerLink = document.getElementById("planner-nav-link");

if (plannerLink) {
    plannerLink.addEventListener("click", (e) => {
        e.preventDefault();

        const eventId = localStorage.getItem("selectedEventId");

        if (eventId) {
            window.location.href = `planner.html?event_id=${eventId}`;
        } else {
            alert("Please select an event first.");
        }
    });
}


window.openPlanner = openPlanner;
window.deleteEvent = deleteEvent;
window.initializeDashboard = initializeDashboard;
initializeDashboard();
