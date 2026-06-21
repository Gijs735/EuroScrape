const JSON_SOURCES = [
  { label: "Gijs's schedule", file: "eurostar_prices.json" },
];
const BRUSSELS = "Brussels-South";
const PARIS = "Paris-Nord";
const BRUSSELS_TIME_ZONE = "Europe/Brussels";
const IS_LOCAL_FILE = window.location.protocol === "file:";
const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];
const STATIONS = {
  brussels: { label: "Brussels", station: BRUSSELS },
  paris: { label: "Paris", station: PARIS },
};

const els = {
  routeTitle: document.querySelector("#route-title"),
  originCity: document.querySelector("#origin-city"),
  destinationCity: document.querySelector("#destination-city"),
  filterPanel: document.querySelector(".filter-panel"),
  serverDataWrap: document.querySelector("#server-data-wrap"),
  jsonSourceButton: document.querySelector("#json-source-button"),
  jsonSourceLabel: document.querySelector("#json-source-label"),
  jsonSourceMenu: document.querySelector("#json-source-menu"),
  lastUpdated: document.querySelector("#last-updated"),
  expensivePrice: document.querySelector("#expensive-price"),
  maximumPrice: document.querySelector("#maximum-price"),
  hideOverMaximum: document.querySelector("#hide-over-maximum"),
  localDataPanel: document.querySelector("#local-data-panel"),
  localJsonFile: document.querySelector("#local-json-file"),
  calendarYears: document.querySelector("#calendar-years"),
  grid: document.querySelector("#journey-grid"),
  template: document.querySelector("#journey-card-template"),
};

let allTrains = [];
let returnJourneys = [];
let calendarTooltip;
let selectedOrigin = "brussels";
let selectedJsonFileName = JSON_SOURCES[0].file;

function ordinal(day) {
  const mod100 = day % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${day}th`;
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}

function parseDateParts(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return { year, month, day };
}

function dateFromIsoDate(isoDate) {
  const { year, month, day } = parseDateParts(isoDate);
  return new Date(Date.UTC(year, month - 1, day));
}

function formatDate(isoDate) {
  const { year, month, day } = parseDateParts(isoDate);
  const monthName = new Intl.DateTimeFormat("en-GB", {
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));

  return `${ordinal(day)} of ${monthName} ${year}`;
}

function formatShortDate(isoDate) {
  const { year, month, day } = parseDateParts(isoDate);
  return `${pad(day)}/${pad(month)}/${year}`;
}

function formatUpdated(isoDateTime) {
  const updated = new Date(isoDateTime);
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: BRUSSELS_TIME_ZONE,
  }).formatToParts(updated);

  const value = (type) => parts.find((part) => part.type === type)?.value;
  return `Last updated ${ordinal(Number(value("day")))} of ${value("month")} ${value("year")} at ${value("hour")}:${value("minute")}`;
}

function formatMoney(amount, currency) {
  const formattedAmount = new Intl.NumberFormat("en-IE", {
    maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
  }).format(amount);

  if (currency === "EUR") return `€ ${formattedAmount}`;

  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency,
    maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
  }).format(amount);
}

function shortMoney(amount, currency) {
  return formatMoney(amount, currency).replace(" ", "");
}

function populateJsonSources() {
  els.jsonSourceMenu.replaceChildren();
  JSON_SOURCES.forEach((source) => {
    const option = document.createElement("button");
    option.className = "schedule-option";
    option.type = "button";
    option.role = "option";
    option.dataset.file = source.file;
    option.textContent = source.label;
    option.setAttribute("aria-selected", source.file === selectedJsonFileName ? "true" : "false");
    option.classList.toggle("is-selected", source.file === selectedJsonFileName);
    els.jsonSourceMenu.appendChild(option);
  });
  updateJsonSourceLabel();
}

function selectedJsonFile() {
  return selectedJsonFileName;
}

function updateJsonSourceLabel() {
  const selected = JSON_SOURCES.find((source) => source.file === selectedJsonFileName) || JSON_SOURCES[0];
  els.jsonSourceLabel.textContent = selected.label;
}

function setScheduleMenuOpen(open) {
  els.jsonSourceButton.setAttribute("aria-expanded", String(open));
  els.jsonSourceMenu.hidden = !open;
}

function toggleScheduleMenu() {
  setScheduleMenuOpen(els.jsonSourceButton.getAttribute("aria-expanded") !== "true");
}

function selectedRoute() {
  const origin = STATIONS[selectedOrigin];
  const destinationKey = selectedOrigin === "brussels" ? "paris" : "brussels";
  const destination = STATIONS[destinationKey];
  return { origin, destination };
}

function stationLabel(stationName) {
  return Object.values(STATIONS).find((city) => city.station === stationName)?.label || stationName;
}

function weekdayName(isoDate) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    timeZone: "UTC",
  }).format(dateFromIsoDate(isoDate));
}

function formatWeekdayRange(startDate, endDate) {
  return `${weekdayName(startDate)} to ${weekdayName(endDate)}`;
}

function routeName(route) {
  return `${route.origin.label} to ${route.destination.label}`;
}

function matchesRoute(train, origin, destination) {
  return train.departure_station === origin.station && train.arrival_station === destination.station;
}

function cheapestTrain(trains) {
  return [...trains].sort((a, b) => {
    if (a.price !== b.price) return a.price - b.price;
    return a.departure_time.localeCompare(b.departure_time);
  })[0];
}

function groupByDate(trains, predicate) {
  return trains.filter(predicate).reduce((map, train) => {
    const existing = map.get(train.date) || [];
    existing.push(train);
    map.set(train.date, existing);
    return map;
  }, new Map());
}

function buildReturnJourneys(trains, route) {
  const outboundByDate = groupByDate(trains, (train) => matchesRoute(train, route.origin, route.destination));
  const returnsByDate = groupByDate(trains, (train) => matchesRoute(train, route.destination, route.origin));
  const outboundDates = [...outboundByDate.keys()].sort();
  const returnDates = [...returnsByDate.keys()].sort();
  const journeys = [];

  outboundDates.forEach((outboundDate, index) => {
    const nextOutboundDate = outboundDates[index + 1];
    const outbound = cheapestTrain(outboundByDate.get(outboundDate));
    const matchingReturnDates = returnDates.filter((returnDate) => (
      returnDate > outboundDate && (!nextOutboundDate || returnDate < nextOutboundDate)
    ));

    matchingReturnDates.forEach((returnDate) => {
      const inbound = cheapestTrain(returnsByDate.get(returnDate));
      journeys.push({
        outboundDate,
        returnDate,
        outbound,
        inbound,
        route,
        total: outbound.price + inbound.price,
        currency: outbound.currency || inbound.currency || "EUR",
      });
    });
  });

  return journeys.sort((a, b) => {
    if (a.outboundDate !== b.outboundDate) return a.outboundDate.localeCompare(b.outboundDate);
    return a.returnDate.localeCompare(b.returnDate);
  });
}

function cheapestJourney(journeys) {
  return [...journeys].sort((a, b) => {
    if (a.total !== b.total) return a.total - b.total;
    if (a.returnDate !== b.returnDate) return a.returnDate.localeCompare(b.returnDate);
    return a.outbound.departure_time.localeCompare(b.outbound.departure_time);
  })[0];
}

function addMapItem(map, key, value) {
  const items = map.get(key) || [];
  items.push(value);
  map.set(key, items);
}

function numericInputValue(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function filterSettings() {
  return {
    expensivePrice: numericInputValue(els.expensivePrice, 70),
    maximumPrice: numericInputValue(els.maximumPrice, 100),
    hideOverMaximum: els.hideOverMaximum.checked,
  };
}

function priceStatus(total, settings) {
  if (total > settings.maximumPrice) return "is-over-maximum";
  if (total > settings.expensivePrice) return "is-expensive";
  return "is-good";
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function monthName(year, monthIndex) {
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, monthIndex, 1)));
}

function renderCard(journey, settings) {
  const fragment = els.template.content.cloneNode(true);
  const card = fragment.querySelector(".journey-card");
  const routeLabel = fragment.querySelector(".route-label");
  const dates = fragment.querySelector(".travel-dates");
  const departures = fragment.querySelector(".departure-times");
  const total = fragment.querySelector(".total-price");
  const outboundDestination = stationLabel(journey.outbound.arrival_station);
  const returnDestination = stationLabel(journey.inbound.arrival_station);

  routeLabel.textContent = formatWeekdayRange(journey.outboundDate, journey.returnDate);
  dates.textContent = `${formatDate(journey.outboundDate)} to ${formatDate(journey.returnDate)}`;
  departures.innerHTML = `
    <span>
      <strong>To ${outboundDestination}</strong>
      <span class="time-row">
        ${journey.outbound.departure_time}
      </span>
    </span>
    <span>
      <strong>Back to ${returnDestination}</strong>
      <span class="time-row">
        ${journey.inbound.departure_time}
        <small>arrives ${journey.inbound.arrival_time}</small>
      </span>
    </span>
  `;
  total.textContent = formatMoney(journey.total, journey.currency);
  total.classList.add(priceStatus(journey.total, settings));

  card.setAttribute(
    "aria-label",
    `Return journey from ${formatDate(journey.outboundDate)} to ${formatDate(journey.returnDate)} for ${formatMoney(journey.total, journey.currency)}`
  );

  els.grid.appendChild(fragment);
}

function visibleJourneys(journeys, settings) {
  if (!settings.hideOverMaximum) return journeys;
  return journeys.filter((journey) => journey.total <= settings.maximumPrice);
}

function updateRouteTitle(route) {
  els.originCity.textContent = route.origin.label;
  els.destinationCity.textContent = route.destination.label;
  els.originCity.setAttribute(
    "aria-label",
    `Current first leg starts in ${route.origin.label}. Click to swap direction.`
  );
  els.destinationCity.setAttribute(
    "aria-label",
    `Current first leg goes to ${route.destination.label}. Click to swap direction.`
  );
  els.routeTitle.setAttribute("aria-label", `${routeName(route)} returns`);
  document.title = `${routeName(route)} Weekend Trains`;
}

function renderJourneys(route) {
  els.grid.replaceChildren();

  const settings = filterSettings();
  const journeys = visibleJourneys(returnJourneys, settings);
  if (!returnJourneys.length) {
    renderEmptyState(`No ${routeName(route)} return journeys were found in this JSON.`);
    return;
  }

  if (!journeys.length) {
    renderEmptyState("No return journeys match the current filters.");
    return;
  }

  journeys.forEach((journey) => renderCard(journey, settings));
}

function renderCalendarDay(day, journeys, settings) {
  const dayElement = document.createElement("span");
  dayElement.className = "calendar-day";
  dayElement.textContent = String(day);

  if (!journeys?.length) return dayElement;

  const journey = cheapestJourney(journeys);
  const price = shortMoney(journey.total, journey.currency);
  dayElement.classList.add(priceStatus(journey.total, settings));
  dayElement.innerHTML = `<span class="calendar-date-number">${day}</span>`;
  dayElement.dataset.tooltipDate = journeys.length === 1
    ? `${formatShortDate(journey.outboundDate)} to ${formatShortDate(journey.returnDate)}`
    : formatShortDate(journey.outboundDate);
  dayElement.dataset.tooltipMeta = journeys.length === 1
    ? routeName(journey.route)
    : `${journeys.length} return options`;
  dayElement.dataset.tooltipPrice = journeys.length === 1
    ? formatMoney(journey.total, journey.currency)
    : `cheapest ${formatMoney(journey.total, journey.currency)}`;
  dayElement.setAttribute("aria-label", `${formatDate(journey.outboundDate)}, ${price}`);
  dayElement.tabIndex = 0;
  return dayElement;
}

function renderCalendarMonth(year, monthIndex, journeysByDate, settings) {
  const month = document.createElement("section");
  month.className = "calendar-month";
  month.innerHTML = `<h4>${monthName(year, monthIndex)}</h4>`;

  const grid = document.createElement("div");
  grid.className = "calendar-month-grid";

  WEEKDAYS.forEach((weekday) => {
    const weekdayElement = document.createElement("span");
    weekdayElement.className = "calendar-weekday";
    weekdayElement.textContent = weekday;
    grid.appendChild(weekdayElement);
  });

  const firstDay = new Date(Date.UTC(year, monthIndex, 1)).getUTCDay();
  const mondayOffset = (firstDay + 6) % 7;
  const daysInMonth = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate();

  for (let index = 0; index < mondayOffset; index += 1) {
    const spacer = document.createElement("span");
    spacer.className = "calendar-day is-empty";
    grid.appendChild(spacer);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const isoDate = `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
    grid.appendChild(renderCalendarDay(day, journeysByDate.get(isoDate), settings));
  }

  month.appendChild(grid);
  return month;
}

function renderCalendar(route) {
  els.calendarYears.replaceChildren();

  if (!returnJourneys.length) {
    const empty = document.createElement("p");
    empty.className = "calendar-empty";
    empty.textContent = allTrains.length
      ? `No ${routeName(route)} pairs to show in the calendar.`
      : "Load train data to see the calendar.";
    els.calendarYears.appendChild(empty);
    return;
  }

  const settings = filterSettings();
  const journeysByDate = new Map();
  returnJourneys.forEach((journey) => addMapItem(journeysByDate, journey.outboundDate, journey));
  const years = [...new Set(returnJourneys.map((journey) => parseDateParts(journey.outboundDate).year))].sort();

  years.forEach((year) => {
    const yearElement = document.createElement("section");
    yearElement.className = "calendar-year";
    yearElement.innerHTML = `<h3>${year}</h3>`;

    const months = document.createElement("div");
    months.className = "calendar-months";
    for (let monthIndex = 0; monthIndex < 12; monthIndex += 1) {
      months.appendChild(renderCalendarMonth(year, monthIndex, journeysByDate, settings));
    }

    yearElement.appendChild(months);
    els.calendarYears.appendChild(yearElement);
  });
}

function renderDashboard() {
  const route = selectedRoute();
  updateRouteTitle(route);
  returnJourneys = buildReturnJourneys(allTrains, route);
  renderJourneys(route);
  renderCalendar(route);
}

function renderEmptyState(message, className = "empty-state") {
  const state = document.createElement("p");
  state.className = className;
  state.textContent = message;
  els.grid.replaceChildren(state);
}

async function loadPriceData() {
  if (IS_LOCAL_FILE) {
    return null;
  }

  let lastError = null;
  const jsonFile = selectedJsonFile();

  for (const url of [`/${jsonFile}`, `./${jsonFile}`]) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`Could not load ${url}`);
      return response.json();
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error("Could not load eurostar_prices.json");
}

function renderData(data) {
  allTrains = data.trains || [];

  els.lastUpdated.textContent = data.last_updated
    ? formatUpdated(data.last_updated)
    : "Last updated time unavailable";

  renderDashboard();
}

async function loadSelectedServerData() {
  try {
    els.lastUpdated.textContent = "Loading prices...";
    renderEmptyState("Loading selected schedule...");
    renderData(await loadPriceData());
  } catch (error) {
    allTrains = [];
    returnJourneys = [];
    els.lastUpdated.textContent = "Price data could not be loaded";
    renderCalendar(selectedRoute());
    renderEmptyState(error.message, "error-state");
  }
}

async function readLocalJson(file) {
  return JSON.parse(await file.text());
}

function ensureCalendarTooltip() {
  if (calendarTooltip) return calendarTooltip;

  calendarTooltip = document.createElement("div");
  calendarTooltip.className = "calendar-tooltip";
  document.body.appendChild(calendarTooltip);
  return calendarTooltip;
}

function showCalendarTooltip(target) {
  if (!target?.dataset.tooltipPrice) return;

  const tooltip = ensureCalendarTooltip();
  const rect = target.getBoundingClientRect();
  tooltip.replaceChildren();
  [
    ["calendar-tooltip-date", target.dataset.tooltipDate],
    ["calendar-tooltip-meta", target.dataset.tooltipMeta],
    ["calendar-tooltip-price", target.dataset.tooltipPrice],
  ].forEach(([className, text]) => {
    const line = document.createElement("span");
    line.className = className;
    line.textContent = text;
    tooltip.appendChild(line);
  });
  tooltip.hidden = false;

  const tooltipRect = tooltip.getBoundingClientRect();
  const top = window.scrollY + rect.top - tooltipRect.height - 10;
  const preferredLeft = window.scrollX + rect.left + rect.width / 2 - tooltipRect.width / 2;
  const left = Math.min(
    Math.max(preferredLeft, window.scrollX + 10),
    window.scrollX + document.documentElement.clientWidth - tooltipRect.width - 10
  );

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${Math.max(window.scrollY + 10, top)}px`;
}

function hideCalendarTooltip() {
  if (calendarTooltip) calendarTooltip.hidden = true;
}

function swapRoute() {
  selectedOrigin = selectedOrigin === "brussels" ? "paris" : "brussels";
  hideCalendarTooltip();
  renderDashboard();
}

async function selectJsonSource(option) {
  const file = option?.dataset.file;
  if (!file || file === selectedJsonFileName) {
    setScheduleMenuOpen(false);
    return;
  }

  selectedJsonFileName = file;
  populateJsonSources();
  setScheduleMenuOpen(false);
  await loadSelectedServerData();
}

async function init() {
  populateJsonSources();
  els.localDataPanel.hidden = !IS_LOCAL_FILE;
  els.serverDataWrap.hidden = IS_LOCAL_FILE;
  els.filterPanel.classList.toggle("is-local-file", IS_LOCAL_FILE);

  try {
    const data = await loadPriceData();

    if (!data) {
      els.lastUpdated.textContent = "Local mode";
      allTrains = [];
      updateRouteTitle(selectedRoute());
      renderCalendar(selectedRoute());
      renderEmptyState("Select eurostar_prices.json to load the train data.");
      return;
    }

    renderData(data);
  } catch (error) {
    els.lastUpdated.textContent = "Price data could not be loaded";
    renderEmptyState(error.message, "error-state");
  }
}

els.originCity.addEventListener("click", swapRoute);
els.destinationCity.addEventListener("click", swapRoute);
els.jsonSourceButton.addEventListener("click", toggleScheduleMenu);
els.jsonSourceMenu.addEventListener("click", (event) => {
  selectJsonSource(event.target.closest(".schedule-option"));
});
document.addEventListener("click", (event) => {
  if (!els.serverDataWrap.contains(event.target)) setScheduleMenuOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setScheduleMenuOpen(false);
});
els.expensivePrice.addEventListener("input", renderDashboard);
els.maximumPrice.addEventListener("input", renderDashboard);
els.hideOverMaximum.addEventListener("change", renderDashboard);
els.calendarYears.addEventListener("mouseover", (event) => {
  showCalendarTooltip(event.target.closest(".calendar-day[data-tooltip-price]"));
});
els.calendarYears.addEventListener("focusin", (event) => {
  showCalendarTooltip(event.target.closest(".calendar-day[data-tooltip-price]"));
});
els.calendarYears.addEventListener("mouseout", (event) => {
  const day = event.target.closest(".calendar-day[data-tooltip-price]");
  if (day && !day.contains(event.relatedTarget)) hideCalendarTooltip();
});
els.calendarYears.addEventListener("focusout", hideCalendarTooltip);
window.addEventListener("scroll", hideCalendarTooltip, { passive: true });
els.localJsonFile.addEventListener("change", async () => {
  const [file] = els.localJsonFile.files;
  if (!file) return;

  try {
    renderData(await readLocalJson(file));
  } catch (error) {
    renderEmptyState(`Could not read ${file.name}: ${error.message}`, "error-state");
  }
});

init();
