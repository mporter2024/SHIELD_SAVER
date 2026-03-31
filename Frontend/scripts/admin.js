document.addEventListener("DOMContentLoaded", async () => {
    const user = JSON.parse(localStorage.getItem("user"));

    if (!user || user.role !== "admin") {
        alert("Access denied.");
        window.location.href = "dashboard.html";
        return;
    }

    loadSidebar("admin", "Admin", "System overview");

    await loadAdminStats(user);
    await loadUsers(user);
    await loadEvents(user);
});

async function loadAdminStats(user) {
    const response = await fetch("http://127.0.0.1:5000/api/admin/stats", {
        headers: {
            "Content-Type": "application/json",
            "X-User-Role": user.role
        }
    });

    const data = await response.json();

    document.getElementById("total-users").textContent = data.total_users ?? 0;
    document.getElementById("total-events").textContent = data.total_events ?? 0;
    document.getElementById("total-tasks").textContent = data.total_tasks ?? 0;
}

async function loadUsers(user) {
    const response = await fetch("http://127.0.0.1:5000/api/admin/users", {
        headers: {
            "Content-Type": "application/json",
            "X-User-Role": user.role
        }
    });

    const users = await response.json();
    const container = document.getElementById("users-list");

    container.innerHTML = users.map(u => `
        <div class="task-item">
            <strong>${u.name}</strong><br>
            Username: ${u.username}<br>
            Email: ${u.email}<br>
            Role: ${u.role}
        </div>
    `).join("");
}

async function loadEvents(user) {
    const response = await fetch("http://127.0.0.1:5000/api/admin/events", {
        headers: {
            "Content-Type": "application/json",
            "X-User-Role": user.role
        }
    });

    const events = await response.json();
    const container = document.getElementById("events-list");

    container.innerHTML = events.map(event => `
        <div class="task-item">
            <strong>${event.name}</strong><br>
            Owner: ${event.owner_name} (${event.owner_email})<br>
            Date: ${event.date || "N/A"}<br>
            Location: ${event.location || "N/A"}
        </div>
    `).join("");
}