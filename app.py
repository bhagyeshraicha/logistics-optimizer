import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import math
import numpy as np

# --- CONFIG ---
st.set_page_config(page_title="Logistics AI (Lite)", layout="wide")
st.title("🚛 AI Last-Mile Delivery Optimizer")
st.markdown("### Fast Route Optimization System")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    st.header("2. Settings")
    num_vehicles = st.slider("Number of Vehicles", 1, 10, 4)
    st.info("Using Nearest-Neighbor Algorithm for instant results.")
    
    run_btn = st.button("🚀 Optimize Now", type="primary")

# --- FAST ALGORITHM (No Heavy Libraries) ---
def get_dist(p1, p2):
    # Simple Euclidean approximation for speed (sufficient for local cities)
    # or Haversine if you prefer. Using simple deg diff for max speed here.
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def solve_fast_vrp(df, num_vehicles):
    # Convert dataframe to list of [lat, lon, name]
    points = df[['lat', 'lon', 'Location_Name']].values.tolist()
    
    depot = points[0] # First row is Warehouse
    customers = points[1:]
    
    # 1. Cluster customers based on angle/location to split among vehicles
    # We sort by longitude to sweep across the city
    customers.sort(key=lambda x: x[1])
    
    # Split into chunks for each vehicle
    chunk_size = math.ceil(len(customers) / num_vehicles)
    vehicle_routes = []
    
    for i in range(num_vehicles):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        chunk = customers[start_idx:end_idx]
        
        if not chunk:
            continue
            
        # 2. Optimize the route for this vehicle (Nearest Neighbor)
        route = [depot]
        unvisited = chunk.copy()
        current_loc = depot
        
        while unvisited:
            # Find closest next stop
            nearest = min(unvisited, key=lambda x: get_dist(current_loc, x))
            route.append(nearest)
            unvisited.remove(nearest)
            current_loc = nearest
            
        route.append(depot) # Return home
        vehicle_routes.append(route)
        
    return vehicle_routes

# --- MAIN APP ---
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # --- THE FIX FOR STRINGS ---
        # This block forces everything to numbers and deletes bad rows
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        initial_count = len(df)
        df = df.dropna(subset=['lat', 'lon'])
        
        if len(df) < initial_count:
            st.warning(f"Cleaned data: Removed {initial_count - len(df)} rows containing text/errors.")
        
        # ---------------------------

        # Layout
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("📍 Data Preview")
            st.dataframe(df[['Location_Name']].head(10), height=300)
            st.caption(f"Total stops: {len(df)}")

        # Map Setup
        mid_lat = df['lat'].mean()
        mid_lon = df['lon'].mean()
        m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles="cartodbpositron")

        # Plot all points
        for i, row in df.iterrows():
            color = "red" if i == 0 else "blue" # Warehouse = Red
            icon = "home" if i == 0 else "map-marker"
            
            folium.Marker(
                [row['lat'], row['lon']],
                popup=str(row['Location_Name']),
                icon=folium.Icon(color=color, icon=icon, prefix='fa')
            ).add_to(m)

        if run_btn:
            with st.spinner("Calculating..."):
                routes = solve_fast_vrp(df, num_vehicles)
                
                # Colors for lines
                colors = ['red', 'blue', 'green', 'purple', 'orange', 'black']
                
                with col1:
                    st.success(f"✅ Dispatched {len(routes)} Vehicles!")
                
                for i, route in enumerate(routes):
                    # Extract just lat/lon for the line
                    line_points = [[p[0], p[1]] for p in route]
                    
                    folium.PolyLine(
                        line_points, 
                        color=colors[i % len(colors)], 
                        weight=4, 
                        opacity=0.8,
                        tooltip=f"Vehicle {i+1}"
                    ).add_to(m)

        with col2:
            st_folium(m, width=900, height=600)

    except Exception as e:
        st.error(f"Something went wrong: {e}")
