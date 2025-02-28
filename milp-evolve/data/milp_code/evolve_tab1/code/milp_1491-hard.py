import random
import time
import numpy as np
import networkx as nx
import scipy.spatial as spatial
from pyscipopt import Model, quicksum

class FCMCNF:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_erdos_graph(self):
        G = nx.erdos_renyi_graph(n=self.n_nodes, p=self.er_prob, seed=self.seed, directed=True)
        adj_mat = np.zeros((self.n_nodes, self.n_nodes), dtype=object)
        edge_list = []
        incommings = {j: [] for j in range(self.n_nodes)}
        outcommings = {i: [] for i in range(self.n_nodes)}

        for i, j in G.edges:
            c_ij = np.random.uniform(*self.c_range)
            f_ij = np.random.uniform(self.c_range[0] * self.ratio, self.c_range[1] * self.ratio)
            u_ij = np.random.uniform(1, self.k_max + 1) * np.random.uniform(*self.d_range)
            adj_mat[i, j] = (c_ij, f_ij, u_ij)
            edge_list.append((i, j))
            outcommings[i].append(j)
            incommings[j].append(i)

        return G, adj_mat, edge_list, incommings, outcommings

    def generate_commodities(self, G):
        commodities = []
        for k in range(self.n_commodities):
            while True:
                o_k = np.random.randint(0, self.n_nodes)
                d_k = np.random.randint(0, self.n_nodes)
                if nx.has_path(G, o_k, d_k) and o_k != d_k:
                    break
            # integer demands
            demand_k = int(np.random.uniform(*self.d_range))
            commodities.append((o_k, d_k, demand_k))
        return commodities
    
    def generate_hospital_data(self):
        hospital_coordinates = np.random.rand(self.n_hospitals, 2) * 100
        disaster_point = np.array([np.random.uniform(0, 100), np.random.uniform(0, 100)])
        distances = spatial.distance.cdist(hospital_coordinates, [disaster_point]).flatten()

        min_supply_limits = np.random.randint(1, self.max_supply_limit + 1, size=self.n_hospitals)
        
        res = {
            'hospital_coordinates': hospital_coordinates.tolist(),
            'disaster_point': disaster_point.tolist(),
            'distances': distances.tolist(),
            'min_supply_limits': min_supply_limits.tolist(),
        }

        return res

    def generate_instance(self):
        self.n_nodes = np.random.randint(self.min_n_nodes, self.max_n_nodes + 1)
        self.n_commodities = np.random.randint(self.min_n_commodities, self.max_n_commodities + 1)
        G, adj_mat, edge_list, incommings, outcommings = self.generate_erdos_graph()
        commodities = self.generate_commodities(G)
        hospital_data = self.generate_hospital_data()

        # Additional data generation for new constraints
        remote_prob = 0.3
        remote_conditions = {}
        for u, v in edge_list:
            remote_conditions[(u, v)] = {
                'is_remote': np.random.choice([0, 1], p=[1 - remote_prob, remote_prob]),
                'fuel_consumption': np.random.uniform(10, 50),
                'load': np.random.uniform(1, 10),
                'driving_hours': np.random.uniform(5, 20)
            }

        res = {
            'commodities': commodities, 
            'adj_mat': adj_mat, 
            'edge_list': edge_list, 
            'incommings': incommings, 
            'outcommings': outcommings,
            'hospital_data': hospital_data,
            'remote_conditions': remote_conditions
        }

        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        commodities = instance['commodities']
        adj_mat = instance['adj_mat']
        edge_list = instance['edge_list']
        incommings = instance['incommings']
        outcommings = instance['outcommings']
        hospital_data = instance['hospital_data']
        remote_conditions = instance['remote_conditions']

        model = Model("FCMCNF")
        x_vars = {f"x_{i+1}_{j+1}_{k+1}": model.addVar(vtype="C", name=f"x_{i+1}_{j+1}_{k+1}") for (i, j) in edge_list for k in range(self.n_commodities)}
        y_vars = {f"y_{i+1}_{j+1}": model.addVar(vtype="B", name=f"y_{i+1}_{j+1}") for (i, j) in edge_list}
        hospital_supply_vars = {f"h_{h+1}": model.addVar(vtype="B", name=f"h_{h+1}") for h in range(self.n_hospitals)}
        is_remote_vars = {f"is_remote_{i+1}_{j+1}": model.addVar(vtype="B", name=f"is_remote_{i+1}_{j+1}") for (i, j) in edge_list}
        z_vars = {f"z_{i+1}_{j+1}": model.addVar(vtype="B", name=f"z_{i+1}_{j+1}") for (i, j) in edge_list}

        # Objective function
        objective_expr = quicksum(
            commodities[k][2] * adj_mat[i, j][0] * x_vars[f"x_{i+1}_{j+1}_{k+1}"]
            for (i, j) in edge_list for k in range(self.n_commodities)
        )
        objective_expr += quicksum(
            adj_mat[i, j][1] * y_vars[f"y_{i+1}_{j+1}"]
            for (i, j) in edge_list
        )
        objective_expr += quicksum(
            hospital_data['distances'][h] * hospital_supply_vars[f"h_{h+1}"]
            for h in range(self.n_hospitals)
        )

        # Flow conservation constraints
        for i in range(self.n_nodes):
            for k in range(self.n_commodities):
                delta_i = 1 if commodities[k][0] == i else -1 if commodities[k][1] == i else 0
                flow_expr = quicksum(x_vars[f"x_{i+1}_{j+1}_{k+1}"] for j in outcommings[i]) - quicksum(x_vars[f"x_{j+1}_{i+1}_{k+1}"] for j in incommings[i])
                model.addCons(flow_expr == delta_i, f"flow_{i+1}_{k+1}")

        # Arc capacity constraints
        for (i, j) in edge_list:
            arc_expr = quicksum(commodities[k][2] * x_vars[f"x_{i+1}_{j+1}_{k+1}"] for k in range(self.n_commodities))
            model.addCons(arc_expr <= adj_mat[i, j][2] * y_vars[f"y_{i+1}_{j+1}"], f"arc_{i+1}_{j+1}")

        # Hospital supply constraints
        for h in range(self.n_hospitals):
            model.addCons(
                hospital_supply_vars[f"h_{h+1}"] * quicksum(
                    x_vars[f"x_{i+1}_{j+1}_{k+1}"] for k in range(self.n_commodities) for (i, j) in edge_list
                ) >= hospital_data['min_supply_limits'][h], f"hospital_min_supply_{h+1}"
            )

        # Minimum number of hospitals to supply
        model.addCons(
            quicksum(hospital_supply_vars[f"h_{h+1}"] for h in range(self.n_hospitals)) >= self.min_hospitals_to_supply,
            "min_hospitals_to_supply"
        )

        # New constraints for remote locations, fuel consumption, load capacity, and driving hours
        model.addCons(
            quicksum(is_remote_vars[f"is_remote_{i+1}_{j+1}"] for (i, j) in edge_list) >= 0.4 * quicksum(y_vars[f"y_{i+1}_{j+1}"] for (i, j) in edge_list),
            "RemoteRoute_Minimum_40%"
        )

        total_fuel_budget = quicksum(remote_conditions[(i, j)]['fuel_consumption'] * y_vars[f"y_{i+1}_{j+1}"] for (i, j) in edge_list)
        remote_fuel_budget = quicksum(remote_conditions[(i, j)]['fuel_consumption'] * is_remote_vars[f"is_remote_{i+1}_{j+1}"] for (i, j) in edge_list)
        model.addCons(
            remote_fuel_budget <= 0.25 * total_fuel_budget,
            "RemoteFuel_Budget_25%"
        )

        for (i, j) in edge_list:
            model.addCons(
                remote_conditions[(i, j)]['load'] * y_vars[f"y_{i+1}_{j+1}"] <= self.vehicle_capacity,
                f"Vehicle_Load_Capacity_{i+1}_{j+1}"
            )
            model.addCons(
                remote_conditions[(i, j)]['driving_hours'] * y_vars[f"y_{i+1}_{j+1}"] <= 0.2 * self.regular_working_hours,
                f"Driving_Hours_{i+1}_{j+1}"
            )

        # Additional Big M constraints
        M = 1e6
        
        for (i, j) in edge_list:
            # Big M constraint for flow related to z_vars
            model.addCons(
                quicksum(x_vars[f"x_{i+1}_{j+1}_{k+1}"] for k in range(self.n_commodities)) <= M * z_vars[f"z_{i+1}_{j+1}"],
                f"BigM_Flow_{i+1}_{j+1}"
            )
            model.addCons(
                quicksum(x_vars[f"x_{i+1}_{j+1}_{k+1}"] for k in range(self.n_commodities)) >= -M * z_vars[f"z_{i+1}_{j+1}"],
                f"BigM_Flow_neg_{i+1}_{j+1}"
            )

            # Big M constraint to ensure logical routing involving remote locations
            model.addCons(
                is_remote_vars[f"is_remote_{i+1}_{j+1}"] <= y_vars[f"y_{i+1}_{j+1}"] + M * z_vars[f"z_{i+1}_{j+1}"],
                f"BigM_Routing_{i+1}_{j+1}"
            )

        model.setObjective(objective_expr, "minimize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time
    

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_n_nodes': 20,
        'max_n_nodes': 30,
        'min_n_commodities': 30,
        'max_n_commodities': 45, 
        'c_range': (11, 50),
        'd_range': (10, 100),
        'ratio': 100,
        'k_max': 10,
        'er_prob': 0.3,
        'n_hospitals': 10,
        'max_supply_limit': 150,
        'min_hospitals_to_supply': 5,
        'vehicle_capacity': 50,
        'regular_working_hours': 240,
        'big_m_value': 1e6
    }

    fcmcnf = FCMCNF(parameters, seed=seed)
    instance = fcmcnf.generate_instance()
    solve_status, solve_time = fcmcnf.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")