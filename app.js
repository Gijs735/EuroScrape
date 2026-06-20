const JSON_URLS = ["/eurostar_prices.json", "./eurostar_prices.json"];
const BRUSSELS = "Brussels-South";
const PARIS = "Paris-Nord";
const BRUSSELS_TIME_ZONE = "Europe/Brussels";
const IS_LOCAL_FILE = window.location.protocol === "file:";

const els = {
  lastUpdated: document.querySelector("#last-updated"),
  expensivePrice: document.querySelector("#expensive-price"),
  maximumPrice: document.querySelector("#maximum-price"),
  hideOverMaximum: document.querySelector("#hide-over-maximum"),
  localDataPanel: document.querySelector("#local-data-panel"),
  localJsonFile: document.querySelector("#local-json-file"),
  grid: document.querySelector("#journey-grid"),
  template: document.querySelector("#journey-card-template"),
};

let returnJourneys = [];

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

function addDays(isoDate, days) {
  const date = dateFromIsoDate(isoDate);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatDate(isoDate) {
  const { year, month, day } = parseDateParts(isoDate);
  const monthName = new Intl.DateTimeFormat("en-GB", {
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));

  return `${ordinal(day)} of ${monthName} ${year}`;
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

function isOutbound(train) {
  return train.departure_station === BRUSSELS && train.arrival_station === PARIS;
}

function isReturn(train) {
  return train.departure_station === PARIS && train.arrival_station === BRUSSELS;
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

function buildReturnJourneys(trains) {
  const outboundByDate = groupByDate(trains, isOutbound);
  const returnsByDate = groupByDate(trains, isReturn);

  return [...outboundByDate.keys()]
    .sort()
    .map((outboundDate) => {
      const returnDate = addDays(outboundDate, 2);
      const outboundOptions = outboundByDate.get(outboundDate);
      const returnOptions = returnsByDate.get(returnDate);

      if (!outboundOptions || !returnOptions) return null;

      const outbound = cheapestTrain(outboundOptions);
      const inbound = cheapestTrain(returnOptions);

      return {
        outboundDate,
        returnDate,
        outbound,
        inbound,
        total: outbound.price + inbound.price,
        currency: outbound.currency || inbound.currency || "EUR",
      };
    })
    .filter(Boolean);
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

function renderCard(journey, settings) {
  const fragment = els.template.content.cloneNode(true);
  const card = fragment.querySelector(".journey-card");
  const dates = fragment.querySelector(".travel-dates");
  const departures = fragment.querySelector(".departure-times");
  const total = fragment.querySelector(".total-price");

  dates.textContent = `${formatDate(journey.outboundDate)} to ${formatDate(journey.returnDate)}`;
  departures.innerHTML = `
    <span>
      <strong>To Paris</strong>
      <span class="time-row">
        ${journey.outbound.departure_time}
      </span>
    </span>
    <span>
      <strong>Back to Brussels</strong>
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

function renderJourneys() {
  els.grid.replaceChildren();

  const settings = filterSettings();
  const journeys = visibleJourneys(returnJourneys, settings);
  if (!journeys.length) {
    renderEmptyState("No return journeys match the current filters.");
    return;
  }

  journeys.forEach((journey) => renderCard(journey, settings));
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

  for (const url of JSON_URLS) {
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
  returnJourneys = buildReturnJourneys(data.trains || []);

  els.lastUpdated.textContent = data.last_updated
    ? formatUpdated(data.last_updated)
    : "Last updated time unavailable";

  if (!returnJourneys.length) {
    renderEmptyState("No complete Friday to Sunday return journeys were found in the JSON.");
    return;
  }

  renderJourneys();
}

async function readLocalJson(file) {
  return JSON.parse(await file.text());
}

async function init() {
  try {
    els.localDataPanel.hidden = !IS_LOCAL_FILE;
    const data = await loadPriceData();

    if (!data) {
      els.lastUpdated.textContent = "Local mode";
      renderEmptyState("Select eurostar_prices.json to load the train data.");
      return;
    }

    renderData(data);
  } catch (error) {
    els.lastUpdated.textContent = "Price data could not be loaded";
    renderEmptyState(error.message, "error-state");
  }
}

els.expensivePrice.addEventListener("input", renderJourneys);
els.maximumPrice.addEventListener("input", renderJourneys);
els.hideOverMaximum.addEventListener("change", renderJourneys);
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
