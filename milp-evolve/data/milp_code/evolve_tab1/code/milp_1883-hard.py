import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class Graph:
    """Helper function: Container for a graph."""
    def __init__(self, number_of_nodes, edges):
        self.number_of_nodes = number_of_nodes
        self.nodes = np.arange(number_of_nodes)
        self.edges = edges

    @staticmethod
    def erdos_renyi(number_of_nodes, edge_probability):
        """Generate an Erdös-Rényi random graph with a given edge probability."""
        G = nx.erdos_renyi_graph(number_of_nodes, edge_probability)
        edges = set(G.edges)
        return Graph(number_of_nodes, edges)

class LogisticsNetworkOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_graph(self):
        if self.graph_type == 'erdos_renyi':
            return Graph.erdos_renyi(self.n_locations, self.edge_probability)
        else:
            raise ValueError("Unsupported graph type.")

    def generate_instance(self):
        graph = self.generate_graph()
        delivery_demands = np.random.randint(100, 1000, size=self.n_locations)
        supply_populations = np.random.randint(500, 5000, size=self.n_locations)
        supply_vehicles = np.random.choice([1, 2, 3], size=self.n_locations, p=[0.5, 0.3, 0.2])
        distances = np.random.randint(1, 200, size=(self.n_locations, self.n_locations))

        # Vehicle allocation and logistics parameters
        operation_costs = np.random.randint(100, 500, size=self.n_locations)
        fuel_costs = np.random.randint(50, 100, size=(self.n_locations, self.n_locations))
        maintenance_costs = np.random.randint(50, 200, size=self.n_locations)
        max_budget = np.random.randint(10000, 20000)
        max_vehicle_capacity = np.random.randint(100, 500, size=self.n_locations)
        min_route_vehicles = 5
        max_route_vehicles = 15

        # Hub parameters
        n_hubs = np.random.randint(3, 7)
        hub_capacity = np.random.randint(200, 1000, size=n_hubs).tolist()
        hub_graph = nx.erdos_renyi_graph(n_hubs, 0.4)
        graph_edges = list(hub_graph.edges)

        # Logical dependencies for hubs (simplified)
        route_dependencies = [(random.randint(0, n_hubs - 1), random.randint(0, n_hubs - 1)) for _ in range(3)]

        # Additional Warehouse Data
        facility_costs = np.random.randint(self.min_facility_cost, self.max_facility_cost + 1, self.n_facilities)
        transport_costs = np.random.randint(self.min_transport_cost, self.max_transport_cost + 1, (self.n_facilities, self.n_units))
        spaces = np.random.randint(self.min_facility_space, self.max_facility_space + 1, self.n_facilities)
        demands = np.random.randint(1, 10, self.n_units)
        opening_times = np.random.randint(self.min_opening_time, self.max_opening_time + 1, self.n_facilities)
        maintenance_periods = np.random.randint(self.min_maintenance_period, self.max_maintenance_period + 1, self.n_facilities)

        res = {
            'graph': graph,
            'delivery_demands': delivery_demands,
            'supply_populations': supply_populations,
            'supply_vehicles': supply_vehicles,
            'distances': distances,
            'operation_costs': operation_costs,
            'fuel_costs': fuel_costs,
            'maintenance_costs': maintenance_costs,
            'max_budget': max_budget,
            'max_vehicle_capacity': max_vehicle_capacity,
            'min_route_vehicles': min_route_vehicles,
            'max_route_vehicles': max_route_vehicles,
            'n_hubs': n_hubs,
            'hub_capacity': hub_capacity,
            'graph_edges': graph_edges,
            'route_dependencies': route_dependencies,
            'facility_costs': facility_costs,
            'transport_costs': transport_costs,
            'spaces': spaces,
            'demands': demands,
            'opening_times': opening_times,
            'maintenance_periods': maintenance_periods
        }
        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        graph = instance['graph']
        delivery_demands = instance['delivery_demands']
        supply_populations = instance['supply_populations']
        supply_vehicles = instance['supply_vehicles']
        distances = instance['distances']
        operation_costs = instance['operation_costs']
        fuel_costs = instance['fuel_costs']
        maintenance_costs = instance['maintenance_costs']
        max_budget = instance['max_budget']
        max_vehicle_capacity = instance['max_vehicle_capacity']
        min_route_vehicles = instance['min_route_vehicles']
        max_route_vehicles = instance['max_route_vehicles']
        n_hubs = instance['n_hubs']
        hub_capacity = instance['hub_capacity']
        graph_edges = instance['graph_edges']
        route_dependencies = instance['route_dependencies']
        facility_costs = instance['facility_costs']
        transport_costs = instance['transport_costs']
        spaces = instance['spaces']
        demands = instance['demands']
        opening_times = instance['opening_times']
        maintenance_periods = instance['maintenance_periods']

        model = Model("LogisticsNetworkOptimization")

        # Variables
        route_vars = {node: model.addVar(vtype="B", name=f"Route_{node}") for node in graph.nodes}
        vehicle_vars = {(i, j): model.addVar(vtype="B", name=f"VehicleAllocation_{i}_{j}") for i in graph.nodes for j in graph.nodes}
        supply_vars = {node: model.addVar(vtype="C", name=f"Supply_{node}") for node in graph.nodes}
        hub_vars = {j: model.addVar(vtype="B", name=f"Hub_{j}") for j in range(n_hubs)}
        hub_allocation_vars = {(i, j): model.addVar(vtype="C", name=f"HubAllocation_{i}_{j}") for i in graph.nodes for j in range(n_hubs)}

        facility_vars = {f: model.addVar(vtype="B", name=f"Facility_{f}") for f in range(self.n_facilities)}
        transport_vars = {(f, u): model.addVar(vtype="B", name=f"Facility_{f}_Unit_{u}") for f in range(self.n_facilities) for u in range(self.n_units)}
        opening_time_vars = {f: model.addVar(vtype="I", lb=0, name=f"OpeningTime_{f}") for f in range(self.n_facilities)}
        maintenance_period_vars = {f: model.addVar(vtype="I", lb=0, name=f"MaintenancePeriod_{f}") for f in range(self.n_facilities)}

        # Constraints
        model.addCons(quicksum(route_vars[node] for node in graph.nodes) >= min_route_vehicles, name="MinRouteVehicles")
        model.addCons(quicksum(route_vars[node] for node in graph.nodes) <= max_route_vehicles, name="MaxRouteVehicles")

        for demand in graph.nodes:
            model.addCons(quicksum(vehicle_vars[demand, supply] for supply in graph.nodes) == 1, name=f"DeliveryDemand_{demand}")
        
        for i in graph.nodes:
            for j in graph.nodes:
                model.addCons(vehicle_vars[i, j] <= route_vars[j], name=f"VehicleAllocation_{i}_{j}")

        total_cost = quicksum(route_vars[node] * operation_costs[node] for node in graph.nodes) + \
                     quicksum(vehicle_vars[i, j] * fuel_costs[i, j] for i in graph.nodes for j in graph.nodes) + \
                     quicksum(supply_vars[node] * maintenance_costs[node] for node in graph.nodes)

        model.addCons(total_cost <= max_budget, name="Budget")

        for node in graph.nodes:
            model.addCons(supply_vars[node] <= max_vehicle_capacity[node], name=f"VehicleCapacity_{node}")
            model.addCons(supply_vars[node] <= route_vars[node] * max_vehicle_capacity[node], name=f"SupplyOpenRoute_{node}")

        for j in range(n_hubs):
            model.addCons(quicksum(hub_allocation_vars[i, j] for i in graph.nodes) <= hub_capacity[j], name=f"HubCapacity_{j}")

        for i in graph.nodes:
            model.addCons(quicksum(hub_allocation_vars[i, j] for j in range(n_hubs)) == route_vars[i], name=f"RouteHub_{i}")

        for dependency in route_dependencies:
            i, j = dependency
            model.addCons(hub_vars[i] >= hub_vars[j], name=f"HubDependency_{i}_{j}")

        # Each unit demand is met by exactly one facility
        for u in demands:
            model.addCons(quicksum(transport_vars[f, u] for f in range(self.n_facilities)) == 1, f"Unit_{u}_Demand")

        # Only open facilities can serve units
        for f in range(self.n_facilities):
            for u in demands:
                model.addCons(transport_vars[f, u] <= facility_vars[f], f"Facility_{f}_Serve_{u}")

        # Facilities cannot exceed their space
        for f in range(self.n_facilities):
            model.addCons(quicksum(demands[u] * transport_vars[f, u] for u in range(self.n_units)) <= spaces[f], f"Facility_{f}_Space")

        # Facilities must respect their opening and maintenance schedules
        for f in range(self.n_facilities):
            model.addCons(opening_time_vars[f] == opening_times[f], f"Facility_{f}_OpeningTime")
            model.addCons(maintenance_period_vars[f] == maintenance_periods[f], f"Facility_{f}_MaintenancePeriod")

        model.setObjective(total_cost + 
                           quicksum(facility_costs[f] * facility_vars[f] for f in range(self.n_facilities)) + 
                           quicksum(transport_costs[f, u] * transport_vars[f, u] for f in range(self.n_facilities) for u in range(self.n_units)) +
                           quicksum(opening_times[f] * opening_time_vars[f] for f in range(self.n_facilities)) + 
                           quicksum(maintenance_periods[f] * maintenance_period_vars[f] for f in range(self.n_facilities)) - 
                           50 * quicksum(transport_vars[f, u] for f in range(self.n_facilities) for u in range(self.n_units)),
                           "minimize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_locations': 100,
        'edge_probability': 0.45,
        'graph_type': 'erdos_renyi',
        'max_time_periods': 1400,
        'min_hubs': 450,
        'max_hubs': 2160,
        'max_vehicle_capacity': 1575,
        'n_facilities': 200,
        'n_units': 560,
        'min_transport_cost': 10,
        'max_transport_cost': 700,
        'min_facility_cost': 3000,
        'max_facility_cost': 5000,
        'min_facility_space': 1125,
        'max_facility_space': 1200,
        'min_opening_time': 0,
        'max_opening_time': 4,
        'min_maintenance_period': 67,
        'max_maintenance_period': 135,
    }

    logistics_network_optimization = LogisticsNetworkOptimization(parameters, seed=seed)
    instance = logistics_network_optimization.generate_instance()
    solve_status, solve_time = logistics_network_optimization.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")