const map = L.map("map").setView([39.47, -0.376], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let geoLayer;

function getColor(congestion) {

    if (congestion < 1.2)
        return "green";

    if (congestion < 2)
        return "yellow";

    if (congestion < 3)
        return "orange";

    return "red";
}

function loadMap() {

    fetch("/api/state")
        .then(r => r.json())
        .then(state => {

            fetch("/api/geojson")
                .then(r => r.json())
                .then(geojson => {

                    if (geoLayer) {
                        map.removeLayer(geoLayer);
                    }

                    geoLayer = L.geoJSON(geojson, {

                        style: function (feature) {

                            // Get flow from backend
                            const u = feature.properties.u;
                            const v = feature.properties.v;

                            const edge = state.edges.find(
                                e => e.u === u && e.v === v
                            );

                            const congestion = edge ? edge.congestion : 1;

                            return {

                                color:
                                    edge && edge.closed
                                        ? "black"
                                        : getColor(congestion),

                                weight:
                                    edge && edge.closed
                                        ? 6
                                        : Math.min(
                                            8,
                                            2 + congestion
                                        )
                            };
                        },

                        onEachFeature: function (feature, layer) {

                            layer.on("click", (e) => {

                                const props = feature.properties;

                                const u = props.u ?? props.source;
                                const v = props.v ?? props.target;

                                console.log("EDGE CLICKED:", u, v);

                                if (u === undefined || v === undefined) {
                                    console.error("Edge sin u/v:", props);
                                    return;
                                }

                                selectEdge(u, v);
                            });

                        }

                    }).addTo(map);

                });

            const alertContainer = document.getElementById('traffic-alert-box'); 
                
            if (state.alert && state.alert.interrupted) {
                // Build list of suggested reopenings
                let listItems = state.alert.suggested_reopenings.map(street => {
                    return `<li><strong>${street.name}</strong></li>`;
                }).join('');

                // Show alert on the web
                alertContainer.innerHTML = `
                    <div style="background-color: #ffcccc; color: #cc0000; padding: 15px; border: 1px solid #cc0000; border-radius: 5px; margin: 10px 0;">
                        <p>⚠️ <strong>Warning!</strong> Valencia is now separated by closed streets.</p>
                        <p>You can reconnect Valencia reopening any of these streets:</p>
                        <ul>${listItems}</ul>
                    </div>
                `;
                alertContainer.style.display = 'block';
            } else {
                // If no alert:
                alertContainer.innerHTML = '';
                alertContainer.style.display = 'none';
            }
        });
        const impactedDiv =
            document.getElementById(
                "impacted"
            );

        if (impactedDiv) {

            impactedDiv.innerHTML =
                state.impacted
                .map(street => `
                    <p>
                        ${street.street}
                        (+${street.increase})
                    </p>
                `)
                .join("");
        }
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

loadMap();