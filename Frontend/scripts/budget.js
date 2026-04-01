const API_BASE = "http://127.0.0.1:5000";
let myEvents = [];
let myTasks = [];

function getNumberValue(id) {
  const value = parseFloat(document.getElementById(id).value);
  return isNaN(value) ? 0 : value;
}

function formatCurrency(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
}

function formatDate(dateString) {
  if (!dateString) return "No date";
  const date = new Date(`${dateString}T00:00:00`);
  return date.toLocaleDateString();
}

function formatDateTime(dateTimeString) {
  if (!dateTimeString) return "";
  const date = new Date(dateTimeString);
  if (Number.isNaN(date.getTime())) return dateTimeString;
  return date.toLocaleString();
}

function formatDateTimeRange(startDateTime, endDateTime, fallbackDate) {
  if (startDateTime && endDateTime) {
    return `${formatDateTime(startDateTime)} - ${formatDateTime(endDateTime)}`;
  }
  if (startDateTime) {
    return formatDateTime(startDateTime);
  }
  if (fallbackDate) {
    return formatDate(fallbackDate);
  }
  return "No date";
}

function getBudgetTip(total, guests) {
  if (guests === 0) {
    return "Enter a guest count to get a more realistic estimate.";
  }

  if (total < 500) {
    return "This looks like a lower-cost event. Double-check that you included all categories.";
  }

  if (total >= 500 && total < 2000) {
    return "This looks like a moderate event budget. Make sure your venue and food numbers are realistic.";
  }

  return "This is a higher-cost event. Consider reviewing large categories like venue, catering, and equipment.";
}

function calculateBudget() {
  const eventName = document.getElementById("event-name").value.trim() || "Untitled Event";
  const guests = getNumberValue("guest-count");
  const venue = getNumberValue("venue-cost");
  const foodPerPerson = getNumberValue("food-cost");
  const decorations = getNumberValue("decorations-cost");
  const equipment = getNumberValue("equipment-cost");
  const staff = getNumberValue("staff-cost");
  const marketing = getNumberValue("marketing-cost");
  const misc = getNumberValue("misc-cost");
  const contingencyPercent = getNumberValue("contingency-percent");

  const foodTotal = guests * foodPerPerson;
  const subtotal = venue + foodTotal + decorations + equipment + staff + marketing + misc;
  const contingency = subtotal * (contingencyPercent / 100);
  const total = subtotal + contingency;

  document.getElementById("summary-event").textContent = eventName;
  document.getElementById("summary-guests").textContent = guests;
  document.getElementById("summary-venue").textContent = formatCurrency(venue);
  document.getElementById("summary-food").textContent = formatCurrency(foodTotal);
  document.getElementById("summary-decorations").textContent = formatCurrency(decorations);
  document.getElementById("summary-equipment").textContent = formatCurrency(equipment);
  document.getElementById("summary-staff").textContent = formatCurrency(staff);
  document.getElementById("summary-marketing").textContent = formatCurrency(marketing);
  document.getElementById("summary-misc").textContent = formatCurrency(misc);
  document.getElementById("summary-subtotal").textContent = formatCurrency(subtotal);
  document.getElementById("summary-contingency").textContent = formatCurrency(contingency);
  document.getElementById("summary-total").textContent = formatCurrency(total);
  document.getElementById("budget-tip").textContent = getBudgetTip(total, guests);

  return {
    eventName,
    guests,
    venue,
    foodPerPerson,
    foodTotal,
    decorations,
    equipment,
    staff,
    marketing,
    misc,
    contingencyPercent,
    subtotal,
    contingency,
    total
  };
}

function resetBudgetForm() {
  document.getElementById("event-name").value = "";
  document.getElementById("guest-count").value = 50;
  document.getElementById("venue-cost").value = 300;
  document.getElementById("food-cost").value = 10;
  document.getElementById("decorations-cost").value = 100;
  document.getElementById("equipment-cost").value = 150;
  document.getElementById("staff-cost").value = 100;
  document.getElementById("marketing-cost").value = 75;
  document.getElementById("misc-cost").value = 50;
  document.getElementById("contingency-percent").value = 10;

  calculateBudget();
}

async function fetchMyEvents() {
  const response = await fetch(`${API_BASE}/api/events/mine`, {
    method: "GET",
    credentials: "include"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Could not load events");
  }

  return data;
}

async function fetchMyTasks() {
  const response = await fetch(`${API_BASE}/api/tasks/mine`, {
    method: "GET",
    credentials: "include"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Could not load tasks");
  }

  return data;
}

function getRequestedEventId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event_id");
}

function populateEventSelector(events) {
  const select = document.getElementById("event-select");

  if (!events.length) {
    select.innerHTML = `<option value="">No events available</option>`;
    renderSelectedEventSnapshot(null);
    return;
  }

  select.innerHTML = events.map(event => `
    <option value="${event.id}">${escapeHtml(event.title)}</option>
  `).join("");

  const requestedId = getRequestedEventId();
  const hasRequested = requestedId && events.some(event => String(event.id) === String(requestedId));
  if (hasRequested) {
    select.value = requestedId;
  }

  loadEventIntoForm(select.value);
}

function loadEventIntoForm(eventId) {
  const selectedEvent = myEvents.find(event => Number(event.id) === Number(eventId));
  if (!selectedEvent) {
    renderSelectedEventSnapshot(null);
    return;
  }

  document.getElementById("event-name").value = selectedEvent.title || "";
  document.getElementById("guest-count").value = Number(selectedEvent.guest_count || 0);
  document.getElementById("venue-cost").value = Number(selectedEvent.venue_cost || 0);
  document.getElementById("food-cost").value = Number(selectedEvent.food_cost_per_person || 0);
  document.getElementById("decorations-cost").value = Number(selectedEvent.decorations_cost || 0);
  document.getElementById("equipment-cost").value = Number(selectedEvent.equipment_cost || 0);
  document.getElementById("staff-cost").value = Number(selectedEvent.staff_cost || 0);
  document.getElementById("marketing-cost").value = Number(selectedEvent.marketing_cost || 0);
  document.getElementById("misc-cost").value = Number(selectedEvent.misc_cost || 0);
  document.getElementById("contingency-percent").value = Number(selectedEvent.contingency_percent || 0);

  const backLink = document.getElementById("back-to-planner-link");
  if (backLink) {
    backLink.href = `planner.html?event_id=${selectedEvent.id}`;
  }

  renderSelectedEventSnapshot(selectedEvent);
  calculateBudget();
}

function renderSelectedEventSnapshot(selectedEvent) {
  const scheduleEl = document.getElementById("budget-snapshot-schedule");
  const locationEl = document.getElementById("budget-snapshot-location");
  const descriptionEl = document.getElementById("budget-snapshot-description");
  const progressEl = document.getElementById("budget-snapshot-progress");

  if (!scheduleEl || !locationEl || !descriptionEl || !progressEl) {
    return;
  }

  if (!selectedEvent) {
    scheduleEl.textContent = "—";
    locationEl.textContent = "—";
    descriptionEl.textContent = "—";
    progressEl.textContent = "0 / 0 complete";
    return;
  }

  const eventTasks = myTasks.filter(task => Number(task.event_id) === Number(selectedEvent.id));
  const completed = eventTasks.filter(task => Number(task.completed) === 1).length;

  scheduleEl.textContent = formatDateTimeRange(selectedEvent.start_datetime, selectedEvent.end_datetime, selectedEvent.date);
  locationEl.textContent = selectedEvent.location || "Not set";
  descriptionEl.textContent = selectedEvent.description || "No description";
  progressEl.textContent = `${completed} / ${eventTasks.length} complete`;
}

async function saveBudgetToEvent() {
  const eventId = document.getElementById("event-select").value;
  const statusEl = document.getElementById("budget-status");

  if (!eventId) {
    statusEl.textContent = "Select an event first.";
    return;
  }

  const budget = calculateBudget();
  statusEl.textContent = "Saving budget...";

  try {
    const response = await fetch(`${API_BASE}/api/events/${eventId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify({
        title: budget.eventName,
        guest_count: budget.guests,
        venue_cost: budget.venue,
        food_cost_per_person: budget.foodPerPerson,
        decorations_cost: budget.decorations,
        equipment_cost: budget.equipment,
        staff_cost: budget.staff,
        marketing_cost: budget.marketing,
        misc_cost: budget.misc,
        contingency_percent: budget.contingencyPercent,
        budget_subtotal: budget.subtotal,
        budget_contingency: budget.contingency,
        budget_total: budget.total
      })
    });

    const data = await response.json();
    if (!response.ok) {
      statusEl.textContent = data.error || "Could not save budget.";
      return;
    }

    statusEl.textContent = `Budget saved to ${budget.eventName}.`;
    myEvents = await fetchMyEvents();
    populateEventSelector(myEvents);
    document.getElementById("event-select").value = String(eventId);
    loadEventIntoForm(eventId);
  } catch (error) {
    console.error("Save budget error:", error);
    statusEl.textContent = "Server error while saving budget.";
  }
}

async function sendMessage(message) {
  const response = await fetch(`${API_BASE}/api/ai/chat`, {
      method: "POST",
      headers: {
          "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify({ message })
  });

  const data = await response.json();

  if (!response.ok) {
      throw new Error(data.error || "Chat request failed");
  }

  return data;
}

async function handleChatSubmit(event) {
  event.preventDefault();

  const input = document.getElementById("chat-input");
  const message = input.value.trim();

  if (!message) return;

  appendChatMessage("user", message);
  input.value = "";

  try {
      const result = await sendMessage(message);
      appendChatMessage("bot", result.reply || "I couldn't generate a reply.");
  } catch (error) {
      console.error("Chat error:", error);
      appendChatMessage("bot", "There was a problem reaching the chatbot.");
  }
}

function appendChatMessage(sender, text) {
  const container = document.getElementById("chat-messages");
  const bubble = document.createElement("div");

  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(value) {
  return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", async () => {
  const currentUser = JSON.parse(localStorage.getItem("user") || "null");
  const adminLink = document.getElementById("admin-nav-link");
  if (adminLink && currentUser) {
    adminLink.style.display = currentUser.role === "admin" ? "block" : "none";
  }
  document.getElementById("calculate-btn").addEventListener("click", calculateBudget);
  document.getElementById("save-btn").addEventListener("click", saveBudgetToEvent);
  document.getElementById("reset-btn").addEventListener("click", resetBudgetForm);
  document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
  document.getElementById("event-select").addEventListener("change", (event) => {
    loadEventIntoForm(event.target.value);
  });

  const inputIds = [
    "event-name",
    "guest-count",
    "venue-cost",
    "food-cost",
    "decorations-cost",
    "equipment-cost",
    "staff-cost",
    "marketing-cost",
    "misc-cost",
    "contingency-percent"
  ];

  inputIds.forEach((id) => {
    document.getElementById(id).addEventListener("input", calculateBudget);
  });

  calculateBudget();

  try {
    [myEvents, myTasks] = await Promise.all([fetchMyEvents(), fetchMyTasks()]);
    populateEventSelector(myEvents);
  } catch (error) {
    console.error("Failed to load events for budget page:", error);
    document.getElementById("budget-status").textContent = "Could not load your events. Make sure you're logged in.";
  }
});
