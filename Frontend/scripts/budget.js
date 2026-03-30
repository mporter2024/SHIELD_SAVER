const API_BASE = "http://127.0.0.1:5000";
let myEvents = [];

function getNumberValue(id) {
  const value = parseFloat(document.getElementById(id).value);
  return isNaN(value) ? 0 : value;
}

function formatCurrency(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
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

function populateEventSelector(events) {
  const select = document.getElementById("event-select");

  if (!events.length) {
    select.innerHTML = `<option value="">No events available</option>`;
    return;
  }

  select.innerHTML = events.map(event => `
    <option value="${event.id}">${escapeHtml(event.title)}</option>
  `).join("");

  loadEventIntoForm(select.value);
}

function loadEventIntoForm(eventId) {
  const selectedEvent = myEvents.find(event => Number(event.id) === Number(eventId));
  if (!selectedEvent) return;

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

  calculateBudget();
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
    myEvents = await fetchMyEvents();
    populateEventSelector(myEvents);
  } catch (error) {
    console.error("Failed to load events for budget page:", error);
    document.getElementById("budget-status").textContent = "Could not load your events. Make sure you're logged in.";
  }
});
