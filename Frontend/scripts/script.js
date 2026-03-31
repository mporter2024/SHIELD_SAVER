const API_BASE = "http://127.0.0.1:5000";

const loginForm = document.getElementById("login-form");
const messageEl = document.getElementById("message");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();

    messageEl.textContent = "Logging in...";

    try {
       const response = await fetch("http://127.0.0.1:5000/api/users/login", {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    credentials: "include",
    body: JSON.stringify({
        email,
        password
    })
});

const data = await response.json();

if (!response.ok) {
    alert(data.error || "Login failed.");
    return;
}

localStorage.setItem("user", JSON.stringify(data.user));

if (data.user.role === "admin") {
    window.location.href = "admin.html";
} else {
    window.location.href = "dashboard.html";
} 
    } catch (error) {
        console.error("Login error:", error);
        messageEl.textContent = "Could not connect to the server.";
    }
});

async function checkExistingSession() {
    try {
        const response = await fetch(`${API_BASE}/api/users/me`, {
            method: "GET",
            credentials: "include"
        });

        if (response.ok) {
            window.location.href = "dashboard.html";
        }
    } catch (error) {
        console.error("Session check failed:", error);
    }
}

checkExistingSession();