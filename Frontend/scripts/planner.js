const API_BASE = "http://127.0.0.1:5000";

let selectedEventId = null;
let availableEvents = [];
let currentEvent = null;
let currentTasks = [];
let currentAgenda = [];
let editingTaskId = null;
let editingAgendaId = null;

const editForm = document.getElementById("event-edit-form");
const selectedTaskForm = document.getElementById("selected-task-form");
const agendaForm = document.getElementById("agenda-form");

if (editForm) editForm.addEventListener("submit", saveSelectedEvent);
if (selectedTaskForm) selectedTaskForm.addEventListener("submit", addTaskToSelectedEvent);
if (agendaForm) agendaForm.addEventListener("submit", addAgendaItem);

function getEventIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("event_id") || localStorage.getItem("selectedEventId");
}

async function fetchAvailableEvents() {
    const response = await fetch(`${API_BASE}/api/events`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || "Could not load events.");
    }

    if (Array.isArray(data)) return data;
    if (Array.isArray(data.events)) return data.events;
    return [];
}

function syncEventSelector() {
    const dropdown = document.getElementById("event-selector");
    if (!dropdown) return;

    if (!availableEvents.length) {
        dropdown.innerHTML = `<option value="">No events available</option>`;
        dropdown.disabled = true;
        return;
    }

    dropdown.disabled = false;
    dropdown.innerHTML = availableEvents.map(event => `
        <option value="${event.id}" ${String(event.id) === String(selectedEventId) ? "selected" : ""}>
            ${escapeHtml(event.title || `Event #${event.id}`)}
        </option>
    `).join("");
}

function showPlannerEmptyState() {
    const errorBox = document.getElementById("planner-error");
    const content = document.getElementById("planner-content");
    errorBox.classList.remove("hidden");
    content.classList.add("hidden");
    errorBox.innerHTML = `<h2>No events yet</h2><p>Create an event on the dashboard to get started.</p>`;
    document.getElementById("planner-title").textContent = "Event Planner";
    document.getElementById("planner-subtitle").textContent = "Create an event on the dashboard to get started.";
    const sidebarTitle = document.getElementById("sidebar-title");
    const sidebarSubtitle = document.getElementById("sidebar-subtitle");
    if (sidebarTitle) sidebarTitle.textContent = "Planner";
    if (sidebarSubtitle) sidebarSubtitle.textContent = "No event selected";
}

function handlePlannerEventSelection(event) {
    const newEventId = event.target.value;
    if (!newEventId) return;
    selectedEventId = newEventId;
    localStorage.setItem("selectedEventId", selectedEventId);
    window.location.href = `planner.html?event_id=${selectedEventId}`;
}


async function initializePlanner() {
    selectedEventId = getEventIdFromUrl();

    try {
        availableEvents = await fetchAvailableEvents();

        if (!availableEvents.length) {
            showPlannerEmptyState();
            syncEventSelector();
            return;
        }

        const matchedEvent = availableEvents.find(event => String(event.id) === String(selectedEventId));
        if (!matchedEvent) {
            selectedEventId = String(availableEvents[0].id);
        }

        localStorage.setItem("selectedEventId", selectedEventId);
        syncEventSelector();

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

        if (!eventResponse.ok) throw new Error(eventData.error || "Could not load event planner.");
        if (!agendaResponse.ok) throw new Error(agendaData.error || "Could not load agenda.");

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
    document.getElementById("planner-subtitle").textContent = "Select an event or return to the dashboard.";
}

function renderPlanner() {
    const content = document.getElementById("planner-content");
    const errorBox = document.getElementById("planner-error");
    errorBox.classList.add("hidden");
    content.classList.remove("hidden");

    syncEventSelector();
    document.getElementById("planner-title").textContent = currentEvent.title || "Event Planner";
    document.getElementById("planner-subtitle").textContent = "Manage this event's details, tasks, agenda, lineup, and budget in one place.";
    document.getElementById("sidebar-title").textContent = currentEvent.title || "Planner";
    document.getElementById("sidebar-subtitle").textContent = formatDateTimeRange(currentEvent.start_datetime, currentEvent.end_datetime, currentEvent.date);

    const overviewLink = document.getElementById("open-overview-page-link");
    const budgetLink = document.getElementById("open-budget-page-link");
    if (overviewLink) overviewLink.href = `overview.html?event_id=${currentEvent.id}`;
    if (budgetLink) budgetLink.href = `budget.html?event_id=${currentEvent.id}`;

    document.getElementById("edit-event-title").value = currentEvent.title || "";
    document.getElementById("edit-event-start").value = normalizeForDateTimeInput(currentEvent.start_datetime);
    document.getElementById("edit-event-end").value = normalizeForDateTimeInput(currentEvent.end_datetime);
    document.getElementById("edit-event-location").value = currentEvent.location || "";
    document.getElementById("edit-event-description").value = currentEvent.description || "";
    document.getElementById("agenda-date").value = document.getElementById("agenda-date").value || (currentEvent.date || "");

    const completedCount = currentTasks.filter(task => Number(task.completed) === 1).length;
    document.getElementById("snapshot-schedule").textContent = formatDateTimeRange(currentEvent.start_datetime, currentEvent.end_datetime, currentEvent.date);
    document.getElementById("snapshot-location").textContent = currentEvent.location || "Not set";
    document.getElementById("snapshot-progress").textContent = `${completedCount} / ${currentTasks.length} complete`;
    document.getElementById("snapshot-budget").textContent = formatCurrency(Number(currentEvent.budget_total || 0));

    renderTasks();
    renderAgenda();
    highlightPlannerFromAI();
}

function highlightPlannerFromAI() {
    if (!currentEvent) return;

    const lastEventId = localStorage.getItem("last_ai_event_id");
    const panel =
        document.getElementById("planner-content") ||
        document.querySelector(".hero-panel");

    if (!panel) return;

    panel.classList.remove("ai-highlight");

    if (lastEventId && String(currentEvent.id) === String(lastEventId)) {
        panel.classList.add("ai-highlight");

        setTimeout(() => {
            panel.classList.remove("ai-highlight");
        }, 3000);
    }
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
            ${sortedTasks.map(task => editingTaskId === task.id ? renderTaskEditItem(task) : renderTaskReadItem(task)).join("")}
        </ul>
    `;
}

function renderTaskReadItem(task) {
    return `
        <li class="task-item planner-editable-item">
            <div class="task-main task-main-stack">
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
            <div class="inline-action-group">
                <button class="secondary-btn small-action-btn" onclick="startTaskEdit(${task.id})">Edit</button>
                <button class="small-danger-btn task-delete-btn" onclick="deleteTask(${task.id})">Delete</button>
            </div>
        </li>
    `;
}

function renderTaskEditItem(task) {
    return `
        <li class="task-item planner-editable-item editing">
            <div class="task-main task-main-stack full-width">
                <input type="text" id="edit-task-title-${task.id}" value="${escapeHtml(task.title)}" placeholder="Task title">
                <div class="inline-edit-grid">
                    <div>
                        <label for="edit-task-start-${task.id}">Start</label>
                        <input type="datetime-local" id="edit-task-start-${task.id}" value="${normalizeForDateTimeInput(task.start_datetime)}">
                    </div>
                    <div>
                        <label for="edit-task-end-${task.id}">End</label>
                        <input type="datetime-local" id="edit-task-end-${task.id}" value="${normalizeForDateTimeInput(task.end_datetime)}">
                    </div>
                </div>
            </div>
            <div class="inline-action-group">
                <button class="secondary-btn small-action-btn" onclick="saveTaskEdit(${task.id}, ${Number(task.completed)})">Save</button>
                <button class="secondary-btn small-action-btn" onclick="cancelTaskEdit()">Cancel</button>
            </div>
        </li>
    `;
}

function renderAgenda() {
    const agendaList = document.getElementById("agenda-list");

    if (!currentAgenda.length) {
        agendaList.innerHTML = `
            <div class="empty-state compact-empty-state">
                <h3>No agenda yet</h3>
                <p>Add your first dated agenda item on the right.</p>
            </div>
        `;
        return;
    }

    agendaList.innerHTML = currentAgenda.map(item => editingAgendaId === item.id ? renderAgendaEditItem(item) : renderAgendaReadItem(item)).join("");
}

function renderAgendaReadItem(item) {
    return `
        <div class="agenda-card planner-editable-item">
            <div class="agenda-card-header">
                <div>
                    <h4>${escapeHtml(item.title)}</h4>
                    <p class="muted-text">${formatAgendaSchedule(item)}</p>
                </div>
                <div class="inline-action-group">
                    <button class="secondary-btn small-action-btn" onclick="startAgendaEdit(${item.id})">Edit</button>
                    <button class="small-danger-btn" onclick="deleteAgendaItem(${item.id})">Delete</button>
                </div>
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
    `;
}

function renderAgendaEditItem(item) {
    return `
        <div class="agenda-card planner-editable-item editing">
            <div class="inline-edit-grid">
                <div>
                    <label for="edit-agenda-title-${item.id}">Title</label>
                    <input type="text" id="edit-agenda-title-${item.id}" value="${escapeHtml(item.title)}" placeholder="Agenda title">
                </div>
                <div>
                    <label for="edit-agenda-date-${item.id}">Date</label>
                    <input type="date" id="edit-agenda-date-${item.id}" value="${item.agenda_date || currentEvent?.date || ""}">
                </div>
                <div>
                    <label for="edit-agenda-start-${item.id}">Start time</label>
                    <input type="time" id="edit-agenda-start-${item.id}" value="${item.start_time || ""}">
                </div>
                <div>
                    <label for="edit-agenda-end-${item.id}">End time</label>
                    <input type="time" id="edit-agenda-end-${item.id}" value="${item.end_time || ""}">
                </div>
            </div>
            <label for="edit-agenda-description-${item.id}">Description</label>
            <textarea id="edit-agenda-description-${item.id}" rows="3">${escapeHtml(item.description || "")}</textarea>
            <div class="inline-action-group top-gap">
                <button class="secondary-btn small-action-btn" onclick="saveAgendaEdit(${item.id})">Save</button>
                <button class="secondary-btn small-action-btn" onclick="cancelAgendaEdit()">Cancel</button>
            </div>
        </div>
    `;
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
        agenda_date: document.getElementById("agenda-date").value,
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

        if (agendaForm) {
            agendaForm.reset();
            document.getElementById("agenda-date").value = currentEvent?.date || "";
        }
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

function startTaskEdit(taskId) {
    editingTaskId = taskId;
    renderTasks();
}

function cancelTaskEdit() {
    editingTaskId = null;
    renderTasks();
}

async function saveTaskEdit(taskId, completed) {
    const payload = {
        title: document.getElementById(`edit-task-title-${taskId}`).value.trim(),
        start_datetime: document.getElementById(`edit-task-start-${taskId}`).value,
        end_datetime: document.getElementById(`edit-task-end-${taskId}`).value,
        completed
    };

    try {
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not update task.");
            return;
        }
        editingTaskId = null;
        await initializePlanner();
    } catch (error) {
        console.error("Save task error:", error);
        alert("Server error while saving task.");
    }
}

function startAgendaEdit(agendaItemId) {
    editingAgendaId = agendaItemId;
    renderAgenda();
}

function cancelAgendaEdit() {
    editingAgendaId = null;
    renderAgenda();
}

async function saveAgendaEdit(agendaItemId) {
    const payload = {
        title: document.getElementById(`edit-agenda-title-${agendaItemId}`).value.trim(),
        agenda_date: document.getElementById(`edit-agenda-date-${agendaItemId}`).value,
        start_time: document.getElementById(`edit-agenda-start-${agendaItemId}`).value,
        end_time: document.getElementById(`edit-agenda-end-${agendaItemId}`).value,
        description: document.getElementById(`edit-agenda-description-${agendaItemId}`).value.trim()
    };

    try {
        const response = await fetch(`${API_BASE}/api/agenda/items/${agendaItemId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Could not update agenda item.");
            return;
        }
        editingAgendaId = null;
        await initializePlanner();
    } catch (error) {
        console.error("Save agenda error:", error);
        alert("Server error while saving agenda item.");
    }
}

async function toggleTask(taskId, title, dueDate, startDateTime, endDateTime, checked) {
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
                title,
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

function formatAgendaSchedule(item) {
    const dateLabel = item.agenda_date ? formatDate(item.agenda_date) : "No date";
    if (item.start_time && item.end_time) return `${dateLabel} • ${item.start_time} - ${item.end_time}`;
    if (item.start_time) return `${dateLabel} • ${item.start_time}`;
    if (item.end_time) return `${dateLabel} • Ends ${item.end_time}`;
    return dateLabel;
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

window.startTaskEdit = startTaskEdit;
window.cancelTaskEdit = cancelTaskEdit;
window.saveTaskEdit = saveTaskEdit;
window.startAgendaEdit = startAgendaEdit;
window.cancelAgendaEdit = cancelAgendaEdit;
window.saveAgendaEdit = saveAgendaEdit;
window.toggleTask = toggleTask;
window.deleteTask = deleteTask;
window.addLineupItem = addLineupItem;
window.deleteAgendaItem = deleteAgendaItem;
window.deleteLineupItem = deleteLineupItem;
window.initializePlanner = initializePlanner;
window.renderPlanner = renderPlanner;

window.addEventListener("shield-ai-action", async (event) => {
    const data = event.detail || {};
    const relatedEventId = data.event?.id || data.event_id || data.task?.event_id;

    if (relatedEventId && String(selectedEventId) === String(relatedEventId)) {
        await initializePlanner();
    }
});


document.addEventListener("DOMContentLoaded", async () => {
    const eventSelector = document.getElementById("event-selector");
    if (eventSelector) {
        eventSelector.addEventListener("change", handlePlannerEventSelection);
    }

    await loadSidebar("planner", "Planner", "Manage one event in detail", {
        brandSubtitle: "Event Planner",
        actions: [
            { id: "back-dashboard-btn", label: "Back to Dashboard", className: "secondary-btn", action: "go", href: "dashboard.html" },
            { id: "logout-btn", label: "Logout", className: "danger-btn", action: "logout" }
        ]
    });
    initializePlanner();
});
