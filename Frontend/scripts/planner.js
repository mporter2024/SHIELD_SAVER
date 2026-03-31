const API_BASE = "http://127.0.0.1:5000";

let selectedEventId = null;
let currentEvent = null;
let currentTasks = [];
let currentAgenda = [];

const editForm = document.getElementById("event-edit-form");
const selectedTaskForm = document.getElementById("selected-task-form");
const agendaForm = document.getElementById("agenda-form");
const backDashboardBtn = document.getElementById("back-dashboard-btn");

if (editForm) editForm.addEventListener("submit", saveSelectedEvent);
if (selectedTaskForm) selectedTaskForm.addEventListener("submit", addTaskToSelectedEvent);
if (agendaForm) agendaForm.addEventListener("submit", addAgendaItem);
if (backDashboardBtn) {
    backDashboardBtn.addEventListener("click", () => {
        window.location.href = "dashboard.html";
    });
}

function getEventIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("event_id") || localStorage.getItem("selectedEventId");
}

async function initializePlanner() {
    selectedEventId = getEventIdFromUrl();

    if (!selectedEventId) {
        showError("No event was selected. Go back to the dashboard and open a planner from one of your events.");
        return;
    }

    localStorage.setItem("selectedEventId", selectedEventId);

    try {
        const [eventResponse, agendaResponse] = await Promise.all([
            fetch(`${API_BASE}/api/events/${selectedEventId}`, {
                method: "GET",
                credentials: "include"
            }),
            fetch(`${API_BASE}/api/agenda/event/${selectedEventId}`, {
                method: "GET",
                credentials: "include"
            })
        ]);

        const eventData = await eventResponse.json();
        const agendaData = await agendaResponse.json();

        if (!eventResponse.ok) {
            throw new Error(eventData.error || "Could not load event planner.");
        }
        if (!agendaResponse.ok) {
            throw new Error(agendaData.error || "Could not load agenda.");
        }

        currentEvent = eventData.event;
        currentTasks = eventData.tasks || [];
        currentAgenda = agendaData || [];
        renderPlanner();
    } catch (error) {
        console.error("Planner initialization failed:", error);
        showError(error.message || "Could not load planner.");
    }
}

function showError(message) {
    const errorBox = document.getElementById("planner-error");
    const content = document.getElementById("planner-content");
    errorBox.classList.remove("hidden");
    content.classList.add("hidden");
    errorBox.innerHTML = `<h2>Planner unavailable</h2><p>${escapeHtml(message)}</p>`;
    document.getElementById("planner-subtitle").textContent = "Unable to load event";
}

function renderPlanner() {
    const content = document.getElementById("planner-content");
    const errorBox = document.getElementById("planner-error");
    errorBox.classList.add("hidden");
    content.classList.remove("hidden");

    document.getElementById("planner-title").textContent = currentEvent.title || "Event Planner";
    document.getElementById("planner-subtitle").textContent = "Manage this event's details, tasks, agenda, lineup, and budget in one place.";
    document.getElementById("planner-sidebar-title").textContent = currentEvent.title || "Planner";
    document.getElementById("planner-sidebar-subtitle").textContent = formatDateTimeRange(currentEvent.start_datetime, currentEvent.end_datetime, currentEvent.date);

    document.getElementById("planner-budget-link").href = `budget.html?event_id=${currentEvent.id}`;
    document.getElementById("open-budget-page-link").href = `budget.html?event_id=${currentEvent.id}`;

    document.getElementById("edit-event-title").value = currentEvent.title || "";
    document.getElementById("edit-event-start").value = normalizeForDateTimeInput(currentEvent.start_datetime);
    document.getElementById("edit-event-end").value = normalizeForDateTimeInput(currentEvent.end_datetime);
    document.getElementById("edit-event-location").value = currentEvent.location || "";
    document.getElementById("edit-event-description").value = currentEvent.description || "";

    const completedCount = currentTasks.filter(task => Number(task.completed) === 1).length;
    document.getElementById("snapshot-schedule").textContent = formatDateTimeRange(currentEvent.start_datetime, currentEvent.end_datetime, currentEvent.date);
    document.getElementById("snapshot-location").textContent = currentEvent.location || "Not set";
    document.getElementById("snapshot-progress").textContent = `${completedCount} / ${currentTasks.length} complete`;
    document.getElementById("snapshot-budget").textContent = formatCurrency(Number(currentEvent.budget_total || 0));

    renderTasks();
    renderAgenda();
}

function renderTasks() {
    const taskContainer = document.getElementById("selected-event-tasks");
    const sortedTasks = [...currentTasks].sort((a, b) => {
        const aValue = a.start_datetime || a.due_date || "";
        const bValue = b.start_datetime || b.due_date || "";
        return aValue.localeCompare(bValue);
    });

    if (!sortedTasks.length) {
        taskContainer.innerHTML = `
            <div class="empty-state compact-empty-state">
                <h3>No tasks yet</h3>
                <p>Add the first task for this event using the form on the right.</p>
            </div>
        `;
        return;
    }

    taskContainer.innerHTML = `
        <ul class="task-list selected-task-list">
            ${sortedTasks.map(task => `
                <li class="task-item">
                    <div class="task-main">
                        <label>
                            <input
                                type="checkbox"
                                ${Number(task.completed) === 1 ? "checked" : ""}
                                onchange="toggleTask(${task.id}, ${jsonSafe(task.title)}, ${jsonSafe(task.due_date || "")}, ${jsonSafe(task.start_datetime || "")}, ${jsonSafe(task.end_datetime || "")}, this.checked)"
                            >
                            <span class="${Number(task.completed) === 1 ? "completed-task" : ""}">
                                ${escapeHtml(task.title)}
                            </span>
                        </label>
                        <span class="task-date">${formatDateTimeRange(task.start_datetime, task.end_datetime, task.due_date)}</span>
                    </div>
                    <button class="small-danger-btn task-delete-btn" onclick="deleteTask(${task.id})">Delete</button>
                </li>
            `).join("")}
        </ul>
    `;
}

function renderAgenda() {
    const agendaList = document.getElementById("agenda-list");

    if (!currentAgenda.length) {
        agendaList.innerHTML = `
            <div class="empty-state compact-empty-state">
                <h3>No agenda yet</h3>
                <p>Add your first timed agenda item on the right.</p>
            </div>
        `;
        return;
    }

    agendaList.innerHTML = currentAgenda.map(item => `
        <div class="agenda-card">
            <div class="agenda-card-header">
                <div>
                    <h4>${escapeHtml(item.title)}</h4>
                    <p class="muted-text">${formatTimeRange(item.start_time, item.end_time)}</p>
                </div>
                <button class="small-danger-btn" onclick="deleteAgendaItem(${item.id})">Delete</button>
            </div>
            ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}

            <div class="lineup-block">
                <strong>Lineup</strong>
                ${item.lineup && item.lineup.length ? `
                    <ul class="lineup-list">
                        ${item.lineup.map(person => `
                            <li>
                                <span>${escapeHtml(person.name)}${person.role ? ` — ${escapeHtml(person.role)}` : ""}</span>
                                <button class="small-danger-btn" onclick="deleteLineupItem(${person.id})">Remove</button>
                            </li>
                        `).join("")}
                    </ul>
                ` : `<p class="muted-text">No lineup entries yet.</p>`}

                <form class="lineup-form" onsubmit="addLineupItem(event, ${item.id})">
                    <input type="text" name="name" placeholder="Person or act name" required>
                    <input type="text" name="role" placeholder="Role or note">
                    <button type="submit">Add Lineup Entry</button>
                </form>
            </div>
        </div>
    `).join("");
}

async function saveSelectedEvent(event) {
    event.preventDefault();

    const messageEl = document.getElementById("event-edit-message");
    messageEl.textContent = "Saving changes...";

    const payload = {
        title: document.getElementById("edit-event-title").value.trim(),
        start_datetime: document.getElementById("edit-event-start").value,
        end_datetime: document.getElementById("edit-event-end").value,
        location: document.getElementById("edit-event-location").value.trim(),
        description: document.getElementById("edit-event-description").value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/events/${selectedEventId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            messageEl.textContent = data.error || "Could not save event changes.";
            return;
        }

        messageEl.textContent = "Event details updated.";
        await initializePlanner();
    } catch (error) {
        console.error("Save event error:", error);
        messageEl.textContent = "Server error while saving event.";
    }
}

async function addTaskToSelectedEvent(event) {
    event.preventDefault();

    const messageEl = document.getElementById("selected-task-message");
    messageEl.textContent = "Adding task...";

    const payload = {
        title: document.getElementById("selected-task-title").value.trim(),
        start_datetime: document.getElementById("selected-task-start").value,
        end_datetime: document.getElementById("selected-task-end").value,
        event_id: selectedEventId,
        completed: 0
    };

    try {
        const response = await fetch(`${API_BASE}/api/tasks/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            messageEl.textContent = data.error || "Could not create task.";
            return;
        }

        document.getElementById("selected-task-form").reset();
        messageEl.textContent = "Task added to event.";
        await initializePlanner();
    } catch (error) {
        console.error("Add task error:", error);
        messageEl.textContent = "Server error while adding task.";
    }
}

async function addAgendaItem(event) {
    event.preventDefault();

    const messageEl = document.getElementById("agenda-message");
    messageEl.textContent = "Adding agenda item...";

    const payload = {
        event_id: selectedEventId,
        title: document.getElementById("agenda-title").value.trim(),
        start_time: document.getElementById("agenda-start").value,
        end_time: document.getElementById("agenda-end").value,
        description: document.getElementById("agenda-description").value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/agenda/items`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            messageEl.textContent = data.error || "Could not create agenda item.";
            return;
        }

        if (agendaForm) agendaForm.reset();
        messageEl.textContent = "Agenda item added.";
        await initializePlanner();
    } catch (error) {
        console.error("Add agenda error:", error);
        messageEl.textContent = "Server error while adding agenda item.";
    }
}

async function addLineupItem(event, agendaItemId) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        agenda_item_id: agendaItemId,
        name: form.name.value.trim(),
        role: form.role.value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/agenda/lineup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not add lineup entry.");
            return;
        }
        form.reset();
        await initializePlanner();
    } catch (error) {
        console.error("Add lineup error:", error);
        alert("Server error while adding lineup entry.");
    }
}

async function toggleTask(taskId, title, dueDate, startDateTime, endDateTime, checked) {
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                title: title,
                due_date: dueDate,
                start_datetime: startDateTime,
                end_datetime: endDateTime,
                completed: checked ? 1 : 0
            })
        });

        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not update task.");
            return;
        }

        await initializePlanner();
    } catch (error) {
        console.error("Toggle task error:", error);
        alert("Server error while updating task.");
    }
}

async function deleteTask(taskId) {
    if (!confirm("Delete this task?")) return;

    try {
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
            method: "DELETE",
            credentials: "include"
        });

        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not delete task.");
            return;
        }

        await initializePlanner();
    } catch (error) {
        console.error("Delete task error:", error);
        alert("Server error while deleting task.");
    }
}

async function deleteAgendaItem(agendaItemId) {
    if (!confirm("Delete this agenda item and its lineup entries?")) return;

    try {
        const response = await fetch(`${API_BASE}/api/agenda/items/${agendaItemId}`, {
            method: "DELETE",
            credentials: "include"
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not delete agenda item.");
            return;
        }
        await initializePlanner();
    } catch (error) {
        console.error("Delete agenda error:", error);
        alert("Server error while deleting agenda item.");
    }
}

async function deleteLineupItem(lineupItemId) {
    if (!confirm("Remove this lineup entry?")) return;

    try {
        const response = await fetch(`${API_BASE}/api/agenda/lineup/${lineupItemId}`, {
            method: "DELETE",
            credentials: "include"
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not delete lineup entry.");
            return;
        }
        await initializePlanner();
    } catch (error) {
        console.error("Delete lineup error:", error);
        alert("Server error while deleting lineup entry.");
    }
}

function normalizeForDateTimeInput(dateTimeString) {
    if (!dateTimeString) return "";
    return String(dateTimeString).slice(0, 16);
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

function formatTimeRange(startTime, endTime) {
    if (startTime && endTime) return `${startTime} - ${endTime}`;
    if (startTime) return startTime;
    if (endTime) return endTime;
    return "Time not set";
}

function formatCurrency(amount) {
    return `$${Number(amount || 0).toFixed(2)}`;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function jsonSafe(value) {
    return JSON.stringify(String(value ?? ""));
}

window.toggleTask = toggleTask;
window.deleteTask = deleteTask;
window.addLineupItem = addLineupItem;
window.deleteAgendaItem = deleteAgendaItem;
window.deleteLineupItem = deleteLineupItem;

initializePlanner();
