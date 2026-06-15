from flask import Flask, render_template, jsonify, request
import osmnx as ox
import networkx as nx
from pathlib import Path
import pandas as pd
from functools import lru_cache
import json
import pickle
import os
import re


TRAFFIC_DIR = Path("traffic_data")

app = Flask(__name__)


# =========================
# Real Valencia Graph
# =========================
G = ox.graph_from_place("Valencia, Spain", network_type="drive")


# =========================
# Traffic CSV helpers
# =========================
def get_reference_csv():
    """
    Finds one traffic CSV file to build the mapping between Valencia traffic
    segment IDs and OSMnx graph edges.

    rglob searches recursively, so CSV files can be inside subfolders such as:
    traffic_data/estat_trafic_VLC-main/...
    """
    files = sorted(
        TRAFFIC_DIR.rglob("estat_traf*.csv")
    )

    if not files:
        raise RuntimeError(
            "No traffic CSV found. Put at least one estat_traf*.csv file inside traffic_data."
        )

    print("Reference CSV:", files[0])
    return str(files[0])


@lru_cache(maxsize=100)
def load_traffic_snapshot(date_str, hour_str):
    """
    Loads one traffic CSV for a specific date and hour.

    Expected filename pattern:
    estat_trafDD-MM-YYYY_HH-00-XX.csv

    Example:
    estat_traf01-01-2023_08-00-02.csv
    """
    pattern = f"estat_traf{date_str}_{hour_str}*.csv"

    files = sorted(
        TRAFFIC_DIR.rglob(pattern)
    )

    print("Searching traffic file:", pattern)
    print("Found:", files[:3])

    if not files:
        return None

    return pd.read_csv(files[0], sep=";")


def build_segment_mapping():
    """
    Maps traffic segment IDs from the CSV files to the nearest OSMnx edges.
    The result is cached because this step can be slow.
    """
    cache_file = "cache/segment_mapping.pkl"

    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    print("Building traffic mapping...")

    df = pd.read_csv(
        get_reference_csv(),
        sep=";"
    )

    mapping = {}

    for _, row in df.iterrows():

        try:
            geometry = json.loads(
                row["geo_shape"]
            )

            coords = geometry["coordinates"]

            midpoint = coords[
                len(coords) // 2
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


SEGMENT_MAPPING = build_segment_mapping()
print("Mapped traffic segments:", len(SEGMENT_MAPPING))


# =========================
# Starting scenario
# =========================
scenario = {
    # Change this if your default available date is different.
    # Browser date picker value 2023-01-01 becomes 01-01-2023 here.
    "date": "01-01-2023",
    "hour": "00-00",
    "selected_edge": None,
    "closed_edges": set(),
    "traffic_alert": {
        "interrupted": False,
        "suggested_reopenings": []
    }
}


# =========================
# Apply traffic snapshot
# =========================
def apply_snapshot(snapshot):
    """
    Converts traffic status values from the CSV into approximate flow values.
    This is a simplified modelling step for the prototype.
    """
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

        if G.has_edge(u, v, k):
            G[u][v][k]["base_flow"] = flow


# =========================
# Initial default flows
# =========================
def init_flows():
    for u, v, k, data in G.edges(keys=True, data=True):
        base = max(
            50,
            int(1000 / (data.get("length", 100) + 1))
        )
        data["base_flow"] = base
        data["flow"] = base


init_flows()


# =========================
# Utility helpers
# =========================
def get_first_edge_data(u, v):
    """
    Safely returns the first edge data object between u and v.
    OSMnx MultiDiGraphs can have different edge keys, not always key 0.
    """
    if not G.has_edge(u, v):
        return None

    return next(iter(G[u][v].values()))


def get_street_name(edge_data, fallback="Unknown street"):
    name = edge_data.get("name", fallback)

    if isinstance(name, list):
        name = " / ".join(name)

    return name


def calculate_congestion(edge_data):
    return round(
        edge_data.get("flow", 1) / max(edge_data.get("base_flow", 1), 1),
        2
    )


# =========================
# Flow estimation after closing edges
# =========================
def compute_flows():
    """
    1. Loads the current traffic snapshot for selected date/hour.
    2. Resets all flows to base flows.
    3. If streets are closed, removes them from a temporary graph.
    4. Redistributes the trapped flow through alternative paths.
    """
    scenario["traffic_alert"] = {
        "interrupted": False,
        "suggested_reopenings": []
    }

    # 1. Reset initial state using historical data from the selected snapshot
    snapshot = load_traffic_snapshot(
        scenario["date"],
        scenario["hour"]
    )

    if snapshot is not None:
        apply_snapshot(snapshot)
    else:
        print(
            f"No snapshot found for date={scenario['date']} hour={scenario['hour']}. Using fallback values."
        )

        for u, v, k, data in G.edges(keys=True, data=True):
            data["base_flow"] = max(
                50,
                int(1000 / (data.get("length", 100) + 1))
            )

    # Reset current flow to base flow
    for u, v, k, data in G.edges(keys=True, data=True):
        data["flow"] = data["base_flow"]

    if not scenario["closed_edges"]:
        return

    # 2. Store trapped flow BEFORE setting closed streets to zero
    trapped_flows = []

    for u, v in scenario["closed_edges"]:

        if not G.has_edge(u, v):
            continue

        for k in list(G[u][v].keys()):

            trapped_flow = G[u][v][k].get("base_flow", 0)

            trapped_flows.append({
                "u": u,
                "v": v,
                "k": k,
                "flow": trapped_flow
            })

            # The closed street itself has no current traffic
            G[u][v][k]["flow"] = 0

    # 3. Create a temporary graph and REALLY remove closed streets
    G_temp = G.copy()

    for u, v in scenario["closed_edges"]:

        if G_temp.has_edge(u, v):
            for k in list(G_temp[u][v].keys()):
                G_temp.remove_edge(u, v, k)

    # 4. Redistribute the trapped flow to alternative paths
    for item in trapped_flows:

        u = item["u"]
        v = item["v"]
        trapped_flow = item["flow"]

        if trapped_flow <= 0:
            continue

        try:
            alternative_path = nx.shortest_path(
                G_temp,
                source=u,
                target=v,
                weight="length"
            )

            for i in range(len(alternative_path) - 1):

                alt_u = alternative_path[i]
                alt_v = alternative_path[i + 1]

                # Never add traffic back to a closed street
                if (alt_u, alt_v) in scenario["closed_edges"]:
                    continue

                if not G.has_edge(alt_u, alt_v):
                    continue

                for alt_k in G[alt_u][alt_v]:

                    # Extra safety: skip if this exact edge is closed
                    if (alt_u, alt_v) in scenario["closed_edges"]:
                        continue

                    G[alt_u][alt_v][alt_k]["flow"] += trapped_flow

        except (nx.NetworkXNoPath, nx.NodeNotFound):

            scenario["traffic_alert"]["interrupted"] = True

            suggested = []

            for cu, cv in scenario["closed_edges"]:

                edge_data = get_first_edge_data(cu, cv)

                if edge_data is None:
                    continue

                street_name = get_street_name(
                    edge_data,
                    f"Calle ({cu} -> {cv})"
                )

                street_info = {
                    "u": cu,
                    "v": cv,
                    "name": street_name
                }

                if street_info not in suggested:
                    suggested.append(street_info)

            scenario["traffic_alert"]["suggested_reopenings"] = suggested

# =========================
# Edge info
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
            "congestion": calculate_congestion(data),
            "closed": (u, v) in scenario["closed_edges"],
            "selected": scenario["selected_edge"] == (u, v)
        })

    return edges


def impacted_streets():
    street_impacts = {}

    for u, v, k, data in G.edges(keys=True, data=True):

        increase = data.get("flow", 0) - data.get("base_flow", 0)

        if increase <= 0:
            continue

        name = get_street_name(
            data,
            "Unknown street"
        )

        if name not in street_impacts:
            street_impacts[name] = {
                "street": name,
                "increase": 0,
                "segments": 0
            }

        street_impacts[name]["increase"] += increase
        street_impacts[name]["segments"] += 1

    streets = list(street_impacts.values())

    for street in streets:
        street["increase"] = round(street["increase"], 1)

    streets.sort(
        key=lambda x: x["increase"],
        reverse=True
    )

    return streets[:10]


# =========================
# Web views
# =========================
@app.route("/")
def map_view():
    return render_template("map.html")


@app.route("/analytics")
def analytics_page():
    return render_template("analytics.html")


@app.route("/analysis/<int:node>")
def analysis_view(node):
    return render_template("analysis.html", node=node)


# =========================
# API: GeoJSON
# =========================
@app.route("/api/geojson")
def geojson():
    nodes, edges = ox.graph_to_gdfs(
        G,
        nodes=True,
        edges=True
    )

    edges = edges.reset_index()
    edges = edges.to_crs(epsg=4326)

    edges["edge_id"] = (
        edges["u"].astype(str) + "_" +
        edges["v"].astype(str) + "_" +
        edges["key"].astype(str)
    )

    return edges.__geo_interface__


# =========================
# API: Change hour
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
# API: Change date
# =========================
@app.route("/api/set_date", methods=["POST"])
def set_date():

    data = request.get_json()

    date = data["date"]

    # Convert YYYY-MM-DD from browser date picker to DD-MM-YYYY for file names
    year, month, day = date.split("-")

    scenario["date"] = f"{day}-{month}-{year}"

    return jsonify({
        "ok": True,
        "date": scenario["date"]
    })

# =========================
# API: Available traffic snapshots
# =========================
@app.route("/api/available_snapshots")
def available_snapshots():

    snapshots = {}

    pattern = re.compile(
        r"estat_traf(\d{2}-\d{2}-\d{4})_(\d{2})-(\d{2})-\d{2}\.csv"
    )

    files = sorted(
        TRAFFIC_DIR.rglob("estat_traf*.csv")
    )

    for file in files:

        match = pattern.match(file.name)

        if not match:
            continue

        date = match.group(1)
        hour = match.group(2)
        minute = match.group(3)

        # Keep only full-hour snapshots because the current slider works hourly
        if minute != "00":
            continue

        day, month, year = date.split("-")
        browser_date = f"{year}-{month}-{day}"

        if browser_date not in snapshots:
            snapshots[browser_date] = []

        if hour not in snapshots[browser_date]:
            snapshots[browser_date].append(hour)

    for date in snapshots:
        snapshots[date].sort()

    return jsonify({
        "snapshots": snapshots
    })


# =========================
# API: State
# =========================
@app.route("/api/state")
def state():

    compute_flows()

    return jsonify({
        "date": scenario["date"],
        "hour": scenario["hour"],
        "closed_edges": list(scenario["closed_edges"]),
        "edges": edge_list(),
        "alert": scenario["traffic_alert"],
        "impacted": impacted_streets()
    })


# =========================
# API: Select edge / street
# =========================
@app.route("/api/select_edge", methods=["POST"])
def select_edge():

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

    edge_data = get_first_edge_data(u, v)

    if edge_data is None:
        return jsonify({"error": "Selected edge not found"}), 404

    return jsonify({
        "u": u,
        "v": v,
        "name": get_street_name(edge_data, "Sin nombre"),
        "length": edge_data.get("length", 0),
        "flow": edge_data.get("flow", 0),
        "base_flow": edge_data.get("base_flow", 0),
        "congestion": calculate_congestion(edge_data),
        "closed": (u, v) in scenario["closed_edges"]
    })


# =========================
# API: Close selected street
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
# API: Open selected street
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
# API: Analytics
# =========================
@app.route("/api/analytics")
def analytics():

    compute_flows()

    impacted = impacted_streets()
    edges = edge_list()

    closed_edges = [
        edge for edge in edges
        if edge["closed"]
    ]

    total_flow = sum(
        edge["flow"]
        for edge in edges
    )

    total_base_flow = sum(
        edge["base_flow"]
        for edge in edges
    )

    total_increase = total_flow - total_base_flow

    avg_congestion = sum(
        edge["congestion"]
        for edge in edges
    ) / max(len(edges), 1)

    most_congested = max(
        edges,
        key=lambda edge: edge["congestion"],
        default={"congestion": 0, "flow": 0}
    )

    # =========================
    # Street mode
    # =========================
    force_global = request.args.get("mode") == "global"

    if scenario["selected_edge"] and not force_global:

        u, v = scenario["selected_edge"]

        edge_data = get_first_edge_data(u, v)

        if edge_data is None:
            return jsonify({
                "error": "Selected street not found"
            }), 404

        street_name = get_street_name(
            edge_data,
            "Unknown street"
        )

        base_flow = edge_data.get("base_flow", 0)
        current_flow = edge_data.get("flow", 0)

        flow_change = current_flow - base_flow

        congestion = calculate_congestion(edge_data)

        is_closed = (u, v) in scenario["closed_edges"]

        if is_closed:
            insight_text = (
                "The selected street is currently closed. "
                "Its traffic flow is redirected to alternative routes."
            )
        elif flow_change > 0:
            insight_text = (
                "The selected street receives additional traffic because of the current scenario."
            )
        elif flow_change < 0:
            insight_text = (
                "The selected street currently has less traffic than in the baseline."
            )
        else:
            insight_text = (
                "The selected street has no relevant traffic change compared to the baseline."
            )

        return jsonify({
            "mode": "street",

            "date": scenario["date"],
            "hour": scenario["hour"],

            "street": street_name,

            "status": "Closed" if is_closed else "Open",

            "flow": [
                round(base_flow, 1),
                round(current_flow, 1)
            ],

            "labels": [
                "Base flow",
                "Current flow"
            ],

            "base_flow": round(base_flow, 1),
            "current_flow": round(current_flow, 1),
            "flow_change": round(flow_change, 1),

            "congestion": congestion,

            "length": round(
                edge_data.get("length", 0),
                1
            ),

            "closed_streets": len(scenario["closed_edges"]),

            "impacted": impacted,

            "insight_text": insight_text
        })

    # =========================
    # Global mode
    # =========================
    if len(scenario["closed_edges"]) == 0:
        insight_text = (
            "No streets are currently closed. The dashboard shows the baseline traffic situation "
            "for the selected date and hour."
        )
    elif total_increase > 0:
        insight_text = (
            "The current street closure scenario redistributes traffic through the network. "
            "The most impacted streets show where additional traffic is concentrated."
        )
    else:
        insight_text = (
            "The current scenario does not create a strong global traffic increase, "
            "but local effects may still be visible on individual streets."
        )

    return jsonify({
        "mode": "global",

        "date": scenario["date"],
        "hour": scenario["hour"],

        "average_congestion": round(
            avg_congestion,
            2
        ),

        "most_congested": round(
            most_congested["congestion"],
            2
        ),

        "closed_streets": len(
            scenario["closed_edges"]
        ),

        "total_flow": round(
            total_flow,
            1
        ),

        "total_base_flow": round(
            total_base_flow,
            1
        ),

        "total_increase": round(
            total_increase,
            1
        ),

        "flow": [
            round(total_base_flow, 1),
            round(total_flow, 1)
        ],

        "labels": [
            "Base flow",
            "Current flow"
        ],

        "impacted": impacted,

        "insight_text": insight_text
    })


if __name__ == "__main__":
    app.run(debug=True)
