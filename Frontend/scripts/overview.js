const API_BASE = "http://127.0.0.1:5000";

let selectedEventId = null;

function getEventIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("event_id") || localStorage.getItem("selectedEventId");
}

async function initializeOverview() {
    selectedEventId = getEventIdFromUrl();
    if (!selectedEventId) {
        showOverviewError("No event was selected. Open an event from the dashboard first.");
        return;
    }

    localStorage.setItem("selectedEventId", selectedEventId);

    try {
        const currentUser = JSON.parse(localStorage.getItem("user") || "null");
        const adminLink = document.getElementById("admin-nav-link");
        if (adminLink && currentUser) adminLink.style.display = currentUser.role === "admin" ? "block" : "none";

        const [eventResponse, agendaResponse] = await Promise.all([
            fetch(`${API_BASE}/api/events/${selectedEventId}`, { method: "GET", credentials: "include" }),
            fetch(`${API_BASE}/api/agenda/event/${selectedEventId}`, { method: "GET", credentials: "include" })
        ]);

        const eventData = await eventResponse.json();
        const agendaData = await agendaResponse.json();

        if (!eventResponse.ok) throw new Error(eventData.error || "Could not load event overview.");
        if (!agendaResponse.ok) throw new Error(agendaData.error || "Could not load agenda.");

        renderOverview(eventData.event, eventData.tasks || [], agendaData || []);
    } catch (error) {
        console.error("Overview initialization failed:", error);
        showOverviewError(error.message || "Could not load overview.");
    }
}

function renderOverview(event, tasks, agenda) {
    document.getElementById("overview-error").classList.add("hidden");
    document.getElementById("overview-content").classList.remove("hidden");

    const completedTasks = tasks.filter(task => Number(task.completed) === 1).length;
    const pendingTasks = tasks.length - completedTasks;

    document.getElementById("overview-title").textContent = event.title || "Event Overview";
    document.getElementById("overview-subtitle").textContent = "Use this page for a clean summary before diving back into planning.";
    document.getElementById("overview-sidebar-title").textContent = event.title || "Overview";
    document.getElementById("overview-sidebar-subtitle").textContent = formatDateTimeRange(event.start_datetime, event.end_datetime, event.date);
    document.getElementById("overview-event-name").textContent = event.title || "Event";
    document.getElementById("overview-event-when").textContent = formatDateTimeRange(event.start_datetime, event.end_datetime, event.date);
    document.getElementById("overview-event-description").textContent = event.description || "No description yet.";
    document.getElementById("overview-location").textContent = event.location || "Not set";
    document.getElementById("overview-guests").textContent = String(event.guest_count || 0);
    document.getElementById("overview-schedule").textContent = formatDateTimeRange(event.start_datetime, event.end_datetime, event.date);
    document.getElementById("overview-budget-total").textContent = formatCurrency(Number(event.budget_total || 0));
    document.getElementById("overview-total-tasks").textContent = String(tasks.length);
    document.getElementById("overview-completed-tasks").textContent = String(completedTasks);
    document.getElementById("overview-pending-tasks").textContent = String(pendingTasks);
    document.getElementById("overview-agenda-count").textContent = String(agenda.length);

    document.getElementById("overview-planner-link").href = `planner.html?event_id=${event.id}`;
    document.getElementById("overview-budget-link").href = `budget.html?event_id=${event.id}`;
    document.getElementById("overview-open-planner").href = `planner.html?event_id=${event.id}`;
    document.getElementById("overview-open-budget").href = `budget.html?event_id=${event.id}`;

    renderTaskSnapshot(tasks);
    renderAgendaSnapshot(agenda);
}

function renderTaskSnapshot(tasks) {
    const container = document.getElementById("overview-tasks-list");
    if (!tasks.length) {
        container.innerHTML = `<div class="empty-state compact-empty-state"><h3>No tasks yet</h3><p>Add tasks in the planner page.</p></div>`;
        return;
    }

    const sorted = [...tasks].sort((a, b) => (a.start_datetime || a.due_date || "").localeCompare(b.start_datetime || b.due_date || ""));
    container.innerHTML = `
        <ul class="task-list selected-task-list">
            ${sorted.slice(0, 6).map(task => `
                <li class="task-item overview-list-item">
                    <div class="task-main">
                        <span class="${Number(task.completed) === 1 ? "completed-task" : ""}">${escapeHtml(task.title)}</span>
                        <span class="task-date">${formatDateTimeRange(task.start_datetime, task.end_datetime, task.due_date)}</span>
                    </div>
                </li>
            `).join("")}
        </ul>
    `;
}

function renderAgendaSnapshot(agenda) {
    const container = document.getElementById("overview-agenda-list");
    if (!agenda.length) {
        container.innerHTML = `<div class="empty-state compact-empty-state"><h3>No agenda yet</h3><p>Add agenda items in the planner page.</p></div>`;
        return;
    }

    container.innerHTML = agenda.slice(0, 6).map(item => `
        <div class="agenda-card overview-agenda-card">
            <div class="agenda-card-header">
                <div>
                    <h4>${escapeHtml(item.title)}</h4>
                    <p class="muted-text">${formatAgendaSchedule(item)}</p>
                </div>
            </div>
            ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}
        </div>
    `).join("");
}

function showOverviewError(message) {
    document.getElementById("overview-error").classList.remove("hidden");
    document.getElementById("overview-content").classList.add("hidden");
    document.getElementById("overview-error").innerHTML = `<h2>Overview unavailable</h2><p>${escapeHtml(message)}</p>`;
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

document.getElementById("overview-back-btn")?.addEventListener("click", () => {
    window.location.href = "dashboard.html";
});

initializeOverview();
