const API_BASE = "http://127.0.0.1:5000";

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

    const container = document.getElementById("events-list");
    container.innerHTML = events.map((event) => `
        <div class="task-item">
            <strong>${escapeHtml(event.title)}</strong><br>
            Owner: ${escapeHtml(event.owner_name)} (${escapeHtml(event.owner_email)})<br>
            Date: ${escapeHtml(event.start_datetime || event.date || "N/A")}<br>
            Location: ${escapeHtml(event.location || "N/A")}
        </div>
    `).join("");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
