import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math

# --- CONFIG ---
st.set_page_config(page_title="Logistics AI", layout="wide")
st.title("🚛 AI Last-Mile Delivery Optimizer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Input Parameters")
    uploaded_file = st.file_uploader("Upload 'final_delivery_data.csv'", type=["csv"])
    
    st.divider()
    num_vehicles = st.slider("Number of Vehicles", 1, 10, 4)
    vehicle_capacity = st.slider("Vehicle Capacity", 10, 100, 25)
    
    run_btn = st.button("🚀 Optimize Route", type="primary")

# --- HELPER FUNCTIONS ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c * 1000) # Meters

def solve_vrp(df, num_vehicles, cap):
    # Data Model
    locs = df[['lat', 'lon']].values
    names = df['Location_Name'].tolist()
    demands = df['demand'].tolist()
    size = len(locs)
    
    # Matrix
    dist_matrix = [[0]*size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            dist_matrix[i][j] = calculate_distance(locs[i][0], locs[i][1], locs[j][0], locs[j][1])
            
    # OR-Tools
    manager = pywrapcp.RoutingIndexManager(size, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    def dist_cb(i, j):
        return dist_matrix[manager.IndexToNode(i)][manager.IndexToNode(j)]
    
    transit_cb = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)
    
    def demand_cb(i):
        return demands[manager.IndexToNode(i)]
    
    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(demand_cb_idx, 0, [cap]*num_vehicles, True, 'Capacity')
    
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    
    solution = routing.SolveWithParameters(params)
    return solution, routing, manager, dist_matrix

# --- MAIN APP ---
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # Layout: Map on Right, Stats on Left
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📍 Orders")
        st.dataframe(df[['Location_Name', 'demand']].head(10), height=200)
        st.caption("showing first 10 orders")

    # Base Map
    mid_lat = df['lat'].mean()
    mid_lon = df['lon'].mean()
    m = folium.Map(location=[mid_lat, mid_lon], zoom_start=13, tiles="cartodbpositron")

    # Add Points (Before Optimization)
    for i, row in df.iterrows():
        # Depot is red, others blue
        color = "red" if i == 0 else "blue"
        icon = "home" if i == 0 else "info-sign"
        
        folium.Marker(
            [row['lat'], row['lon']],
            popup=f"<b>{row['Location_Name']}</b><br>{row['Address']}",
            tooltip=row['Location_Name'],
            icon=folium.Icon(color=color, icon=icon)
        ).add_to(m)

    if run_btn:
        solution, routing, manager, dist_matrix = solve_vrp(df, num_vehicles, vehicle_capacity)
        
        if solution:
            total_dist = 0
            colors = ['#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231']
            
            with col1:
                st.success("✅ Optimization Complete!")
            
            # Draw Routes
            for vehicle_id in range(num_vehicles):
                index = routing.Start(vehicle_id)
                coords = []
                route_dist = 0
                
                while not routing.IsEnd(index):
                    node = manager.IndexToNode(index)
                    coords.append([df.iloc[node]['lat'], df.iloc[node]['lon']])
                    
                    prev_index = index
                    index = solution.Value(routing.NextVar(index))
                    route_dist += routing.GetArcCostForVehicle(prev_index, index, vehicle_id)
                
                # Add return to depot
                node = manager.IndexToNode(index)
                coords.append([df.iloc[node]['lat'], df.iloc[node]['lon']])
                
                total_dist += route_dist
                
                # Plot
                folium.PolyLine(
                    coords, 
                    color=colors[vehicle_id % len(colors)], 
                    weight=5, 
                    opacity=0.8,
                    tooltip=f"Vehicle {vehicle_id+1}"
                ).add_to(m)

            # Display Big Metrics
            col1.metric("Total Distance (Optimized)", f"{total_dist/1000:.2f} km")
            col1.metric("Vehicles Used", num_vehicles)

        else:
            st.error("Could not find a solution. Try increasing Vehicle Capacity.")

    with col2:
        st_folium(m, width=800, height=600)
