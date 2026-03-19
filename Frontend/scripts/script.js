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
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok) {
            messageEl.textContent = data.message;

            localStorage.setItem("loggedInUser", JSON.stringify(data.user));

            window.location.href = "/Frontend/pages/dashboard.html";
        } else {
            messageEl.textContent = data.error || "Login failed.";
        }
    } catch (error) {
        console.error("Login error:", error);
        messageEl.textContent = "Could not connect to the server.";
    }
});