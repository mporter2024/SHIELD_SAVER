// If already logged in, redirect to dashboard
if (window.location.pathname.includes("index.html") || window.location.pathname === "/") {
  const user = localStorage.getItem("user");
  if (user) {
    window.location.href = "dashboard.html";
  }
}

// Protect dashboard
if (window.location.pathname.includes("dashboard.html")) {
  const user = localStorage.getItem("user");

  if (!user) {
    window.location.href = "index.html";
  } else {
    document.getElementById("welcome").innerText = "Welcome, " + user;
  }
}

function login() {
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  // Demo credentials
  if (username === "demo" && password === "1234") {
    localStorage.setItem("user", username);
    window.location.href = "dashboard.html";
  } else {
    alert("Invalid login");
  }
}

function logout() {
  localStorage.removeItem("user");
  window.location.href = "index.html";
}
