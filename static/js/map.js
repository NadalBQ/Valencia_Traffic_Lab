const map = L.map("map").setView([39.47, -0.376], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let geoLayer;

function getFlowColor(flow, baseFlow) {

    const increase = flow - baseFlow;

    // If traffic increased because of a closure, highlight it strongly
    if (increase >= 100) {
        return "red";
    }

    if (increase > 0) {
        return "orange";
    }

    // Normal baseline traffic
    if (flow <= 50) {
        return "green";
    }

    if (flow <= 200) {
        return "yellow";
    }

    if (flow <= 500) {
        return "orange";
    }

    return "red";
}

function loadMap() {

    fetch("/api/state")
        .then(r => r.json())
        .then(state => {

            const dataStatus = document.getElementById("dataStatus");

            if (dataStatus) {
                dataStatus.innerHTML = state.loaded_file
                    ? `Loaded data: ${state.loaded_file}`
                    : `No file found for ${state.date} ${state.hour}`;
            }

            fetch("/api/geojson")
                .then(r => r.json())
                .then(geojson => {

                    if (geoLayer) {
                        map.removeLayer(geoLayer);
                    }

                    geoLayer = L.geoJSON(geojson, {

                        style: function (feature) {

                            const u = feature.properties.u;
                            const v = feature.properties.v;

                            const edge = state.edges.find(
                                e => e.u === u && e.v === v
                            );

                            const flow = edge ? edge.flow : 0;
                            const baseFlow = edge ? edge.base_flow : 0;

                            const increase = flow - baseFlow;

                            return {

                                color:
                                    edge && edge.closed
                                        ? "black"
                                        : edge && edge.selected
                                            ? "blue"
                                            : getFlowColor(flow, baseFlow),

                                weight:
                                    edge && edge.closed
                                        ? 7
                                        : edge && edge.selected
                                            ? 7
                                            : increase > 0
                                                ? 6
                                                : Math.min(
                                                    5,
                                                    2 + flow / 500
                                                ),

                                opacity:
                                    edge && edge.closed
                                        ? 1
                                        : increase > 0
                                            ? 1
                                            : 0.8
                            };
                        },

                        onEachFeature: function (feature, layer) {

                            layer.on("click", () => {

                                const props = feature.properties;

                                const u = props.u ?? props.source;
                                const v = props.v ?? props.target;

                                console.log("EDGE CLICKED:", u, v);

                                if (u === undefined || v === undefined) {
                                    console.error("Edge without u/v:", props);
                                    return;
                                }

                                selectEdge(u, v);
                            });
                        }

                    }).addTo(map);
                });

            const alertContainer = document.getElementById("traffic-alert-box");

            if (state.alert && state.alert.interrupted) {

                let listItems = state.alert.suggested_reopenings.map(street => {
                    return `<li><strong>${street.name}</strong></li>`;
                }).join("");

                alertContainer.innerHTML = `
                    <div style="background-color: #ffcccc; color: #cc0000; padding: 15px; border: 1px solid #cc0000; border-radius: 5px; margin: 10px 0;">
                        <p>⚠️ <strong>Warning!</strong> Valencia is now separated by closed streets.</p>
                        <p>You can reconnect Valencia by reopening one of these streets:</p>
                        <ul>${listItems}</ul>
                    </div>
                `;

                alertContainer.style.display = "block";

            } else {
                alertContainer.innerHTML = "";
                alertContainer.style.display = "none";
            }

            const impactedDiv = document.getElementById("impacted");

            if (impactedDiv) {

                if (state.impacted && state.impacted.length > 0) {

                    impactedDiv.innerHTML = state.impacted
                        .map(street => `
                            <p>
                                <strong>${street.street}</strong><br>
                                Traffic increase: +${street.increase}
                            </p>
                        `)
                        .join("");

                } else {
                    impactedDiv.innerHTML = "<p>No affected streets yet.</p>";
                }
            }
        });
}

function selectEdge(u, v) {

    fetch("/api/select_edge", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({"u": u, "v": v})
    })
    .then(r => r.json())
    .then(data => {

        document.getElementById("info").innerHTML = `

        <h3>${data.name}</h3>

        <p>
        Length:
        ${Math.round(data.length)} m
        </p>

        <p>
        Flow:
        ${data.flow}
        </p>

        <p>
        Base flow:
        ${data.base_flow}
        </p>

        <p>
        Congestion:
        ${data.congestion}x
        </p>

        <p>
        Status:
        ${data.closed
            ? "Closed"
            : "Open"}
        </p>

        <button onclick="closeStreet()">
        Close street
        </button>

        <button onclick="openStreet()">
        Open street
        </button>
        `;

        loadMap();
    });
}

function closeStreet() {
    fetch("/api/close_edge", {method: "POST"})
        .then(() => loadMap());
}

function openStreet() {
    fetch("/api/open_edge", {method: "POST"})
        .then(() => loadMap());
}