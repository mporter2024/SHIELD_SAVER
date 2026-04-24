const API_BASE = "http://127.0.0.1:5000";
let allEvents = [];
let filteredEvents = [];
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const user = await fetchCurrentUser();
        if (user.role !== "admin") {
            alert("Access denied.");
            window.location.href = "dashboard.html";
            return;
        }
        await loadSidebar("admin", "Admin", `${user.name} • system overview`, { brandSubtitle: "Administration" });
        await loadAdminStats();
        await loadUsers();
        await loadEvents();
    } catch (error) {
        console.error("Admin page failed to load:", error);
        alert("You must be logged in as an admin to view this page.");
        window.location.href = "index.html";
    }
});

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

async function loadAdminStats() {
    const response = await fetch(`${API_BASE}/api/admin/stats`, {
        credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || "Could not load admin stats");
    }

    document.getElementById("total-users").textContent = data.total_users ?? 0;
    document.getElementById("total-events").textContent = data.total_events ?? 0;
    document.getElementById("total-tasks").textContent = data.total_tasks ?? 0;
    const agendaStat = document.getElementById("total-agenda-items");
    if (agendaStat) agendaStat.textContent = data.total_agenda_items ?? 0;
}

async function loadUsers() {
    const response = await fetch(`${API_BASE}/api/admin/users`, {
        credentials: "include"
    });
    const users = await response.json();
    if (!response.ok) {
        throw new Error(users.error || "Could not load users");
    }

    const container = document.getElementById("users-list");
    container.innerHTML = users.map((user) => `
        <div class="task-item">
            <strong>${escapeHtml(user.name)}</strong><br>
            Username: ${escapeHtml(user.username)}<br>
            Email: ${escapeHtml(user.email)}<br>
            Role: ${escapeHtml(user.role)}
        </div>
    `).join("");
}

async function loadEvents() {
    const response = await fetch(`${API_BASE}/api/admin/events`, {
        credentials: "include"
    });

    const events = await response.json();

    if (!response.ok) {
        throw new Error(events.error || "Could not load events");
    }

    allEvents = events;
    filteredEvents = [...events];

    setupEventControls();
    renderEvents();
}

function setupEventControls() {
    const searchInput = document.getElementById("event-search");
    const sortSelect = document.getElementById("event-sort");

    searchInput.addEventListener("input", applyFilters);
    sortSelect.addEventListener("change", applyFilters);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function applyFilters() {
    const searchValue = document.getElementById("event-search").value.toLowerCase();
    const sortValue = document.getElementById("event-sort").value;

    filteredEvents = allEvents.filter(event => {
        const text = `
            ${event.title}
            ${event.location}
            ${event.owner_name}
            ${event.owner_email}
            ${event.selected_venue}
            ${event.selected_catering}
            ${event.description}
        `.toLowerCase();

        return text.includes(searchValue);
    });

    // sorting
    if (sortValue === "newest") {
        filteredEvents.sort((a, b) => new Date(b.start_datetime || 0) - new Date(a.start_datetime || 0));
    }

    if (sortValue === "oldest") {
        filteredEvents.sort((a, b) => new Date(a.start_datetime || 0) - new Date(b.start_datetime || 0));
    }

    if (sortValue === "az") {
        filteredEvents.sort((a, b) => a.title.localeCompare(b.title));
    }

    if (sortValue === "za") {
        filteredEvents.sort((a, b) => b.title.localeCompare(a.title));
    }

    renderEvents();
}

function renderEvents() {
    const container = document.getElementById("events-list");
    const count = document.getElementById("event-count");

    count.textContent = `${filteredEvents.length} event(s) found`;

    if (!filteredEvents.length) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No events found</h3>
                <p>Try adjusting your search or filters.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filteredEvents.map(event => {
        const completed = Number(event.completed_task_count || 0);
        const totalTasks = Number(event.task_count || 0);
        const pending = Math.max(totalTasks - completed, 0);
        const budgetTotal = Number(event.budget_total || 0);
        const budgetLimit = Number(event.budget_limit || 0);
        const budgetText = budgetLimit > 0
            ? `${formatCurrency(budgetTotal)} of ${formatCurrency(budgetLimit)}`
            : formatCurrency(budgetTotal);
        const cateringCost = Number(event.estimated_catering_cost || 0);
        const venueCost = Number(event.estimated_venue_cost || 0);

        return `
            <div class="admin-event-card">
                <div class="admin-event-title-row">
                    <div>
                        <h3>${escapeHtml(event.title || "Untitled Event")}</h3>
                        <p class="muted-text">${escapeHtml(formatDateTimeRange(event.start_datetime, event.end_datetime, event.date))}</p>
                    </div>
                    <span class="admin-status-pill">${escapeHtml(Number(event.guest_count || 0))} guests</span>
                </div>

                <div class="admin-detail-grid">
                    <p><strong>Owner</strong><span>${escapeHtml(event.owner_name || "Unknown")} (${escapeHtml(event.owner_email || "No email")})</span></p>
                    <p><strong>Location</strong><span>${escapeHtml(event.location || "Not set")}</span></p>
                    <p><strong>Venue</strong><span>${escapeHtml(event.selected_venue || "Not selected")}${venueCost > 0 ? ` • ${formatCurrency(venueCost)}` : ""}</span></p>
                    <p><strong>Catering</strong><span>${escapeHtml(event.selected_catering || "Not selected")}${cateringCost > 0 ? ` • ${formatCurrency(cateringCost)}` : ""}</span></p>
                    <p><strong>Budget</strong><span>${escapeHtml(budgetText)}</span></p>
                    <p><strong>Planning</strong><span>${completed}/${totalTasks} tasks complete, ${pending} pending</span></p>
                    <p><strong>Agenda</strong><span>${Number(event.agenda_count || 0)} agenda item(s), ${Number(event.lineup_count || 0)} lineup entry/entries</span></p>
                    <p><strong>Next Agenda Time</strong><span>${escapeHtml(event.next_agenda_time || "Not scheduled")}</span></p>
                </div>

                ${event.description ? `<p class="admin-event-description"><strong>Description:</strong> ${escapeHtml(event.description)}</p>` : ""}
            </div>
        `;
    }).join("");
}

function formatDateTimeRange(startDateTime, endDateTime, fallbackDate) {
    if (startDateTime && endDateTime) return `${formatDateTime(startDateTime)} - ${formatDateTime(endDateTime)}`;
    if (startDateTime) return formatDateTime(startDateTime);
    if (fallbackDate) return formatDate(fallbackDate);
    return "No date";
}

function formatDate(dateString) {
    if (!dateString) return "No date";
    const date = new Date(`${dateString}T00:00:00`);
    if (Number.isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString();
}

function formatDateTime(dateTimeString) {
    if (!dateTimeString) return "";
    const date = new Date(dateTimeString);
    if (Number.isNaN(date.getTime())) return dateTimeString;
    return date.toLocaleString();
}

function formatCurrency(amount) {
    return `$${Number(amount || 0).toFixed(2)}`;
}
