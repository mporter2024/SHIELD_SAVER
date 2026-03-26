const API_BASE = "http://127.0.0.1:5000";

let currentUser = null;
let currentEvents = [];
let allTasks = [];

document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("refresh-btn").addEventListener("click", initializeDashboard);
document.getElementById("event-form").addEventListener("submit", createEvent);
document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);

async function initializeDashboard() {
    try {
        const user = await fetchCurrentUser();
        currentUser = user;

        document.getElementById("welcome-message").textContent = user.name;
        document.getElementById("user-email").textContent = user.email;

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

    if (!response.ok) {
        throw new Error(data.error || "Not logged in");
    }

    return data.user;
}

async function fetchMyEvents() {
    const response = await fetch(`${API_BASE}/api/events/mine`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Could not load events");
    }

    return data;
}

async function fetchMyTasks() {
    const response = await fetch(`${API_BASE}/api/tasks/mine`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Could not load tasks");
    }

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

        return `
            <div class="event-card">
                <div class="event-card-top">
                    <div>
                        <h3>${escapeHtml(event.title)}</h3>
                        <p><strong>Date:</strong> ${formatDate(event.date)}</p>
                        <p><strong>Location:</strong> ${escapeHtml(event.location)}</p>
                    </div>
                    <button class="small-danger-btn" onclick="deleteEvent(${event.id})">Delete</button>
                </div>

                <p class="event-description">${escapeHtml(event.description)}</p>

                <div class="task-section">
                    <h4>Tasks</h4>
                    ${
                        eventTasks.length
                            ? `<ul class="task-list">
                                ${eventTasks.map(task => `
                                    <li class="task-item">
                                        <label>
                                            <input
                                                type="checkbox"
                                                ${Number(task.completed) === 1 ? "checked" : ""}
                                                onchange="toggleTask(${task.id}, '${escapeJs(task.title)}', '${task.due_date || ""}', this.checked)"
                                            >
                                            <span class="${Number(task.completed) === 1 ? "completed-task" : ""}">
                                                ${escapeHtml(task.title)}
                                            </span>
                                        </label>
                                        <span class="task-date">${task.due_date ? formatDate(task.due_date) : "No due date"}</span>
                                    </li>
                                `).join("")}
                              </ul>`
                            : `<p class="muted-text">No tasks for this event yet.</p>`
                    }

                    <form class="task-form" onsubmit="addTask(event, ${event.id})">
                        <input type="text" name="title" placeholder="New task title" required>
                        <input type="date" name="due_date">
                        <button type="submit">Add Task</button>
                    </form>
                </div>
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
        date: document.getElementById("event-date").value,
        location: document.getElementById("event-location").value.trim(),
        description: document.getElementById("event-description").value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/events/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
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

async function addTask(event, eventId) {
    event.preventDefault();

    const form = event.target;
    const title = form.title.value.trim();
    const due_date = form.due_date.value;

    try {
        const response = await fetch(`${API_BASE}/api/tasks/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify({
                title,
                due_date,
                event_id: eventId,
                completed: 0
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Could not create task.");
            return;
        }

        form.reset();
        await initializeDashboard();
    } catch (error) {
        console.error("Add task error:", error);
        alert("Server error while adding task.");
    }
}

async function toggleTask(taskId, title, dueDate, checked) {
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify({
                title: title,
                due_date: dueDate,
                completed: checked ? 1 : 0
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Could not update task.");
            return;
        }

        await initializeDashboard();
    } catch (error) {
        console.error("Toggle task error:", error);
        alert("Server error while updating task.");
    }
}

async function deleteEvent(eventId) {
    const confirmed = confirm("Delete this event and its tasks?");
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

    window.location.href = "index.html";
}

function formatDate(dateString) {
    if (!dateString) return "No date";
    const date = new Date(`${dateString}T00:00:00`);
    return date.toLocaleDateString();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeJs(value) {
    return String(value)
        .replaceAll("\\", "\\\\")
        .replaceAll("'", "\\'")
        .replaceAll('"', '\\"');
}

async function sendMessage(message) {
    const response = await fetch(`${API_BASE}/api/ai/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({ message })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || "Chat request failed");
    }

    return data.reply;
}

async function handleChatSubmit(event) {
    event.preventDefault();

    const input = document.getElementById("chat-input");
    const message = input.value.trim();

    if (!message) return;

    appendChatMessage("user", message);
    input.value = "";

    try {
        const reply = await sendMessage(message);
        appendChatMessage("bot", reply || "I couldn't generate a reply.");
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

initializeDashboard();