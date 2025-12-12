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

# --- SESSION STATE INITIALIZATION (The Fix) ---
if 'routes' not in st.session_state:
    st.session_state.routes = []
if 'total_dist' not in st.session_state:
    st.session_state.total_dist = 0

# --- FAST ALGORITHM ---
def get_dist(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def solve_fast_vrp(df, num_vehicles):
    points = df[['lat', 'lon', 'Location_Name']].values.tolist()
    depot = points[0]
    customers = points[1:]
    
    customers.sort(key=lambda x: x[1]) # Sort by longitude
    
    chunk_size = math.ceil(len(customers) / num_vehicles)
    vehicle_routes = []
    total_d = 0
    
    for i in range(num_vehicles):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        chunk = customers[start_idx:end_idx]
        
        if not chunk:
            continue
            
        route = [depot]
        unvisited = chunk.copy()
        current_loc = depot
        
        while unvisited:
            nearest = min(unvisited, key=lambda x: get_dist(current_loc, x))
            route.append(nearest)
            unvisited.remove(nearest)
            current_loc = nearest
            
        route.append(depot)
        vehicle_routes.append(route)
        
        # Calculate approximate distance for metrics
        for k in range(len(route)-1):
            total_d += get_dist(route[k], route[k+1]) * 111 # rough km conversion
            
    return vehicle_routes, total_d

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key="file_uploader")
    
    # Reset state if new file uploaded
    if uploaded_file and 'last_file' not in st.session_state:
        st.session_state.last_file = uploaded_file.name
        st.session_state.routes = []
    
    st.header("2. Settings")
    num_vehicles = st.slider("Number of Vehicles", 1, 10, 4)
    
    if st.button("🚀 Optimize Now", type="primary"):
        if uploaded_file:
            try:
                # Read and Process
                df = pd.read_csv(uploaded_file)
                df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
                df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
                df = df.dropna(subset=['lat', 'lon'])
                
                # Run Solver
                routes, dist = solve_fast_vrp(df, num_vehicles)
                
                # SAVE TO MEMORY (Crucial Step)
                st.session_state.routes = routes
                st.session_state.total_dist = dist
                st.session_state.data = df # Remember the clean data too
                
            except Exception as e:
                st.error(f"Error: {e}")

# --- MAIN PAGE DISPLAY ---
if uploaded_file and 'data' in st.session_state:
    df = st.session_state.data
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("📍 Metrics")
        if st.session_state.routes:
            st.metric("Total Estimated Dist", f"{st.session_state.total_dist:.2f} km")
            st.metric("Active Vehicles", len(st.session_state.routes))
            st.success("Optimization Active")
        else:
            st.info("Click Optimize to start.")
            
        st.dataframe(df[['Location_Name']].head(10), height=300)

    # --- MAP GENERATION ---
    mid_lat = df['lat'].mean()
    mid_lon = df['lon'].mean()
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles="cartodbpositron")

    # 1. Plot Points
    for i, row in df.iterrows():
        color = "red" if i == 0 else "blue"
        icon = "home" if i == 0 else "map-marker"
        folium.Marker(
            [row['lat'], row['lon']],
            popup=str(row['Location_Name']),
            icon=folium.Icon(color=color, icon=icon, prefix='fa')
        ).add_to(m)

    # 2. Plot Routes (Read from Memory)
    if st.session_state.routes:
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'black']
        for i, route in enumerate(st.session_state.routes):
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

elif uploaded_file:
    # First load before clicking button
    df = pd.read_csv(uploaded_file)
    st.info("File Uploaded. Click 'Optimize Now' in the sidebar.")
