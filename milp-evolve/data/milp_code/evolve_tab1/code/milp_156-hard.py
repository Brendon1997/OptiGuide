import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class GISP:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_random_graph(self):
        n_nodes = np.random.randint(self.min_n, self.max_n)
        G = nx.erdos_renyi_graph(n=n_nodes, p=self.er_prob, seed=self.seed)
        return G

    def generate_revenues_costs(self, G):
        if self.set_type == 'SET1':
            for node in G.nodes:
                G.nodes[node]['revenue'] = np.random.randint(1, 100)
            for u, v in G.edges:
                G[u][v]['cost'] = (G.nodes[u]['revenue'] + G.nodes[v]['revenue']) / float(self.set_param)
        elif self.set_type == 'SET2':
            for node in G.nodes:
                G.nodes[node]['revenue'] = float(self.set_param)
            for u, v in G.edges:
                G[u][v]['cost'] = 1.0

    def generate_removable_edges(self, G):
        E2 = set()
        for edge in G.edges:
            if np.random.random() <= self.alpha:
                E2.add(edge)
        return E2

    def generate_instance(self):
        G = self.generate_random_graph()
        self.generate_revenues_costs(G)
        E2 = self.generate_removable_edges(G)
        cliques = list(nx.find_cliques(G))
        
        inventory_holding_costs = {node: np.random.randint(1, 10) for node in G.nodes}
        renewable_energy_costs = {(u, v): np.random.randint(1, 10) for u, v in G.edges}
        carbon_emissions = {(u, v): np.random.randint(1, 10) for u, v in G.edges}
        weather_conditions = {(u, v): np.random.uniform(0.5, 1.5) for u, v in G.edges}
        terrain_difficulty = {(u, v): np.random.uniform(1, 3) for u, v in G.edges}

        # New parameters
        traffic_conditions = {edge: np.random.uniform(1.0, 3.0) for edge in G.edges}
        disaster_severity = {node: np.random.uniform(0.5, 2.0) for node in G.nodes}
        emergency_facility_capacities = {node: np.random.randint(1, 5) for node in G.nodes}
        emergency_facility_availability = {node: np.random.choice([0, 1], p=[0.2, 0.8]) for node in G.nodes}
        
        return {
            'G': G,
            'E2': E2,
            'cliques': cliques, 
            'inventory_holding_costs': inventory_holding_costs, 
            'renewable_energy_costs': renewable_energy_costs,
            'carbon_emissions': carbon_emissions,
            'weather_conditions': weather_conditions,
            'terrain_difficulty': terrain_difficulty,
            'traffic_conditions': traffic_conditions,
            'disaster_severity': disaster_severity,
            'emergency_facility_capacities': emergency_facility_capacities,
            'emergency_facility_availability': emergency_facility_availability
        }

    def solve(self, instance):
        G = instance['G']
        E2 = instance['E2']
        cliques = instance['cliques']
        inventory_holding_costs = instance['inventory_holding_costs']
        renewable_energy_costs = instance['renewable_energy_costs']
        carbon_emissions = instance['carbon_emissions']
        weather_conditions = instance['weather_conditions']
        terrain_difficulty = instance['terrain_difficulty']
        
        traffic_conditions = instance['traffic_conditions']
        disaster_severity = instance['disaster_severity']
        emergency_facility_capacities = instance['emergency_facility_capacities']
        emergency_facility_availability = instance['emergency_facility_availability']
        
        model = Model("GISP")
        node_vars = {f"x{node}": model.addVar(vtype="B", name=f"x{node}") for node in G.nodes}
        edge_vars = {f"y{u}_{v}": model.addVar(vtype="B", name=f"y{u}_{v}") for u, v in G.edges}
        piecewise_vars = {f"z{u}_{v}": model.addVar(vtype="B", name=f"z{u}_{v}") for u, v in G.edges}
        
        # New variables for different vehicle types
        ambulance_vars = {f"a{node}": model.addVar(vtype="B", name=f"a{node}") for node in G.nodes}
        fire_truck_vars = {f"f{node}": model.addVar(vtype="B", name=f"f{node}") for node in G.nodes}
        rescue_vehicle_vars = {f"r{node}": model.addVar(vtype="B", name=f"r{node}") for node in G.nodes}
        
        energy_vars = {f"e{node}": model.addVar(vtype="C", name=f"e{node}") for node in G.nodes}
        yearly_budget = model.addVar(vtype="C", name="yearly_budget")

        demand_level = {f"dem_{node}": model.addVar(vtype="C", name=f"dem_{node}") for node in G.nodes}
        renewable_energy_vars = {f"re_{u}_{v}": model.addVar(vtype="B", name=f"re_{u}_{v}") for u, v in G.edges}

        objective_expr = quicksum(
            G.nodes[node]['revenue'] * node_vars[f"x{node}"]
            for node in G.nodes
        )

        objective_expr -= quicksum(
            G[u][v]['cost'] * edge_vars[f"y{u}_{v}"]
            for u, v in E2
        )

        objective_expr -= quicksum(
            inventory_holding_costs[node] * energy_vars[f"e{node}"]
            for node in G.nodes
        )

        objective_expr -= quicksum(
            renewable_energy_costs[(u, v)] * renewable_energy_vars[f"re_{u}_{v}"]
            for u, v in G.edges
        )

        objective_expr -= quicksum(
            carbon_emissions[(u, v)] * edge_vars[f"y{u}_{v}"]
            for u, v in G.edges
        )

        # New objective terms for real-time data
        objective_expr -= quicksum(
            traffic_conditions[edge] * edge_vars[f"y{edge[0]}_{edge[1]}"]
            for edge in G.edges
        )

        objective_expr += quicksum(
            disaster_severity[node] * node_vars[f"x{node}"]
            for node in G.nodes
        )

        # Constraints
        
        for u, v in G.edges:
            if (u, v) in E2:
                model.addCons(
                    node_vars[f"x{u}"] + node_vars[f"x{v}"] - edge_vars[f"y{u}_{v}"] <= 1,
                    name=f"C_{u}_{v}"
                )
            else:
                model.addCons(
                    node_vars[f"x{u}"] + node_vars[f"x{v}"] <= 1,
                    name=f"C_{u}_{v}"
                )

        for i, clique in enumerate(cliques):
            model.addCons(
                quicksum(node_vars[f"x{node}"] for node in clique) <= 1,
                name=f"Clique_{i}"
            )

        for u, v in G.edges:
            model.addCons(
                node_vars[f"x{u}"] + node_vars[f"x{v}"] <= 1 + piecewise_vars[f"z{u}_{v}"],
                name=f"PL1_{u}_{v}"
            )
            model.addCons(
                node_vars[f"x{u}"] + node_vars[f"x{v}"] >= 2 * piecewise_vars[f"z{u}_{v}"],
                name=f"PL2_{u}_{v}"
            )

        for u, v in G.edges:
            model.addCons(
                edge_vars[f"y{u}_{v}"] >= renewable_energy_vars[f"re_{u}_{v}"],
                name=f"RE_{u}_{v}"
            )

        for node in G.nodes:
            model.addCons(
                energy_vars[f"e{node}"] + demand_level[f"dem_{node}"] == 0,
                name=f"Node_{node}_energy"
            )

        for u, v in G.edges:
            model.addCons(
                G[u][v]['cost'] * terrain_difficulty[(u, v)] * weather_conditions[(u, v)] * edge_vars[f"y{u}_{v}"] <= yearly_budget,
                name=f"Budget_{u}_{v}"
            )

        model.addCons(
            yearly_budget <= self.yearly_budget_limit,
            name="Yearly_budget_limit"
        )

        # New constraints for vehicle capacities and scheduling
        for node in G.nodes:
            model.addCons(
                quicksum([ambulance_vars[f"a{node}"], fire_truck_vars[f"f{node}"], rescue_vehicle_vars[f"r{node}"]]) <= emergency_facility_capacities[node],
                name=f"Capacity_{node}"
            )

            model.addCons(
                quicksum([ambulance_vars[f"a{node}"], fire_truck_vars[f"f{node}"], rescue_vehicle_vars[f"r{node}"]]) <= emergency_facility_availability[node],
                name=f"Availability_{node}"
            )
        
        model.setObjective(objective_expr, "maximize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_n': 37,
        'max_n': 365,
        'er_prob': 0.38,
        'set_type': 'SET1',
        'set_param': 112.5,
        'alpha': 0.38,
        'renewable_percentage': 0.31,
        'carbon_limit': 843,
        'yearly_budget_limit': 5000,
        'ambulance_capacity': 150,
        'fire_truck_capacity': 270,
        'rescue_vehicle_capacity': 8,
    }
    
    gisp = GISP(parameters, seed=seed)
    instance = gisp.generate_instance()
    solve_status, solve_time = gisp.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")