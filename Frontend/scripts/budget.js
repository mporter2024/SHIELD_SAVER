const API_BASE = "http://127.0.0.1:5000";
let myEvents = [];
let myTasks = [];

function getNumberValue(id) {
  const input = document.getElementById(id);
  const value = parseFloat(input?.value);
  return Number.isNaN(value) ? 0 : value;
}

function formatCurrency(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
}

function formatDateTime(dateTimeString) {
  if (!dateTimeString) return "";
  const date = new Date(dateTimeString);
  return Number.isNaN(date.getTime()) ? dateTimeString : date.toLocaleString();
}

function formatDate(dateString) {
  if (!dateString) return "";
  const date = new Date(`${dateString}T00:00:00`);
  return Number.isNaN(date.getTime()) ? dateString : date.toLocaleDateString();
}

function getSelectedEventName() {
  const select = document.getElementById("event-select");
  if (!select || select.selectedIndex < 0) return "Not set";
  return select.options[select.selectedIndex]?.text || "Not set";
}

function getSelectedEventIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("event_id") || localStorage.getItem("selectedEventId") || "";
}

function getBudgetTip(total, guests, healthLabel = "") {
  if (guests === 0) return "Enter a guest count to get a more realistic estimate.";
  if (healthLabel === "High Risk" || healthLabel === "Over Budget Risk") {
    return "This budget has pressure points. Review the warnings and try the smart suggestions before finalizing it.";
  }
  if (total < 500) return "This looks like a lower-cost event. Double-check that you included all categories.";
  if (total < 2000) return "This looks like a moderate event budget. Make sure your venue and food numbers are realistic.";
  return "This is a higher-cost event. Review large categories like venue, catering, and equipment.";
}

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
  const costPerGuest = guests > 0 ? total / guests : 0;

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
  document.getElementById("summary-cost-per-guest").textContent = formatCurrency(costPerGuest);

  const largestCategory = [
    ["Venue", venue],
    ["Food", foodTotal],
    ["Decorations", decorations],
    ["Equipment", equipment],
    ["Staff", staff],
    ["Marketing", marketing],
    ["Miscellaneous", misc]
  ].sort((a, b) => b[1] - a[1])[0][0];
  document.getElementById("summary-largest-category").textContent = largestCategory;

  const currentHealth = document.getElementById("summary-health-label").textContent || "";
  document.getElementById("budget-tip").textContent = getBudgetTip(total, guests, currentHealth);

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
    total,
    costPerGuest,
    largestCategory
  };
}

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
    "venue", "food", "decorations", "equipment", "staff", "marketing", "misc",
    "subtotal", "contingency", "total", "cost-per-guest"
  ].forEach(key => {
    const el = document.getElementById(`summary-${key}`);
    if (el) el.textContent = "$0.00";
  });
  document.getElementById("summary-largest-category").textContent = "—";
  document.getElementById("summary-health-label").textContent = "Not analyzed";
  document.getElementById("budget-health-score").textContent = "—";
  document.getElementById("budget-recommended-venue").textContent = "—";
  document.getElementById("budget-recommended-caterer").textContent = "—";
  document.getElementById("budget-style").textContent = "—";
  document.getElementById("budget-warnings").innerHTML = "<li>No smart analysis yet.</li>";
  document.getElementById("budget-suggestions").innerHTML = "<li>Generate a smart budget to see recommendations.</li>";
  calculateBudget();
}

async function fetchMyEvents() {
  const response = await fetch(`${API_BASE}/api/events/mine`, { credentials: "include" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load events");
  return data;
}

async function fetchMyTasks() {
  const response = await fetch(`${API_BASE}/api/tasks/mine`, { credentials: "include" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not load tasks");
  return data;
}

function populateEventSelector(events) {
  const select = document.getElementById("event-select");
  if (!events.length) {
    select.innerHTML = `<option value="">No events available</option>`;
    return;
  }

  select.innerHTML = events.map(event => `<option value="${event.id}">${event.title}</option>`).join("");
  const requested = String(getSelectedEventIdFromUrl());
  if (requested && events.some(event => String(event.id) === requested)) {
    select.value = requested;
  }
  loadEventIntoForm(select.value);
}

function updateSnapshot(selectedEvent) {
  const eventTasks = myTasks.filter(task => Number(task.event_id) === Number(selectedEvent.id));
  const completed = eventTasks.filter(task => Number(task.completed) === 1).length;
  const schedule = selectedEvent.start_datetime
    ? formatDateTime(selectedEvent.start_datetime)
    : (selectedEvent.date ? formatDate(selectedEvent.date) : "Not scheduled");

  document.getElementById("budget-snapshot-schedule").textContent = schedule || "—";
  document.getElementById("budget-snapshot-location").textContent = selectedEvent.location || "—";
  document.getElementById("budget-snapshot-description").textContent = selectedEvent.description || "No description yet.";
  document.getElementById("budget-snapshot-progress").textContent = `${completed} / ${eventTasks.length} complete`;
  const plannerLink = document.getElementById("back-to-planner-link");
  if (plannerLink) plannerLink.href = `planner.html?event_id=${selectedEvent.id}`;
}

async function loadInsights(eventId) {
  if (!eventId) return;
  try {
    const response = await fetch(`${API_BASE}/api/events/${eventId}/budget-insights`, {
      credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load budget insights.");
    renderInsights(data);
  } catch (error) {
    console.error("Budget insight load failed:", error);
  }
}

function renderInsights(data, recommendedVenue = null, recommendedCaterer = null) {
  const summary = data.summary || {};
  const health = data.health || {};
  document.getElementById("summary-health-label").textContent = health.label || "Not analyzed";
  document.getElementById("budget-health-score").textContent = typeof health.score === "number" ? `${health.score}/100` : "—";
  document.getElementById("budget-style").textContent = health.style ? (health.style.charAt(0).toUpperCase() + health.style.slice(1)) : "—";
  document.getElementById("summary-cost-per-guest").textContent = formatCurrency(summary.cost_per_guest || 0);
  if (summary.largest_category) {
    document.getElementById("summary-largest-category").textContent = summary.largest_category.charAt(0).toUpperCase() + summary.largest_category.slice(1);
  }
  document.getElementById("budget-recommended-venue").textContent = recommendedVenue?.name || "—";
  document.getElementById("budget-recommended-caterer").textContent = recommendedCaterer?.name || "—";

  const warningsEl = document.getElementById("budget-warnings");
  const suggestionsEl = document.getElementById("budget-suggestions");
  warningsEl.innerHTML = (data.warnings?.length ? data.warnings : ["No major budget warnings right now."])
    .map(item => `<li>${item}</li>`).join("");
  suggestionsEl.innerHTML = (data.suggestions?.length ? data.suggestions : ["No budget suggestions right now."])
    .map(item => `<li>${item}</li>`).join("");
  document.getElementById("budget-tip").textContent = getBudgetTip(summary.total || 0, summary.guest_count || 0, health.label || "");
}

function loadEventIntoForm(eventId) {
  const selectedEvent = myEvents.find(e => Number(e.id) === Number(eventId));
  if (!selectedEvent) return;

  localStorage.setItem("selectedEventId", String(selectedEvent.id));
  document.getElementById("guest-count").value = selectedEvent.guest_count || 0;
  document.getElementById("venue-cost").value = selectedEvent.venue_cost || 0;
  document.getElementById("food-cost").value = selectedEvent.food_cost_per_person || 0;
  document.getElementById("decorations-cost").value = selectedEvent.decorations_cost || 0;
  document.getElementById("equipment-cost").value = selectedEvent.equipment_cost || 0;
  document.getElementById("staff-cost").value = selectedEvent.staff_cost || 0;
  document.getElementById("marketing-cost").value = selectedEvent.marketing_cost || 0;
  document.getElementById("misc-cost").value = selectedEvent.misc_cost || 0;
  document.getElementById("contingency-percent").value = selectedEvent.contingency_percent || 0;
  updateSnapshot(selectedEvent);
  calculateBudget();
  loadInsights(selectedEvent.id);
}

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
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Save failed");
    statusEl.textContent = "Budget saved successfully.";
    myEvents = await fetchMyEvents();
    loadEventIntoForm(eventId);
  } catch (err) {
    console.error(err);
    statusEl.textContent = err.message || "Error saving budget.";
  }
}

async function generateSmartBudget() {
  const eventId = document.getElementById("event-select").value;
  const statusEl = document.getElementById("budget-status");
  if (!eventId) {
    statusEl.textContent = "Select an event first.";
    return;
  }

  statusEl.textContent = "Generating smart budget...";
  try {
    const response = await fetch(`${API_BASE}/api/events/${eventId}/budget-estimate`, {
      method: "POST",
      credentials: "include"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not generate smart budget.");

    const event = data.event || {};
    document.getElementById("guest-count").value = event.guest_count || 0;
    document.getElementById("venue-cost").value = event.venue_cost || 0;
    document.getElementById("food-cost").value = event.food_cost_per_person || 0;
    document.getElementById("decorations-cost").value = event.decorations_cost || 0;
    document.getElementById("equipment-cost").value = event.equipment_cost || 0;
    document.getElementById("staff-cost").value = event.staff_cost || 0;
    document.getElementById("marketing-cost").value = event.marketing_cost || 0;
    document.getElementById("misc-cost").value = event.misc_cost || 0;
    document.getElementById("contingency-percent").value = event.contingency_percent || 0;
    calculateBudget();
    renderInsights(data.analysis || {}, data.recommended_venue, data.recommended_caterer);
    myEvents = await fetchMyEvents();
    statusEl.textContent = "Smart budget generated and saved to the event.";
  } catch (error) {
    console.error(error);
    statusEl.textContent = error.message || "Could not generate smart budget.";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadSidebar("budget", "Budget Calculator", "Estimate event costs and review your plan in one place.", {
    brandSubtitle: "Budget Planning",
    actions: [
      { id: "refresh-btn", label: "Refresh Budget", className: "secondary-btn", action: "reload" },
      { id: "logout-btn", label: "Logout", className: "danger-btn", action: "logout" }
    ]
  });

  document.getElementById("generate-budget-btn").addEventListener("click", generateSmartBudget);
  document.getElementById("save-btn").addEventListener("click", saveBudgetToEvent);
  document.getElementById("reset-btn").addEventListener("click", resetBudgetForm);
  document.getElementById("event-select").addEventListener("change", (e) => loadEventIntoForm(e.target.value));

  [
    "guest-count", "venue-cost", "food-cost", "decorations-cost", "equipment-cost",
    "staff-cost", "marketing-cost", "misc-cost", "contingency-percent"
  ].forEach(id => document.getElementById(id).addEventListener("input", calculateBudget));

  try {
    myEvents = await fetchMyEvents();
    myTasks = await fetchMyTasks();
    populateEventSelector(myEvents);
    document.getElementById("budget-status").textContent = "";
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
    myTasks = await fetchMyTasks();
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
