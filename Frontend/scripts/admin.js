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
        loadSidebar("admin", "Admin", `${user.name} • system overview`);
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

    container.innerHTML = filteredEvents.map(event => `
        <div class="admin-event-card">
            <h3>${escapeHtml(event.title)}</h3>

            <p><strong>Owner:</strong> ${escapeHtml(event.owner_name)} (${escapeHtml(event.owner_email)})</p>
            <p><strong>Date:</strong> ${escapeHtml(event.start_datetime || event.date || "N/A")}</p>
            <p><strong>Location:</strong> ${escapeHtml(event.location || "N/A")}</p>
        </div>
    `).join("");
}