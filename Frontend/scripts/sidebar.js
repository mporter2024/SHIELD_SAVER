const SIDEBAR_API_BASE = "http://127.0.0.1:5000";

function getSelectedEventId() {
    return localStorage.getItem("selectedEventId") || localStorage.getItem("last_ai_event_id");
}

function buildEventAwareHref(page) {
    const eventId = getSelectedEventId();
    if (!eventId) return `${page}.html`;
    if (["overview", "planner", "budget"].includes(page)) {
        return `${page}.html?event_id=${eventId}`;
    }
    return `${page}.html`;
}

async function resolveSidebarUser() {
    const cachedUser = JSON.parse(localStorage.getItem("user") || "null");
    if (cachedUser) return cachedUser;

    try {
        const response = await fetch(`${SIDEBAR_API_BASE}/api/users/me`, {
            method: "GET",
            credentials: "include"
        });
        const data = await response.json();
        if (!response.ok) return null;
        if (data.user) {
            localStorage.setItem("user", JSON.stringify(data.user));
            return data.user;
        }
    } catch (error) {
        console.error("Sidebar user lookup failed:", error);
    }

    return null;
}

async function loadSidebar(activePage, title = "Welcome", subtitle = "Manage your events", options = {}) {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return null;

    const {
        brandSubtitle = "Event Planning",
        links = [
            { page: "dashboard", label: "Dashboard" },
            { page: "overview", label: "Event Overview" },
            { page: "planner", label: "Planning" },
            { page: "budget", label: "Budget Calculator" },
            { page: "calendar", label: "Calendar" },
            { page: "admin", label: "Admin", adminOnly: true }
        ],
        actions = [
            { id: "refresh-btn", label: "Refresh", className: "secondary-btn", action: "reload" },
            { id: "logout-btn", label: "Logout", className: "danger-btn", action: "logout" }
        ]
    } = options;

    const user = await resolveSidebarUser();

    const navHtml = links
        .filter((link) => !link.adminOnly || user?.role === "admin")
        .map((link) => {
            const href = link.href || buildEventAwareHref(link.page);
            const activeClass = link.page === activePage ? "active" : "";
            return `<a href="${href}" data-page="${link.page}" class="${activeClass}">${link.label}</a>`;
        })
        .join("");

    const actionsHtml = actions
        .map((button) => `
            <button id="${button.id}" class="${button.className || "secondary-btn"}" type="button" data-action="${button.action || ""}" ${button.href ? `data-href="${button.href}"` : ""}>${button.label}</button>
        `)
        .join("");

    sidebar.innerHTML = `
        <div class="brand">
            <img src="../logo.png" alt="Shield Saver Logo" class="brand-logo">
            <div>
                <h2>Spartan Shield Saver</h2>
                <p>${brandSubtitle}</p>
            </div>
        </div>

        <div class="profile-card">
            <h3 id="sidebar-title">${title}</h3>
            <p id="sidebar-subtitle" class="muted-text">${subtitle}</p>
            ${user ? `<p id="sidebar-user-email" class="muted-text sidebar-user-email">${user.email || ""}</p>` : ""}
        </div>

        <nav class="sidebar-nav">
            <h3>Navigation</h3>
            ${navHtml}
        </nav>

        <div class="sidebar-actions">
            ${actionsHtml}
        </div>
    `;

    sidebar.querySelectorAll(".sidebar-actions button").forEach((button) => {
        button.addEventListener("click", async () => {
            const action = button.dataset.action;
            const href = button.dataset.href;

            if (action === "reload") {
                window.location.reload();
                return;
            }

            if (action === "go" && href) {
                window.location.href = href;
                return;
            }

            if (action === "logout") {
                try {
                    await fetch(`${SIDEBAR_API_BASE}/api/users/logout`, {
                        method: "POST",
                        credentials: "include"
                    });
                } catch (error) {
                    console.error("Logout request failed:", error);
                }

                localStorage.removeItem("user");
                localStorage.removeItem("selectedEventId");
                window.location.href = "index.html";
            }
        });
    });

    return user;
}

window.loadSidebar = loadSidebar;
window.resolveSidebarUser = resolveSidebarUser;
