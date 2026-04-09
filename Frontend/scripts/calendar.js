const API_BASE = "http://127.0.0.1:5000";

let currentMonthDate = new Date();
let calendarItems = [];
let selectedDateKey = null;
let quickAddMode = "event";

const filters = {
    events: true,
    tasks: true,
    agendas: true,
    search: ""
};

document.getElementById("prev-month-btn").addEventListener("click", () => {
    currentMonthDate = new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() - 1, 1);
    renderCalendar();
});

document.getElementById("next-month-btn").addEventListener("click", () => {
    currentMonthDate = new Date(currentMonthDate.getFullYear(), currentMonthDate.getMonth() + 1, 1);
    renderCalendar();
});

document.getElementById("calendar-refresh-btn").addEventListener("click", initializeCalendar);
document.getElementById("calendar-back-btn").addEventListener("click", () => {
    window.location.href = "dashboard.html";
});
document.getElementById("calendar-logout-btn").addEventListener("click", logout);

document.getElementById("filter-events").addEventListener("change", (e) => {
    filters.events = e.target.checked;
    rerenderCalendarViews();
});

document.getElementById("filter-tasks").addEventListener("change", (e) => {
    filters.tasks = e.target.checked;
    rerenderCalendarViews();
});

document.getElementById("filter-agendas").addEventListener("change", (e) => {
    filters.agendas = e.target.checked;
    rerenderCalendarViews();
});

document.getElementById("calendar-search").addEventListener("input", (e) => {
    filters.search = e.target.value.trim().toLowerCase();
    rerenderCalendarViews();
});

document.getElementById("today-btn").addEventListener("click", () => {
    const today = new Date();
    currentMonthDate = new Date(today.getFullYear(), today.getMonth(), 1);
    selectedDateKey = toDateKey(today.getFullYear(), today.getMonth(), today.getDate());
    rerenderCalendarViews();
    syncQuickAddDateMessage();
});

document.getElementById("clear-filters-btn").addEventListener("click", () => {
    document.getElementById("calendar-search").value = "";
    filters.search = "";
    rerenderCalendarViews();
});

document.getElementById("toggle-quick-add-btn").addEventListener("click", () => {
    const panel = document.getElementById("quick-add-panel");

    if (!selectedDateKey) {
        setQuickAddMessage("Select a date before adding an item.", true);
        return;
    }

    panel.classList.toggle("hidden");
    syncQuickAddDateMessage();
});

document.getElementById("quick-add-event-tab").addEventListener("click", () => {
    quickAddMode = "event";
    updateQuickAddTabs();
});

document.getElementById("quick-add-task-tab").addEventListener("click", () => {
    quickAddMode = "task";
    updateQuickAddTabs();
});

document.getElementById("quick-add-event-form").addEventListener("submit", handleQuickAddEvent);
document.getElementById("quick-add-task-form").addEventListener("submit", handleQuickAddTask);

initializeCalendar();

async function initializeCalendar() {
    try {
        const user = await fetchCurrentUser();
        localStorage.setItem("user", JSON.stringify(user));
        document.getElementById("calendar-sidebar-title").textContent = user.name || "Calendar";

        const adminLink = document.getElementById("admin-nav-link");
        if (adminLink) {
            adminLink.style.display = user.role === "admin" ? "block" : "none";
        }

        await refreshCalendarData();

        if (!selectedDateKey) {
            const today = new Date();
            selectedDateKey = toDateKey(today.getFullYear(), today.getMonth(), today.getDate());
        }

        rerenderCalendarViews();
        syncQuickAddDateMessage();
    } catch (error) {
        console.error("Calendar initialization failed:", error);
        window.location.href = "index.html";
    }
}

async function refreshCalendarData() {
    const events = await fetchMyEvents();
    const tasks = await fetchMyTasks();
    const agendaByEvent = await fetchAgendaForEvents(events);
    calendarItems = normalizeCalendarItems(events, tasks, agendaByEvent);
}

async function fetchCurrentUser() {
    const response = await fetch(`${API_BASE}/api/users/me`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Not logged in");
    return data.user;
}

async function fetchMyEvents() {
    const response = await fetch(`${API_BASE}/api/events/mine`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load events");
    return data;
}

async function fetchMyTasks() {
    const response = await fetch(`${API_BASE}/api/tasks/mine`, {
        method: "GET",
        credentials: "include"
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load tasks");
    return data;
}

async function fetchAgendaForEvents(events) {
    const results = {};

    await Promise.all(
        events.map(async (event) => {
            try {
                const response = await fetch(`${API_BASE}/api/agenda/event/${event.id}`, {
                    method: "GET",
                    credentials: "include"
                });

                const data = await response.json();
                results[event.id] = response.ok ? data : [];
            } catch (error) {
                console.error(`Could not load agenda for event ${event.id}:`, error);
                results[event.id] = [];
            }
        })
    );

    return results;
}

function normalizeCalendarItems(events, tasks, agendaByEvent) {
    const items = [];

    events.forEach((event) => {
        const eventDateKey = extractDateKey(event.start_datetime || event.date);
        if (eventDateKey) {
            items.push({
                type: "event",
                dateKey: eventDateKey,
                title: event.title,
                subtitle: event.location || "No location",
                meta: formatEventRange(event),
                eventId: event.id
            });
        }

        const agendaItems = agendaByEvent[event.id] || [];
        agendaItems.forEach((agendaItem) => {
            if (!eventDateKey) return;

            items.push({
                type: "agenda",
                dateKey: eventDateKey,
                title: agendaItem.title,
                subtitle: event.title,
                meta: formatAgendaRange(agendaItem),
                eventId: event.id
            });
        });
    });

    tasks.forEach((task) => {
        const taskDateKey = extractDateKey(task.start_datetime || task.due_date);
        if (!taskDateKey) return;

        items.push({
            type: "task",
            dateKey: taskDateKey,
            title: task.title,
            subtitle: Number(task.completed) === 1 ? "Completed" : "Pending",
            meta: formatTaskRange(task),
            eventId: task.event_id
        });
    });

    return items.sort((a, b) => {
        if (a.dateKey !== b.dateKey) return a.dateKey.localeCompare(b.dateKey);
        return a.title.localeCompare(b.title);
    });
}

function getFilteredItems() {
    return calendarItems.filter((item) => {
        const matchesType =
            (item.type === "event" && filters.events) ||
            (item.type === "task" && filters.tasks) ||
            (item.type === "agenda" && filters.agendas);

        if (!matchesType) return false;

        if (!filters.search) return true;

        const searchableText = [item.title, item.subtitle, item.meta, item.type]
            .join(" ")
            .toLowerCase();

        return searchableText.includes(filters.search);
    });
}

function rerenderCalendarViews() {
    renderCalendar();
    renderSelectedDay();
}

function renderCalendar() {
    const grid = document.getElementById("calendar-grid");
    const monthLabel = document.getElementById("calendar-month-label");

    const year = currentMonthDate.getFullYear();
    const month = currentMonthDate.getMonth();

    monthLabel.textContent = currentMonthDate.toLocaleDateString(undefined, {
        month: "long",
        year: "numeric"
    });

    const firstDayOfMonth = new Date(year, month, 1);
    const startWeekday = firstDayOfMonth.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const filteredItems = getFilteredItems();

    const cells = [];

    for (let i = 0; i < startWeekday; i++) {
        cells.push(`<div class="calendar-cell empty"></div>`);
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const dateKey = toDateKey(year, month, day);
        const itemsForDay = filteredItems.filter(item => item.dateKey === dateKey);
        const isSelected = selectedDateKey === dateKey;

        cells.push(`
            <button class="calendar-cell ${isSelected ? "selected" : ""}" type="button" onclick="selectCalendarDay('${dateKey}')">
                <div class="calendar-date-number-row">
                    <div class="calendar-date-number">${day}</div>
                    ${isToday(dateKey) ? `<span class="today-badge">Today</span>` : ""}
                </div>
                <div class="calendar-cell-items">
                    ${itemsForDay.slice(0, 3).map(item => `
                        <div class="calendar-item-chip ${item.type}">
                            ${escapeHtml(item.title)}
                        </div>
                    `).join("")}
                    ${itemsForDay.length > 3 ? `<div class="calendar-more">+${itemsForDay.length - 3} more</div>` : ""}
                </div>
            </button>
        `);
    }

    grid.innerHTML = cells.join("");
}

function selectCalendarDay(dateKey) {
    selectedDateKey = dateKey;
    renderCalendar();
    renderSelectedDay();
    syncQuickAddDateMessage();
}

window.selectCalendarDay = selectCalendarDay;

function renderSelectedDay() {
    const label = document.getElementById("selected-day-label");
    const container = document.getElementById("selected-day-items");

    if (!selectedDateKey) {
        label.textContent = "Click a date to view details.";
        container.innerHTML = `
            <div class="empty-state compact-empty-state">
                <h3>No day selected</h3>
                <p>Choose a date on the calendar to see its scheduled items.</p>
            </div>
        `;
        return;
    }

    const items = getFilteredItems().filter(item => item.dateKey === selectedDateKey);

    label.textContent = formatLongDate(selectedDateKey);

    if (!items.length) {
        container.innerHTML = `
            <div class="empty-state compact-empty-state">
                <h3>No matching items</h3>
                <p>There are no visible events, tasks, or agenda items for this date with the current filters.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="calendar-detail-card ${item.type}">
            <div class="calendar-detail-top">
                <div>
                    <h3>${escapeHtml(item.title)}</h3>
                    <p class="muted-text">${escapeHtml(item.subtitle || "")}</p>
                    <p>${escapeHtml(item.meta || "")}</p>
                </div>
                <span class="calendar-type-badge ${item.type}">
                    ${capitalize(item.type)}
                </span>
            </div>
            ${item.eventId ? `<a href="planner.html?event_id=${item.eventId}">Open related planner</a>` : ""}
        </div>
    `).join("");
}

function updateQuickAddTabs() {
    const eventTab = document.getElementById("quick-add-event-tab");
    const taskTab = document.getElementById("quick-add-task-tab");
    const eventForm = document.getElementById("quick-add-event-form");
    const taskForm = document.getElementById("quick-add-task-form");

    const eventActive = quickAddMode === "event";

    eventTab.classList.toggle("active", eventActive);
    taskTab.classList.toggle("active", !eventActive);
    eventForm.classList.toggle("hidden", !eventActive);
    taskForm.classList.toggle("hidden", eventActive);
}

function syncQuickAddDateMessage() {
    const messageBox = document.getElementById("quick-add-message");

    if (!selectedDateKey) {
        messageBox.textContent = "Select a date to add an event or task.";
        messageBox.classList.remove("error-text");
        return;
    }

    messageBox.textContent = `Adding to ${formatLongDate(selectedDateKey)}`;
    messageBox.classList.remove("error-text");
}

function setQuickAddMessage(message, isError = false) {
    const messageBox = document.getElementById("quick-add-message");
    messageBox.textContent = message;
    messageBox.classList.toggle("error-text", isError);
}

function getSelectedDayEventIds() {
    return calendarItems
        .filter(item => item.type === "event" && item.dateKey === selectedDateKey && item.eventId)
        .map(item => item.eventId);
}

async function handleQuickAddEvent(e) {
    e.preventDefault();

    if (!selectedDateKey) {
        setQuickAddMessage("Select a date first.", true);
        return;
    }

    const title = document.getElementById("quick-event-title").value.trim();
    const locationInput = document.getElementById("quick-event-location").value.trim();
    const startTime = document.getElementById("quick-event-start-time").value;
    const endTime = document.getElementById("quick-event-end-time").value;

    if (!title) {
        setQuickAddMessage("Event title is required.", true);
        return;
    }

    const payload = {
        title,
        location: locationInput || "TBD",
        description: "Created from calendar quick add.",
        start_datetime: combineDateAndTime(selectedDateKey, startTime || "09:00"),
        end_datetime: combineDateAndTime(selectedDateKey, endTime || startTime || "10:00")
    };

    try {
        const response = await fetch(`${API_BASE}/api/events/`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not create event");
        }

        document.getElementById("quick-add-event-form").reset();
        setQuickAddMessage("Event created successfully.");
        await refreshCalendarData();
        rerenderCalendarViews();
    } catch (error) {
        console.error("Quick add event failed:", error);
        setQuickAddMessage(error.message || "Could not create event.", true);
    }
}

async function handleQuickAddTask(e) {
    e.preventDefault();

    if (!selectedDateKey) {
        setQuickAddMessage("Select a date first.", true);
        return;
    }

    const eventIdsForDay = getSelectedDayEventIds();

    if (eventIdsForDay.length === 0) {
        setQuickAddMessage("Create an event on this date first, then add tasks to it.", true);
        return;
    }

    if (eventIdsForDay.length > 1) {
        setQuickAddMessage("This date has multiple events. Add the task from the Planner page for the correct event.", true);
        return;
    }

    const title = document.getElementById("quick-task-title").value.trim();
    const completed = Number(document.getElementById("quick-task-status").value);
    const startTime = document.getElementById("quick-task-start-time").value;
    const endTime = document.getElementById("quick-task-end-time").value;

    if (!title) {
        setQuickAddMessage("Task title is required.", true);
        return;
    }

    const payload = {
        title,
        completed,
        event_id: eventIdsForDay[0],
        start_datetime: combineDateAndTime(selectedDateKey, startTime || "09:00"),
        end_datetime: combineDateAndTime(selectedDateKey, endTime || startTime || "10:00"),
        due_date: selectedDateKey
    };

    try {
        const response = await fetch(`${API_BASE}/api/tasks/`, {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not create task");
        }

        document.getElementById("quick-add-task-form").reset();
        setQuickAddMessage("Task created successfully.");
        await refreshCalendarData();
        rerenderCalendarViews();
    } catch (error) {
        console.error("Quick add task failed:", error);
        setQuickAddMessage(error.message || "Could not create task.", true);
    }
}

function combineDateAndTime(dateKey, timeValue) {
    return `${dateKey}T${timeValue}:00`;
}

function formatEventRange(event) {
    const start = event.start_datetime ? formatDateTime(event.start_datetime) : "No start time";
    const end = event.end_datetime ? formatDateTime(event.end_datetime) : "No end time";
    return `${start} → ${end}`;
}

function formatTaskRange(task) {
    if (task.start_datetime || task.end_datetime) {
        const start = task.start_datetime ? formatDateTime(task.start_datetime) : "No start time";
        const end = task.end_datetime ? formatDateTime(task.end_datetime) : "No end time";
        return `${start} → ${end}`;
    }

    if (task.due_date) {
        return `Due: ${formatLongDate(task.due_date)}`;
    }

    return "No date";
}

function formatAgendaRange(item) {
    if (item.start_time || item.end_time) {
        return `${item.start_time || "No start"} → ${item.end_time || "No end"}`;
    }
    return "Agenda item";
}

function formatDateTime(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;

    return parsed.toLocaleString([], {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit"
    });
}

function formatLongDate(dateKey) {
    const [year, month, day] = dateKey.split("-").map(Number);
    const date = new Date(year, month - 1, day);

    return date.toLocaleDateString([], {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric"
    });
}

function extractDateKey(value) {
    if (!value) return null;

    if (typeof value === "string" && value.includes("T")) {
        return value.split("T")[0];
    }

    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
        return value;
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;

    return toDateKey(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function toDateKey(year, monthIndex, day) {
    const y = String(year);
    const m = String(monthIndex + 1).padStart(2, "0");
    const d = String(day).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function isToday(dateKey) {
    const now = new Date();
    const todayKey = toDateKey(now.getFullYear(), now.getMonth(), now.getDate());
    return dateKey === todayKey;
}

async function logout() {
    try {
        await fetch(`${API_BASE}/api/users/logout`, {
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

function capitalize(value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.initializeCalendar = initializeCalendar;
window.refreshCalendarData = refreshCalendarData;
window.rerenderCalendarViews = rerenderCalendarViews;

function syncCalendarToAiAction(data) {
    const relatedEventId = data?.event?.id || data?.event_id || data?.task?.event_id;
    if (!relatedEventId) return;

    const matchingItem = calendarItems.find((item) => Number(item.event_id) === Number(relatedEventId) || (item.type === "event" && Number(item.id) === Number(relatedEventId)));
    if (matchingItem && matchingItem.dateKey) {
        selectedDateKey = matchingItem.dateKey;
        const [year, month, day] = matchingItem.dateKey.split("-").map(Number);
        currentMonthDate = new Date(year, month - 1, 1);
    }
}

window.addEventListener("shield-ai-action", async (event) => {
    const data = event.detail || {};
    await refreshCalendarData();
    syncCalendarToAiAction(data);
    rerenderCalendarViews();
    syncQuickAddDateMessage();
});
