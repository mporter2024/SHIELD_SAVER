function getNumberValue(id) {
  const value = parseFloat(document.getElementById(id).value);
  return isNaN(value) ? 0 : value;
}

function formatCurrency(amount) {
  return `$${amount.toFixed(2)}`;
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

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("calculate-btn").addEventListener("click", calculateBudget);
  document.getElementById("reset-btn").addEventListener("click", resetBudgetForm);

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
});