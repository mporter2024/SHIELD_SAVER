async function loadSidebar(activePage, title = "Welcome", subtitle = "Manage your events") {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    sidebar.innerHTML = `
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

    const refreshBtn = document.getElementById("refresh-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            window.location.reload();
        });
    }

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            localStorage.removeItem("user");
            localStorage.removeItem("selectedEventId");
            window.location.href = "index.html";
        });
    }
}