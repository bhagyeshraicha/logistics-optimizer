import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import math

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Route Optimizer", layout="wide")

st.title("🚛 AI Last-Mile Delivery Optimizer")
st.markdown("Upload your delivery orders, set vehicle limits, and let AI find the best path.")

# --- SIDEBAR INPUTS ---
with st.sidebar:
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload CSV (Columns: lat, lon, demand)", type=["csv"])
    
    st.header("2. Fleet Settings")
    num_vehicles = st.slider("Number of Vehicles", 1, 10, 4)
    vehicle_capacity = st.slider("Vehicle Capacity (Items)", 10, 100, 20)
    
    st.header("3. Run AI")
    run_btn = st.button("Optimize Routes")

# --- MATH FUNCTIONS (The "Brain") ---
def calculate_distance(lat1, lon1, lat2, lon2):
    # Haversine formula for distance between coords
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c * 1000 # Return in meters

def create_data_model(df, num_vehicles, capacity):
    data = {}
    # Distance Matrix
    locs = df[['lat', 'lon']].values
    size = len(locs)
    dist_matrix = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            dist_matrix[i][j] = int(calculate_distance(locs[i][0], locs[i][1], locs[j][0], locs[j][1]))
    
    data['distance_matrix'] = dist_matrix
    data['demands'] = df['demand'].tolist()
    data['num_vehicles'] = num_vehicles
    data['vehicle_capacities'] = [capacity] * num_vehicles
    data['depot'] = 0 # Assume first row is the warehouse
    return data

def solve_vrp(data):
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    # Distance Constraint
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacity Constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')

    # Solve
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = routing.SolveWithParameters(search_parameters)
    return solution, routing, manager

# --- APP LOGIC ---
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    # Show Raw Data
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Order Data")
        st.dataframe(df.head())
        st.info(f"Total Orders: {len(df)}")
    
    # Initialize Map
    m = folium.Map(location=[df.iloc[0]['lat'], df.iloc[0]['lon']], zoom_start=11)
    
    # Plot Customer Locations (Before Opt)
    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5, color="blue", fill=True, fill_color="blue"
        ).add_to(m)
    
    # Plot Warehouse (First Row)
    folium.Marker(
        location=[df.iloc[0]['lat'], df.iloc[0]['lon']],
        icon=folium.Icon(color="red", icon="home"),
        tooltip="Warehouse"
    ).add_to(m)

    if run_btn:
        with st.spinner("AI is calculating optimal routes..."):
            data = create_data_model(df, num_vehicles, vehicle_capacity)
            solution, routing, manager = solve_vrp(data)
            
            if solution:
                st.success("Routes Optimized!")
                
                # Colors for different vehicles
                colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen']
                
                total_distance = 0
                
                # Draw Routes
                for vehicle_id in range(data['num_vehicles']):
                    index = routing.Start(vehicle_id)
                    route_coords = []
                    while not routing.IsEnd(index):
                        node_index = manager.IndexToNode(index)
                        route_coords.append([df.iloc[node_index]['lat'], df.iloc[node_index]['lon']])
                        index = solution.Value(routing.NextVar(index))
                    # Add end point
                    node_index = manager.IndexToNode(index)
                    route_coords.append([df.iloc[node_index]['lat'], df.iloc[node_index]['lon']])
                    
                    # Plot line
                    folium.PolyLine(route_coords, color=colors[vehicle_id % len(colors)], weight=4, opacity=0.8).add_to(m)
            else:
                st.error("No solution found. Try increasing vehicle capacity or number of vehicles.")

    with col2:
        st_folium(m, width=700, height=500)