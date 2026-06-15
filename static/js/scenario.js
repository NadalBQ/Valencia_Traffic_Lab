const datePicker = document.getElementById("datePicker");
const hourSelect = document.getElementById("hour");
const label = document.getElementById("hourLabel");

let availableSnapshots = {};

initScenarioControls();

async function initScenarioControls() {

    const response = await fetch("/api/available_snapshots");
    const data = await response.json();

    availableSnapshots = data.snapshots;

    const dates = Object.keys(availableSnapshots).sort();

    datePicker.innerHTML = "";

    dates.forEach(date => {
        const option = document.createElement("option");
        option.value = date;
        option.textContent = formatBrowserDate(date);
        datePicker.appendChild(option);
    });

    const savedDate = localStorage.getItem("traffic_date");
    const savedHour = localStorage.getItem("traffic_hour");

    if (savedDate && availableSnapshots[savedDate]) {
        datePicker.value = savedDate;
    } else if (dates.length > 0) {
        datePicker.value = dates[0];
    }

    updateHourOptions();

    if (
        savedHour &&
        Array.from(hourSelect.options).some(option => option.value === savedHour)
    ) {
        hourSelect.value = savedHour;
    }

    updateHourLabel();

    await syncScenarioToBackend();

    loadMap();
}

function updateHourOptions() {

    const selectedDate = datePicker.value;
    const hours = availableSnapshots[selectedDate] || [];

    hourSelect.innerHTML = "";

    hours.forEach(hour => {
        const option = document.createElement("option");
        option.value = hour;
        option.textContent = `${hour}:00`;
        hourSelect.appendChild(option);
    });
}

function updateHourLabel() {

    if (label) {
        label.innerText = `${hourSelect.value}:00`;
    }
}

async function syncScenarioToBackend() {

    localStorage.setItem("traffic_date", datePicker.value);
    localStorage.setItem("traffic_hour", hourSelect.value);

    await fetch("/api/set_date", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            date: datePicker.value
        })
    });

    await fetch("/api/set_hour", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            hour: hourSelect.value
        })
    });
}

datePicker.addEventListener("change", async () => {

    updateHourOptions();
    updateHourLabel();

    await syncScenarioToBackend();

    loadMap();
});

hourSelect.addEventListener("change", async () => {

    updateHourLabel();

    await syncScenarioToBackend();

    loadMap();
});

function formatBrowserDate(dateString) {

    const parts = dateString.split("-");

    if (parts.length !== 3) {
        return dateString;
    }

    return `${parts[2]}.${parts[1]}.${parts[0]}`;
}