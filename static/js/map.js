const map = L.map("map").setView([39.47, -0.376], 13);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let geoLayer;

function getColor(flow) {
    if (flow < 200) return "green";
    if (flow < 500) return "orange";
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

                            // intentamos leer flujo del backend
                            const u = feature.properties.u;
                            const v = feature.properties.v;

                            const edge = state.edges.find(
                                e => e.u === u && e.v === v
                            );

                            const flow = edge ? edge.flow : 100;

                            return {
                                color: edge && edge.closed
                                    ? "black"
                                    : getColor(flow),
                                weight: 3
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

        document.getElementById("panel").innerHTML = `
            <h3>${data.name}</h3>
            <p>Flujo: ${data.flow}</p>
            <p>Congestión: ${data.congestion}</p>

            <button onclick="closeStreet()">Cerrar calle</button>
            <button onclick="openStreet()">Abrir calle</button>
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