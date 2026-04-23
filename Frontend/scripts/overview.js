const API_BASE = "http://127.0.0.1:5000";

let selectedEventId = null;

function getEventIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("event_id") || localStorage.getItem("selectedEventId");
}

async function loadEventSelector() {
    const dropdown = document.getElementById("event-selector");

    try {
        const response = await fetch(`${API_BASE}/api/events`, {
            method: "GET",
            credentials: "include"
        });

        const data = await response.json();
        const events = data.events || [];

        if (!events.length) {
            document.getElementById("overview-error").classList.remove("hidden");
            document.getElementById("overview-error").innerHTML = `
                <h2>No events found</h2>
                <p>Create an event on the dashboard to get started.</p>
            `;
            return;
        }

        dropdown.innerHTML = events.map(e => `
            <option value="${e.id}">${e.title}</option>
        `).join("");

        selectedEventId = selectedEventId || events[0].id;

        dropdown.addEventListener("change", (e) => {
            const newId = e.target.value;
            localStorage.setItem("selectedEventId", newId);
            window.location.href = `overview.html?event_id=${newId}`;
        });

    } catch (err) {
        console.error(err);
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    selectedEventId = getEventIdFromUrl();
    await loadEventSelector();
});
