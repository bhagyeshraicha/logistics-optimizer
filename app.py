import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import math

# --- CONFIG ---
st.set_page_config(page_title="Logistics AI (Analytics)", layout="wide")
st.title("🚛 AI Last-Mile Delivery Optimizer")
st.markdown("### Route Planning & Feasibility Analysis")

# --- SESSION STATE ---
if 'routes' not in st.session_state:
    st.session_state.routes = []
if 'results' not in st.session_state:
    st.session_state.results = []

# --- MATH HELPER ---
def get_dist_km(p1, p2):
    # Haversine Formula for accurate km
    R = 6371  # Earth radius in km
    dlat = math.radians(p2[0] - p1[0])
    dlon = math.radians(p2[1] - p1[1])
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(p1[0])) * math.cos(math.radians(p2[0])) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- ALGORITHM ---
def solve_fast_vrp(df, num_vehicles):
    points = df[['lat', 'lon', 'Location_Name']].values.tolist()
    depot = points[0]
    customers = points[1:]
    
    # Sort geographically to cluster roughly
    customers.sort(key=lambda x: x[1])
    
    chunk_size = math.ceil(len(customers) / num_vehicles)
    vehicle_routes = []
    vehicle_stats = [] # Store distance per vehicle
    
    for i in range(num_vehicles):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        chunk = customers[start_idx:end_idx]
        
        if not chunk:
            continue
            
        # Nearest Neighbor Optimization
        route = [depot]
        unvisited = chunk.copy()
        current_loc = depot
        route_dist = 0
        
        while unvisited:
            # Find closest
            nearest = min(unvisited, key=lambda x: get_dist_km(current_loc, x))
            dist_leg = get_dist_km(current_loc, nearest)
            
            route.append(nearest)
            route_dist += dist_leg
            
            unvisited.remove(nearest)
            current_loc = nearest
            
        # Return to depot
        return_dist = get_dist_km(current_loc, depot)
        route.append(depot)
        route_dist += return_dist
        
        vehicle_routes.append(route)
        vehicle_stats.append({
            "id": i+1,
            "stops": len(route) - 2, # Exclude start/end depot
            "dist_km": route_dist
        })
        
    return vehicle_routes, vehicle_stats

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    # Reset on new file
    if uploaded_file and 'last_file' not in st.session_state:
        st.session_state.last_file = uploaded_file.name
        st.session_state.routes = []

    st.divider()
    st.header("2. Operational Limits")
    num_vehicles = st.slider("Fleet Size (Vehicles)", 1, 10, 4)
    max_time = st.slider("Shift Duration (Hours)", 1, 12, 4, help="Max time allowed for delivery")
    service_time_min = st.number_input("Time per Stop (mins)", value=10, help="Time spent parking/handing over package")
    
    btn = st.button("🚀 Optimize & Analyze", type="primary")

# --- MAIN LOGIC ---
if uploaded_file:
    # Load & Clean
    try:
        df = pd.read_csv(uploaded_file)
        # Clean coordinates
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        df = df.dropna(subset=['lat', 'lon'])
        
        # --- OPTIMIZATION TRIGGER ---
        if btn:
            routes, stats = solve_fast_vrp(df, num_vehicles)
            st.session_state.routes = routes
            st.session_state.results = stats
            st.session_state.data = df # Persist data

    except Exception as e:
        st.error(f"Data Error: {e}")

# --- DISPLAY RESULTS ---
if 'data' in st.session_state:
    df = st.session_state.data
    routes = st.session_state.routes
    stats = st.session_state.results
    
    # 1. MAP (Top)
    col_map, col_stats = st.columns([2, 1])
    
    with col_map:
        st.subheader("🗺️ Live Route Map")
        mid_lat = df['lat'].mean()
        mid_lon = df['lon'].mean()
        m = folium.Map(location=[mid_lat, mid_lon], zoom_start=12, tiles="cartodbpositron")
        
        # Plot Points
        for i, row in df.iterrows():
            color = "red" if i == 0 else "blue"
            icon = "home" if i == 0 else "box"
            folium.Marker([row['lat'], row['lon']], 
                          popup=str(row['Location_Name']),
                          icon=folium.Icon(color=color, icon=icon, prefix='fa')).add_to(m)
            
        # Plot Routes
        colors = ['#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4']
        for i, route in enumerate(routes):
            points = [[p[0], p[1]] for p in route]
            folium.PolyLine(points, color=colors[i % len(colors)], weight=4, tooltip=f"Vehicle {i+1}").add_to(m)
            
        st_folium(m, width=800, height=500)

    # 2. ANALYTICS TABLE (Right Side)
    with col_stats:
        st.subheader("📊 Fleet Performance")
        
        if stats:
            # Create Analysis DataFrame
            analysis_data = []
            
            for v in stats:
                dist = v['dist_km']
                stops = v['stops']
                
                # Math: Time Calculation
                # Time spent stopped = stops * 10 mins
                stop_time_hours = (stops * service_time_min) / 60
                
                # Driving Time Available = Total Shift - Stop Time
                drive_time_available = max_time - stop_time_hours
                
                if drive_time_available <= 0:
                    req_speed = 999 # Impossible
                    status = "❌ IMPOSSIBLE"
                    reason = "Not enough time for stops!"
                else:
                    # Speed = Distance / Time
                    req_speed = dist / drive_time_available
                    
                    if req_speed > 60:
                        status = "⚠️ HIGH RISK"
                        reason = "Speed too high"
                    elif req_speed > 30:
                        status = "✅ OPTIMAL"
                        reason = "Standard City Speed"
                    else:
                        status = "🟢 EASY"
                        reason = "Plenty of time"

                analysis_data.append({
                    "Vehicle": f"🚛 V{v['id']}",
                    "Stops": stops,
                    "Dist (km)": round(dist, 1),
                    "Req. Speed (km/h)": round(req_speed, 1),
                    "Status": status
                })
            
            # Display as a clean table
            st.dataframe(pd.DataFrame(analysis_data).set_index("Vehicle"), use_container_width=True)
            
            # Show Global Metrics
            total_km = sum(s['dist_km'] for s in stats)
            st.metric("Total Fleet Distance", f"{total_km:.1f} km")
            
            # Warning Logic
            if any(d['Status'] == "❌ IMPOSSIBLE" for d in analysis_data):
                st.error("🚨 Critical Alert: Shift time is too short for the number of stops!")
            elif any(d['Status'] == "⚠️ HIGH RISK" for d in analysis_data):
                st.warning("⚠️ Warning: Drivers must speed to meet the deadline.")
            else:
                st.success("✅ Plan is feasible.")

elif uploaded_file:
    st.info("File Loaded. Adjust settings and click Optimize.")
else:
    st.info("Please upload 'final_delivery_data.csv' to begin.")
