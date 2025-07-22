import streamlit as st
import requests
from streamlit_folium import st_folium
import folium
import os
from dotenv import load_dotenv
from pyproj import Transformer

load_dotenv()
API_KEY = os.getenv("LANDAPP_API_KEY", "")
API_BASE = "https://integration-api.thelandapp.com"

# Set up transformer for BNG to WGS84
bng_to_wgs84 = Transformer.from_crs("epsg:27700", "epsg:4326", always_xy=True)

def reproject_coords(coords):
    # Handles both single and nested coordinate lists
    if isinstance(coords[0], (float, int)):
        return list(bng_to_wgs84.transform(*coords))
    return [reproject_coords(c) for c in coords]

def reproject_feature(feature):
    geom = feature.get("geometry", {})
    if geom.get("type") in ["Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"]:
        geom["coordinates"] = reproject_coords(geom["coordinates"])
    feature["geometry"] = geom
    return feature

def get_all_coords(features):
    coords = []
    def extract_coords(geom_coords):
        if isinstance(geom_coords[0], (float, int)):
            coords.append(geom_coords)
        else:
            for c in geom_coords:
                extract_coords(c)
    for feature in features:
        geom = feature.get("geometry", {})
        if "coordinates" in geom:
            extract_coords(geom["coordinates"])
    return coords

TEMPLATE_TYPES = [
    "BPS", "CSS", "FRM", "RLE1", "OWNERSHIP", "FR1", "SALES_PLAN", "VALUATION_PLAN", "ESS", "UKHAB", "UKHAB_V2", "USER", "LAND_MANAGEMENT", "LAND_MANAGEMENT_V2", "SFI2022", "SFI2023", "SFI2024", "PEAT_ASSESSMENT", "OSMM", "FER", "WCT", "BLANK_SURVEY", "SOIL_SURVEY", "AGROFORESTRY", "CSS_2025", "HEALTHY_HEDGEROWS", "SAF"
]

# User input for API key
api_key_input = st.text_input("Enter your Land App API Key", value="", type="password")

# User selects template type
selected_template = st.selectbox(
    "Select a template type",
    TEMPLATE_TYPES,
    index=0,
    format_func=lambda x: {
        "BPS": "BPS – Basic Payment Scheme",
        "CSS": "CSS – Countryside Stewardship",
        "FRM": "FRM – Field Risk Map",
        "RLE1": "RLE1 form",
        "OWNERSHIP": "OWNERSHIP – Ownership Boundary",
        "FR1": "FR1 – Land Registration (FR1)",
        "SALES_PLAN": "SALES_PLAN – Sales Plan",
        "VALUATION_PLAN": "VALUATION_PLAN – Valuation Plan",
        "ESS": "ESS – Environmental Stewardship",
        "UKHAB": "UKHAB – Baseline Habitat Assessment*",
        "UKHAB_V2": "UKHAB_V2 - Baseline Habitat Assessment (UKHab 2.0)*",
        "USER": "USER – Blank user plan",
        "LAND_MANAGEMENT": "LAND_MANAGEMENT – Land Management Plan*",
        "LAND_MANAGEMENT_V2": "LAND_MANAGEMENT_V2 - Land Management Plan (UKHab 2.0)*",
        "SFI2022": "SFI2022 - Sustainable Farm Incentive 22 (SFI 22)*",
        "SFI2023": "SFI2023 - Sustainable Farm Incentive 23 (SFI 23)*",
        "SFI2024": "SFI2024 - Sustainable Farm Incentive 24 (SFI 24)*",
        "PEAT_ASSESSMENT": "PEAT_ASSESSMENT - Peat Condition Assessment",
        "OSMM": "OSMM - Ordnance Survey MasterMap",
        "FER": "FER - Farm Environment Record",
        "WCT": "WCT - Woodland Creation Template",
        "BLANK_SURVEY": "BLANK_SURVEY - General Data Collection (Mobile Survey)",
        "SOIL_SURVEY": "SOIL_SURVEY - Soil Sampling",
        "AGROFORESTRY": "AGROFORESTRY - Agroforestry Design",
        "CSS_2025": "CSS_2025 - Countryside Stewardship Higher-Tier (2025)",
        "HEALTHY_HEDGEROWS": "HEALTHY_HEDGEROWS - Healthy Hedgerows Survey",
        "SAF": "SAF - Single Application Form"
    }.get(x, x)
)

# 1. Fetch projects (now takes api_key and template_type)
def fetch_projects(api_key, template_type):
    url = f"{API_BASE}/projects?apiKey={api_key}&page=0&size=1000&type={template_type}&from=2025-01-01T06:00:00.000Z"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

# 2. Fetch features for a project
def fetch_features(project_id, api_key):
    url = f"{API_BASE}/projects/{project_id}/features?apiKey={api_key}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("data", [])

# Main app
if not api_key_input:
    # Show a blank map of Great Britain
    m = folium.Map(location=[54.5, -3], zoom_start=6)  # Centered on GB
    st_folium(m, width=700, height=500)
else:
    projects = fetch_projects(api_key_input, selected_template)
    project_options = {proj["name"]: proj["id"] for proj in projects}

    selected_project = st.selectbox("Select a plan", list(project_options.keys()))

    if selected_project:
        project_id = project_options[selected_project]

        # Add a refresh button
        if 'refresh' not in st.session_state:
            st.session_state['refresh'] = 0
        if st.button('Refresh Features'):
            st.session_state['refresh'] += 1

        # Use session state to trigger re-fetch
        features = fetch_features(project_id, api_key_input)
        st.write(f"Found {len(features)} features for plan '{selected_project}'")

        # Reproject features (ensure all downstream code uses reprojected features)
        features_reprojected = [reproject_feature(f) for f in features]

        # Create a folium map
        m = folium.Map(location=[51.5, -0.1], zoom_start=6)  # Default UK center

        # Add features as GeoJSON with thicker lines
        for feature in features_reprojected:
            folium.GeoJson(
                feature,
                style_function=lambda x: {
                    "color": "#3388ff",
                    "weight": 5,  # Increased line thickness
                    "opacity": 1.0,
                    "fillOpacity": 0.2,
                }
            ).add_to(m)

        # Zoom to bounds (use reprojected features)
        all_coords = get_all_coords(features_reprojected)
        if all_coords:
            lats, lons = zip(*all_coords)
            m.fit_bounds([[min(lons), min(lats)], [max(lons), max(lats)]])

        st_folium(m, width=700, height=500)