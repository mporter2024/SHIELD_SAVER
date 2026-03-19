const registerForm = document.getElementById("register-form");
const messageEl = document.getElementById("message");
console.log("register.js loaded");
registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const name = document.getElementById("name").value.trim();
    const username = document.getElementById("username").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();

    const confirmPassword = document.getElementById("confirm-password").value.trim();

if (password !== confirmPassword) {
    messageEl.textContent = "Passwords do not match.";
    return;
}

    messageEl.textContent = "Creating account...";

    try {
        const response = await fetch("http://127.0.0.1:5000/api/users/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                username: username,
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok) {
            messageEl.textContent = "Account created successfully! Redirecting to login...";
            setTimeout(() => {
                window.location.href = "/Frontend/pages/index.html";
            }, 1500);
        } else {
            messageEl.textContent = data.error || "Registration failed.";
        }
    } catch (error) {
        console.error("Registration error:", error);
        messageEl.textContent = "Could not connect to the server.";
    }
});