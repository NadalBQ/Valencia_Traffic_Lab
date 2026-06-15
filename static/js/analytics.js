let flowChart = null;
let congestionChart = null;
let impactChart = null;

syncScenarioAndLoadAnalytics();

async function syncScenarioAndLoadAnalytics() {

    const savedDate = localStorage.getItem("traffic_date");
    const savedHour = localStorage.getItem("traffic_hour");

    if (savedDate) {
        await fetch("/api/set_date", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                date: savedDate
            })
        });
    }

    if (savedHour) {
        await fetch("/api/set_hour", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                hour: savedHour
            })
        });
    }

    loadAnalytics();
}

function loadAnalytics(mode = "auto") {

    let url = "/api/analytics";

    if (mode === "global") {
        url = "/api/analytics?mode=global";
    }

    fetch(url)
        .then(r => r.json())
        .then(data => {

            if (data.error) {
                showError(data.error);
                return;
            }

            const streetTitle = document.getElementById("streetTitle");
            const insights = document.getElementById("insights");

            if (flowChart) {
                flowChart.destroy();
            }

            if (congestionChart) {
                congestionChart.destroy();
            }

            if (impactChart) {
                impactChart.destroy();
            }

            if (data.mode === "street") {
                renderStreetAnalytics(data, streetTitle, insights);
            } else {
                renderGlobalAnalytics(data, streetTitle, insights);
            }
        })
        .catch(error => {
            console.error("Error loading analytics:", error);
            showError("Error loading analytics data. Please check the browser console.");
        });
}


// =========================
// STREET ANALYTICS
// =========================
function renderStreetAnalytics(data, streetTitle, insights) {

    streetTitle.innerHTML = `
        <h3>${data.street}</h3>
        <p>
            Analytics for the selected street |
            Date: ${formatDate(data.date)} |
            Hour: ${formatHour(data.hour)}
        </p>
    `;

    flowChart = new Chart(
        document.getElementById("flowChart"),
        {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [{
                    label: "Traffic flow",
                    data: data.flow
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: "Base flow vs current flow"
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        }
    );

    congestionChart = new Chart(
        document.getElementById("congestionChart"),
        {
            type: "bar",
            data: {
                labels: [
                    "Congestion"
                ],
                datasets: [{
                    label: "Congestion level",
                    data: [
                        data.congestion
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: "Congestion of selected street"
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        }
    );

    insights.innerHTML = `
        <h3>Selected Street Insights</h3>

        <div class="insight-box">
            <p>
                <strong>Street:</strong> ${data.street}
            </p>

            <p>
                <strong>Status:</strong> ${data.status}
            </p>

            <p>
                <strong>Length:</strong> ${data.length} m
            </p>

            <p>
                <strong>Base flow:</strong> ${Math.round(data.base_flow)}
            </p>

            <p>
                <strong>Current flow:</strong> ${Math.round(data.current_flow)}
            </p>

            <p>
                <strong>Flow change:</strong> ${formatChange(data.flow_change)}
            </p>

            <p>
                <strong>Congestion:</strong> ${data.congestion}x
            </p>

            <p>
                <strong>Closed streets in scenario:</strong> ${data.closed_streets}
            </p>

            <h4>Interpretation</h4>
            <p>${data.insight_text}</p>
        </div>

        <h4>Most impacted streets</h4>
        ${renderImpactedStreets(data.impacted)}
    `;

    renderSummaryCards([
        {
            title: "Status",
            value: data.status
        },
        {
            title: "Base flow",
            value: Math.round(data.base_flow)
        },
        {
            title: "Current flow",
            value: Math.round(data.current_flow)
        },
        {
            title: "Flow change",
            value: formatChange(data.flow_change)
        }
    ]);

    renderImpactChart(data.impacted);
}


// =========================
// GLOBAL ANALYTICS
// =========================
function renderGlobalAnalytics(data, streetTitle, insights) {

    streetTitle.innerHTML = `
        <h3>Global Valencia Analytics</h3>
        <p>
            City-wide traffic situation |
            Date: ${formatDate(data.date)} |
            Hour: ${formatHour(data.hour)}
        </p>
    `;

    flowChart = new Chart(
        document.getElementById("flowChart"),
        {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [{
                    label: "Total traffic flow",
                    data: data.flow
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: "Total traffic flow: base vs current"
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        }
    );

    congestionChart = new Chart(
        document.getElementById("congestionChart"),
        {
            type: "bar",
            data: {
                labels: [
                    "Average congestion",
                    "Most congested street"
                ],
                datasets: [{
                    label: "Congestion level",
                    data: [
                        data.average_congestion,
                        data.most_congested
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: "Congestion overview"
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        }
    );

    insights.innerHTML = `
        <h3>City Overview</h3>

        <div class="insight-box">
            <p>
                <strong>Average congestion:</strong> ${data.average_congestion}x
            </p>

            <p>
                <strong>Most congested street value:</strong> ${data.most_congested}x
            </p>

            <p>
                <strong>Closed streets:</strong> ${data.closed_streets}
            </p>

            <p>
                <strong>Total base flow:</strong> ${Math.round(data.total_base_flow)}
            </p>

            <p>
                <strong>Total current flow:</strong> ${Math.round(data.total_flow)}
            </p>

            <p>
                <strong>Total flow change:</strong> ${formatChange(data.total_increase)}
            </p>

            <h4>Interpretation</h4>
            <p>${data.insight_text}</p>
        </div>

        <h4>Most impacted streets</h4>
        ${renderImpactedStreets(data.impacted)}
    `;

    renderSummaryCards([
        {
            title: "Closed streets",
            value: data.closed_streets
        },
        {
            title: "Total flow change",
            value: formatChange(data.total_increase)
        },
        {
            title: "Average congestion",
            value: data.average_congestion + "x"
        },
        {
            title: "Most congested",
            value: data.most_congested + "x"
        }
    ]);

    renderImpactChart(data.impacted);
}


// =========================
// HELPER FUNCTIONS
// =========================
function renderImpactedStreets(impacted) {

    if (!impacted || impacted.length === 0) {
        return `
            <p>
                No impacted streets yet.
                Try selecting and closing a street on the map first.
            </p>
        `;
    }

    return `
        <ol>
            ${impacted.map(street => `
                <li>
                    <strong>${street.street}</strong>
                    <br>
                    Traffic increase: +${Math.round(street.increase)}
                </li>
            `).join("")}
        </ol>
    `;
}


function formatDate(dateString) {

    if (!dateString) {
        return "Unknown date";
    }

    const parts = dateString.split("-");

    if (parts.length !== 3) {
        return dateString;
    }

    return `${parts[0]}.${parts[1]}.${parts[2]}`;
}


function formatHour(hourString) {

    if (!hourString) {
        return "Unknown hour";
    }

    return hourString.replace("-", ":");
}


function formatChange(value) {

    if (value === undefined || value === null) {
        return "0";
    }

    const rounded = Math.round(value);

    if (rounded > 0) {
        return `+${rounded}`;
    }

    return `${rounded}`;
}


function showError(message) {

    const insights = document.getElementById("insights");

    if (insights) {
        insights.innerHTML = `
            <p style="color: red;">
                ${message}
            </p>
        `;
    }
}

function renderImpactChart(impacted) {

    const canvas = document.getElementById("impactChart");

    if (!canvas) {
        return;
    }

    let labels = [];
    let values = [];

    if (!impacted || impacted.length === 0) {
        labels = ["No impacted streets"];
        values = [0];
    } else {
        labels = impacted.map(street => street.street);
        values = impacted.map(street => Math.round(street.increase));
    }

    impactChart = new Chart(
        canvas,
        {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Traffic increase",
                    data: values
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                plugins: {
                    title: {
                        display: true,
                        text: "Most impacted streets after closures"
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        }
    );
}

function renderSummaryCards(cards) {

    const container = document.getElementById("summaryCards");

    if (!container) {
        return;
    }

    container.innerHTML = cards.map(card => `
        <div class="summary-card">
            <h4>${card.title}</h4>
            <p>${card.value}</p>
        </div>
    `).join("");
}