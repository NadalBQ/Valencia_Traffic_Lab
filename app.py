from flask import Flask, render_template, jsonify, request
import osmnx as ox
import networkx as nx
from pathlib import Path
import pandas as pd
from functools import lru_cache
import json
import pickle
import os


TRAFFIC_DIR = Path("traffic_data")


# Build the map

def get_reference_csv():

    files = sorted(
        TRAFFIC_DIR.glob("estat_traf*.csv")
    )

    if not files:
        raise RuntimeError(
            "No traffic CSV found"
        )
    
    return str(files[0])


def build_segment_mapping():

    cache_file = "cache/segment_mapping.pkl"

    if os.path.exists(cache_file):

        with open(cache_file, "rb") as f:
            return pickle.load(f)

    print("Building traffic mapping...")

    df = pd.read_csv(
        get_reference_csv(), sep=";"
    )

    mapping = {}

    for _, row in df.iterrows():

        try:

            geometry = json.loads(
                row["geo_shape"]
            )

            coords = geometry["coordinates"]

            midpoint = coords[
                len(coords)//2
            ]

            lon = midpoint[0]
            lat = midpoint[1]

            u, v, k = ox.distance.nearest_edges(
                G,
                lon,
                lat,
                return_dist=False
            )

            mapping[
                row["Id. Tram / Id. Tramo"]
            ] = (
                u,
                v,
                k
            )

        except Exception:
            continue

    os.makedirs(
        "cache",
        exist_ok=True
    )

    with open(cache_file, "wb") as f:
        pickle.dump(
            mapping,
            f
        )

    return mapping




@lru_cache(maxsize=50)
def load_traffic_snapshot(
    date_str,
    hour_str
):

    pattern = (
        f"estat_traf"
        f"{date_str}_"
        f"{hour_str}*.csv"
    )

    files = list(
        TRAFFIC_DIR.glob(pattern)
    )

    if not files:
        return None

    return pd.read_csv(files[0], sep=";")


app = Flask(__name__)

# =========================
# Real Valencia Graph
# =========================
G = ox.graph_from_place("Valencia, Spain", network_type="drive")

SEGMENT_MAPPING = build_segment_mapping()
print(len(SEGMENT_MAPPING))
def apply_snapshot(snapshot):

    state_to_flow = {
        0: 50,
        1: 200,
        2: 500,
        3: 1000,
        4: 2000,
        5: 4000
    }

    for _, row in snapshot.iterrows():

        segment_id = row[
            "Id. Tram / Id. Tramo"
        ]

        if segment_id not in SEGMENT_MAPPING:
            continue

        u, v, k = SEGMENT_MAPPING[
            segment_id
        ]

        flow = state_to_flow.get(
            row["Estat / Estado"],
            100
        )

        G[u][v][k]["base_flow"] = flow


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
    "date": "31-12-2022",
    "hour": "00-00",
    "selected_edge": None,
    "closed_edges": set(),
    "traffic_alert": {
        "interrupted": False,
        "suggested_reopenings": []
    }
}

# =========================
# Changing hour
# =========================
@app.route("/api/set_hour", methods=["POST"])
def set_hour():

    data = request.get_json()

    hour = int(data["hour"])

    scenario["hour"] = f"{hour:02d}-00"

    return jsonify({
        "ok": True,
        "hour": scenario["hour"]
    })

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
    # Reset the alert after each call
    scenario["traffic_alert"] = {
        "interrupted": False,
        "suggested_reopenings": []
    }

    # 1. Reset initial state using historical data from the snapshot
    snapshot = load_traffic_snapshot(scenario["date"], scenario["hour"])
    if snapshot is not None:
        apply_snapshot(snapshot)
    else:
        for u, v, k, data in G.edges(keys=True, data=True):
            data["base_flow"] = max(50, int(1000 / (data.get("length", 100) + 1)))

    for u, v, k, data in G.edges(keys=True, data=True):
        data["flow"] = data["base_flow"]

    if not scenario["closed_edges"]:
        return

    # 2. Make a copy to calculate reroutes
    G_temp = G.copy()
    for u, v in scenario["closed_edges"]:
        for k in G[u][v]:
            G[u][v][k]["base_flow"] = G[u][v][k]["flow"]
            G[u][v][k]["flow"] = 0
            
        if G_temp.has_edge(u, v):
            for k in G_temp[u][v]:
                G_temp[u][v][k]["length"] = 9999999  # Extreme penalty to avoid taking it

    # 3. Redistribute closed streets flow
    for u, v in scenario["closed_edges"]:
        if not G.has_edge(u, v):
            continue
            
        for k in G[u][v]:
            trapped_flow = G[u][v][k]["base_flow"]
            if trapped_flow <= 0:
                continue
                
            try:
                # Look for alternative path
                alternative_path = nx.shortest_path(G_temp, source=u, target=v, weight="length")
                
                # Redirect traffic
                for i in range(len(alternative_path) - 1):
                    alt_u = alternative_path[i]
                    alt_v = alternative_path[i+1]
                    for alt_k in G[alt_u][alt_v]:
                        G[alt_u][alt_v][alt_k]["flow"] += trapped_flow
                        
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                scenario["traffic_alert"]["interrupted"] = True
                
                # Get closed street names to suggest
                suggested = []
                for cu, cv in scenario["closed_edges"]:
                    # Try to get the name from the graph
                    edge_data = G[cu][cv][0]
                    street_name = edge_data.get("name", f"Calle ({cu} -> {cv})")
                    
                    # If OSM returns a list
                    if isinstance(street_name, list):
                        street_name = " / ".join(street_name)
                        
                    street_info = {"u": cu, "v": cv, "name": street_name}
                    if street_info not in suggested:
                        suggested.append(street_info)
                
                scenario["traffic_alert"]["suggested_reopenings"] = suggested
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


def impacted_streets():

    streets = []

    for u, v, k, data in G.edges(keys=True, data=True):

        increase = data["flow"] - data["base_flow"]

        if increase <= 0:
            continue

        name = data.get("name", "Unknown street")

        if isinstance(name, list):
            name = " / ".join(name)

        streets.append({
            "street": name,
            "increase": round(increase, 1)
        })

    streets.sort(
        key=lambda x: x["increase"],
        reverse=True
    )

    return streets[:10]


# =========================
# WEB VIEW
# =========================
@app.route("/")
def map_view():
    return render_template("map.html")

@app.route("/analytics")
def analytics_page():
    return render_template(
        "analytics.html"
    )

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
        "edges": edge_list(),
        "alert": scenario["traffic_alert"],
        "impacted": impacted_streets()
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
    if scenario["selected_edge"] is None:
        return jsonify({
            "error": "No street selected"
        }), 400
    u, v = scenario["selected_edge"]
    scenario["closed_edges"].add((u, v))
    return jsonify({"ok": True})


# =========================
# OPEN EDGE (STREET)
# =========================
@app.route("/api/open_edge", methods=["POST"])
def open_edge():
    if scenario["selected_edge"] is None:
        return jsonify({
            "error": "No street selected"
        }), 400
    u, v = scenario["selected_edge"]
    scenario["closed_edges"].discard((u, v))
    return jsonify({"ok": True})


# =========================
# SIMPLE ANALYSIS
# =========================
@app.route("/api/analytics")
def analytics():

    compute_flows()

    if scenario["selected_edge"]:

        u,v = scenario["selected_edge"]

        edge = next(
            iter(G[u][v].values())
        )

        street_name = edge.get(
            "name",
            "Unknown street"
        )

        if isinstance(
            street_name,
            list
        ):
            street_name = " / ".join(
                street_name
            )

        return jsonify({

            "mode":"street",

            "street":street_name,

            "flow":[
                edge["base_flow"]*0.5,
                edge["base_flow"]*0.7,
                edge["base_flow"],
                edge["flow"]
            ],

            "labels":[
                "Night",
                "Morning",
                "Normal",
                "Current"
            ],

            "congestion":edge["congestion"],

            "length":round(
                edge["length"],
                1
            )
        })

    avg_congestion = sum(
        d["congestion"]
        for d in edge_list()
    ) / max(
        len(edge_list()),
        1
    )

    closed = len(
        scenario["closed_edges"]
    )

    return jsonify({

        "mode":"global",

        "average_congestion":
            round(
                avg_congestion,
                2
            ),

        "closed_streets":
            closed,

        "flow":[
            800,
            1200,
            1800,
            1600,
            900
        ],

        "labels":[
            "06",
            "08",
            "12",
            "18",
            "22"
        ]
    })


if __name__ == "__main__":
    app.run(debug=True)