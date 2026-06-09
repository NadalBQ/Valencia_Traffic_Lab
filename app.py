from flask import Flask, render_template, jsonify, request
import osmnx as ox
import networkx as nx
import random

app = Flask(__name__)

# =========================
# Real Valencia Graph
# =========================
G = ox.graph_from_place("Valencia, Spain", network_type="drive")

@app.route("/api/geojson")
def geojson():

    # 1. extract edges
    nodes, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)

    # 2. set u/v/key as columns
    edges = edges.reset_index()

    # 3. ensure lat/lon
    edges = edges.to_crs(epsg=4326)

    # 4. unique id
    edges["edge_id"] = (
        edges["u"].astype(str) + "_" +
        edges["v"].astype(str) + "_" +
        edges["key"].astype(str)
    )

    return edges.__geo_interface__

# =========================
# Starting scenario
# =========================
scenario = {
    "hour": 8,
    "selected_edge": None,
    "closed_edges": set()
}

# =========================
# Base edge flow, to be set with historic data
# =========================
def init_flows():
    for u, v, k, data in G.edges(keys=True, data=True):
        base = max(50, int(1000 / (data.get("length", 100) + 1)))
        data["base_flow"] = base
        data["flow"] = base

init_flows()

# =========================
# Flow estimation after closing edges
# =========================
def compute_flows():

    # reset flows
    for u, v, k, data in G.edges(keys=True, data=True):
        data["flow"] = data["base_flow"]

    # Make a copy to not lose the real graph
    G_temp = G.copy()

    for (u, v) in scenario["closed_edges"]:
        if G_temp.has_edge(u, v):
            G_temp.remove_edge(u, v)

    # Redistribution simulation
    nodes = list(G_temp.nodes())

    for _ in range(200):  # N vehicles simulated
        origin = random.choice(nodes)
        target = random.choice(nodes)

        if origin == target:
            continue

        try:
            path = nx.shortest_path(
                G_temp,
                origin,
                target,
                weight="length"
            )

            # adding flow on the path's edges
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]

                if G.has_edge(u, v):
                    G[u][v][0]["flow"] += 1

        except:
            continue


# =========================
# EDGE INFO
# =========================
def edge_list():
    edges = []

    for u, v, k, data in G.edges(keys=True, data=True):

        edges.append({
            "u": u,
            "v": v,
            "length": data.get("length", 0),
            "flow": data.get("flow", 0),
            "base_flow": data.get("base_flow", 0),
            "congestion": round(
                data.get("flow", 1) / max(data.get("base_flow", 1), 1), 2
            ),
            "closed": (u, v) in scenario["closed_edges"]
        })

    return edges


# =========================
# WEB VIEW
# =========================
@app.route("/")
def map_view():
    return render_template("map.html")


@app.route("/analysis/<int:node>")
def analysis_view(node):
    return render_template("analysis.html", node=node)


# =========================
# API STATE
# =========================
@app.route("/api/state")
def state():
    compute_flows()

    return jsonify({
        "hour": scenario["hour"],
        "closed_edges": list(scenario["closed_edges"]),
        "edges": edge_list()
    })


# =========================
# SELECT EDGE (STREET)
# =========================
@app.route("/api/select_edge", methods=["POST"])
def select_edge():
    print("RAW DATA:", request.data)
    print("JSON:", request.get_json())
    data = request.get_json(silent=True)

    if not data:
        print("No JSON received")
        return jsonify({"error": "No JSON received"}), 400

    u = data.get("u")
    v = data.get("v")

    if u is None or v is None:
        print("Missing u or v")
        return jsonify({"error": "Missing u or v"}), 400

    scenario["selected_edge"] = (u, v)

    data = G[u][v][0]

    return jsonify({
        "u": u,
        "v": v,
        "name": data.get("name", "Sin nombre"),
        "length": data.get("length", 0),
        "flow": data.get("flow", 0),
        "base_flow": data.get("base_flow", 0),
        "congestion": round(data.get("flow", 1) / max(data.get("base_flow", 1), 1), 2),
        "closed": (u, v) in scenario["closed_edges"]
    })


# =========================
# CLOSE EDGE (STREET)
# =========================
@app.route("/api/close_edge", methods=["POST"])
def close_edge():
    u, v = scenario["selected_edge"]
    scenario["closed_edges"].add((u, v))
    return jsonify({"ok": True})


# =========================
# OPEN EDGE (STREET)
# =========================
@app.route("/api/open_edge", methods=["POST"])
def open_edge():
    u, v = scenario["selected_edge"]
    scenario["closed_edges"].discard((u, v))
    return jsonify({"ok": True})


# =========================
# SIMPLE ANALYSIS
# =========================
@app.route("/api/analysis/<int:node>")
def analysis(node):
    return jsonify({
        "hours": ["06", "08", "10", "12", "18", "22"],
        "flow": [300, 1200, 900, 1100, 1600, 700],
        "impact": [
            {"street": "Xàtiva", "value": 28},
            {"street": "Gran Vía", "value": 21},
            {"street": "Guillem Castro", "value": 15}
        ]
    })


if __name__ == "__main__":
    app.run(debug=True)