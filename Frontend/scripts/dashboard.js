const API_BASE = "http://127.0.0.1:5000";

async function loadDashboard() {
    try {
        const response = await fetch(`${API_BASE}/api/users/me`, {
            method: "GET",
            credentials: "include"
        });

        const data = await response.json();

        if (!response.ok) {
            window.location.href = "index.html";
            return;
        }

        document.getElementById("welcome-message").textContent =
            `Welcome, ${data.user.name}!`;
    } catch (error) {
        console.error("Dashboard error:", error);
        window.location.href = "index.html";
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/api/users/logout`, {
            method: "POST",
            credentials: "include"
        });
    } catch (error) {
        console.error("Logout error:", error);
    }

    window.location.href = "index.html";
}

document.getElementById("logout-btn").addEventListener("click", logout);

loadDashboard();