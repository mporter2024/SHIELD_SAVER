const API_BASE = "http://127.0.0.1:5000";
let myEvents = [];
let myTasks = [];

/* =========================
   HELPERS
========================= */

function getNumberValue(id) {
  const value = parseFloat(document.getElementById(id).value);
  return isNaN(value) ? 0 : value;
}

function formatCurrency(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
}

function getSelectedEventName() {
  const select = document.getElementById("event-select");
  if (!select || select.selectedIndex < 0) return "Not set";
  return select.options[select.selectedIndex]?.text || "Not set";
}

function getBudgetTip(total, guests) {
  if (guests === 0) {
    return "Enter a guest count to get a more realistic estimate.";
  }

  if (total < 500) {
    return "This looks like a lower-cost event. Double-check that you included all categories.";
  }

  if (total < 2000) {
    return "This looks like a moderate event budget. Make sure your venue and food numbers are realistic.";
  }

  return "This is a higher-cost event. Review large categories like venue, catering, and equipment.";
}

/* =========================
   CALCULATE
========================= */

function calculateBudget() {
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

  document.getElementById("summary-event").textContent = getSelectedEventName();
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
    eventName: getSelectedEventName(),
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

/* =========================
   RESET
========================= */

function resetBudgetForm() {
  [
    "guest-count",
    "venue-cost",
    "food-cost",
    "decorations-cost",
    "equipment-cost",
    "staff-cost",
    "marketing-cost",
    "misc-cost",
    "contingency-percent"
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = 0;
  });

  document.getElementById("summary-event").textContent = getSelectedEventName();
  document.getElementById("summary-guests").textContent = "0";

  [
    "venue",
    "food",
    "decorations",
    "equipment",
    "staff",
    "marketing",
    "misc",
    "subtotal",
    "contingency",
    "total"
  ].forEach(key => {
    const el = document.getElementById(`summary-${key}`);
    if (el) el.textContent = "$0.00";
  });

  calculateBudget();
}

/* =========================
   API CALLS
========================= */

async function fetchMyEvents() {
  const response = await fetch(`${API_BASE}/api/events/mine`, {
    credentials: "include"
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load events");

  return data;
}

async function fetchMyTasks() {
  const response = await fetch(`${API_BASE}/api/tasks/mine`, {
    credentials: "include"
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load tasks");

  return data;
}

/* =========================
   EVENT SELECTOR
========================= */

function populateEventSelector(events) {
  const select = document.getElementById("event-select");

  if (!events.length) {
    select.innerHTML = `<option value="">No events available</option>`;
    return;
  }

  select.innerHTML = events.map(event => `
    <option value="${event.id}">${event.title}</option>
  `).join("");

  loadEventIntoForm(select.value);
}

function loadEventIntoForm(eventId) {
  const selectedEvent = myEvents.find(e => Number(e.id) === Number(eventId));
  if (!selectedEvent) return;

  document.getElementById("guest-count").value = selectedEvent.guest_count || 0;
  document.getElementById("venue-cost").value = selectedEvent.venue_cost || 0;
  document.getElementById("food-cost").value = selectedEvent.food_cost_per_person || 0;
  document.getElementById("decorations-cost").value = selectedEvent.decorations_cost || 0;
  document.getElementById("equipment-cost").value = selectedEvent.equipment_cost || 0;
  document.getElementById("staff-cost").value = selectedEvent.staff_cost || 0;
  document.getElementById("marketing-cost").value = selectedEvent.marketing_cost || 0;
  document.getElementById("misc-cost").value = selectedEvent.misc_cost || 0;
  document.getElementById("contingency-percent").value = selectedEvent.contingency_percent || 0;

  calculateBudget();
}

/* =========================
   SAVE
========================= */

async function saveBudgetToEvent() {
  const eventId = document.getElementById("event-select").value;
  const statusEl = document.getElementById("budget-status");

  if (!eventId) {
    statusEl.textContent = "Select an event first.";
    return;
  }

  const budget = calculateBudget();
  statusEl.textContent = "Saving...";

  try {
    const response = await fetch(`${API_BASE}/api/events/${eventId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
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

    if (!response.ok) throw new Error("Save failed");

    statusEl.textContent = "Budget saved successfully.";
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Error saving budget.";
  }
}

/* =========================
   INIT
========================= */

document.addEventListener("DOMContentLoaded", async () => {

  document.getElementById("save-btn").addEventListener("click", saveBudgetToEvent);
  document.getElementById("reset-btn").addEventListener("click", resetBudgetForm);

  document.getElementById("event-select").addEventListener("change", (e) => {
    loadEventIntoForm(e.target.value);
  });

  [
    "guest-count",
    "venue-cost",
    "food-cost",
    "decorations-cost",
    "equipment-cost",
    "staff-cost",
    "marketing-cost",
    "misc-cost",
    "contingency-percent"
  ].forEach(id => {
    document.getElementById(id).addEventListener("input", calculateBudget);
  });

  try {
    myEvents = await fetchMyEvents();
    myTasks = await fetchMyTasks();
    populateEventSelector(myEvents);

    document.getElementById("budget-status").textContent = ""; // clear error
  } catch (error) {
    console.error(error);
    document.getElementById("budget-status").textContent = "Could not load your events.";
  }

  calculateBudget();
});

window.addEventListener("shield-ai-action", async (event) => {
  const data = event.detail || {};
  const relatedEventId = data.event?.id || data.event_id || data.task?.event_id;
  if (!relatedEventId) return;

  try {
    myEvents = await fetchMyEvents();
    populateEventSelector(myEvents);
    const eventSelect = document.getElementById("event-select");
    if (eventSelect) {
      eventSelect.value = String(relatedEventId);
      loadEventIntoForm(relatedEventId);
    }
  } catch (error) {
    console.error("Budget refresh from AI action failed:", error);
  }
});
