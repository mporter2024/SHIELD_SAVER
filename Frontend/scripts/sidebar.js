function loadSidebar(activePage, title = "Admin", subtitle = "System overview") {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    sidebar.innerHTML = `
        <div class="brand">
            <img src="../logo.png" alt="Shield Saver Logo" class="brand-logo">
            <div>
                <h2>Spartan Shield Saver</h2>
                <p>Administrative View</p>
            </div>
        </div>

        <div class="profile-card">
            <h3 id="sidebar-title">${title}</h3>
            <p id="sidebar-subtitle" class="muted-text">${subtitle}</p>
        </div>

        <nav class="sidebar-nav">
            <h3>Navigation</h3>
            <a href="dashboard.html" data-page="dashboard">Dashboard</a>
            <a href="planner.html" data-page="planner">Planning</a>
            <a href="budget.html" data-page="budget">Budget Calculator</a>
            <a href="admin.html" data-page="admin">Admin</a>
        </nav>

        <div class="sidebar-actions">
            <button id="sidebar-refresh-btn" class="secondary-btn" type="button">Refresh</button>
            <button id="sidebar-logout-btn" class="danger-btn" type="button">Logout</button>
        </div>
    `;

    sidebar.querySelectorAll(".sidebar-nav a").forEach((link) => {
        if (link.dataset.page === activePage) {
            link.classList.add("active");
        }
    });

    const refreshBtn = document.getElementById("sidebar-refresh-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => window.location.reload());
    }

    const logoutBtn = document.getElementById("sidebar-logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            try {
                await fetch("http://127.0.0.1:5000/api/users/logout", {
                    method: "POST",
                    credentials: "include"
                });
            } catch (error) {
                console.error("Logout failed:", error);
            }

            localStorage.removeItem("selectedEventId");
            window.location.href = "index.html";
        });
    }
}
