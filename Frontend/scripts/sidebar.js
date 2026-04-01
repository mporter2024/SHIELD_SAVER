function loadSidebar(activePage, title = "Welcome", subtitle = "Manage your events") {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    const user = JSON.parse(localStorage.getItem("user"));

    sidebar.innerHTML = `
    const user = JSON.parse(localStorage.getItem("user"));

// Show admin link only if admin
if (user && user.role === "admin") {
    const adminLink = document.getElementById("admin-link");
    if (adminLink) {
        adminLink.style.display = "block";
    }
}
        <div class="brand">
            <img src="../logo.png" alt="Shield Saver Logo" class="brand-logo">
            <div>
                <h2>Spartan Shield Saver</h2>
                <p>Event Planning</p>
            </div>
        </div>

        <div class="profile-card">
            <h3 id="sidebar-title">Welcome</h3>
            <p id="sidebar-subtitle" class="muted-text">Manage your events</p>
        </div>

  <nav class="sidebar-nav">
    <h3>Navigation</h3>
    <a href="dashboard.html" data-page="dashboard">Dashboard</a>
    <a href="planner.html" data-page="planner">Planning</a>
    <a href="budget.html" data-page="budget">Budget Calculator</a>
    <a href="admin.html" data-page="admin" id="admin-link" style="display:none;">Admin</a>
</nav>     

        <div class="sidebar-actions">
            <button id="refresh-btn" class="secondary-btn" type="button">Refresh</button>
            <button id="logout-btn" class="danger-btn" type="button">Logout</button>
        </div>
    `;

    const titleEl = document.getElementById("sidebar-title");
    const subtitleEl = document.getElementById("sidebar-subtitle");

    if (titleEl) titleEl.textContent = title;
    if (subtitleEl) subtitleEl.textContent = subtitle;

    document.querySelectorAll(".sidebar-nav a").forEach(link => {
        if (link.dataset.page === activePage) {
            link.classList.add("active");
        }
    });

    if (user && user.role === "admin") {
        const adminLink = document.getElementById("admin-link");
        if (adminLink) {
            adminLink.style.display = "block";
        }
    }

    const refreshBtn = document.getElementById("refresh-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            window.location.reload();
        });
    }

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            try {
                await fetch("http://127.0.0.1:5000/api/users/logout", {
                    method: "POST",
                    credentials: "include"
                });
            } catch (error) {
                console.error("Logout request failed:", error);
            }

            localStorage.removeItem("user");
            localStorage.removeItem("selectedEventId");
            window.location.href = "index.html";
        });
    }
}