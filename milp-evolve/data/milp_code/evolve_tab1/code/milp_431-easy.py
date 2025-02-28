import random
import time
import scipy
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum

class AdvancedLogisticsOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_instance(self):
        nnzrs = int(self.n_rows * self.n_cols * self.density)

        # compute number of rows per column
        indices = np.random.choice(self.n_cols, size=nnzrs)  # random column indexes
        indices[:2 * self.n_cols] = np.repeat(np.arange(self.n_cols), 2)  # force at least 2 rows per col
        _, col_nrows = np.unique(indices, return_counts=True)

        # for each column, sample random rows
        indices[:self.n_rows] = np.random.permutation(self.n_rows) # force at least 1 column per row
        i = 0
        indptr = [0]
        for n in col_nrows:
            if i >= self.n_rows:
                indices[i:i + n] = np.random.choice(self.n_rows, size=n, replace=False)
            elif i + n > self.n_rows:
                remaining_rows = np.setdiff1d(np.arange(self.n_rows), indices[i:self.n_rows], assume_unique=True)
                indices[self.n_rows:i + n] = np.random.choice(remaining_rows, size=i + n - self.n_rows,
                                                              replace=False)
            i += n
            indptr.append(i)

        c = np.random.randint(self.max_coef, size=self.n_cols) + 1
        
        graph = nx.erdos_renyi_graph(self.n_cols, self.edge_prob, seed=self.seed)
        capacities = np.random.randint(1, self.max_capacity, size=len(graph.edges))
        flows = np.random.uniform(0, self.max_flow, size=len(graph.edges))
        
        source_node, sink_node = 0, self.n_cols - 1

        adj_list = {i: [] for i in range(self.n_cols)}
        for idx, (u, v) in enumerate(graph.edges):
            adj_list[u].append((v, flows[idx], capacities[idx]))
            adj_list[v].append((u, flows[idx], capacities[idx]))
        
        A = scipy.sparse.csc_matrix(
            (np.ones(len(indices), dtype=int), indices, indptr),
            shape=(self.n_rows, self.n_cols)).tocsr()
        indices_csr = A.indices
        indptr_csr = A.indptr

        res = {'c': c,
               'indptr_csr': indptr_csr,
               'indices_csr': indices_csr,
               'adj_list': adj_list,
               'source_node': source_node,
               'sink_node': sink_node}

        depot_capacity = np.random.randint(1, self.max_depot_capacity, size=self.n_depots)
        depot_zones = {i: np.random.choice(range(self.n_cols), size=self.n_depots_in_zone, replace=False) for i in
                         range(self.n_depots)}
        
        demand = np.random.uniform(1, self.max_demand, size=self.n_cols)
        emergency_routes = np.random.choice([True, False], size=self.n_cols)

        time_windows = {i: (np.random.randint(0, self.latest_delivery_time // 2), np.random.randint(self.latest_delivery_time // 2, self.latest_delivery_time)) for i in range(self.n_cols)}
        
        res.update({'depot_capacity': depot_capacity, 
                    'depot_zones': depot_zones,
                    'demand': demand,
                    'emergency_routes': emergency_routes,
                    'time_windows': time_windows})

        # Parameters for energy consumption and peak load management
        E = np.random.uniform(0.1, 10, size=(self.n_machines, self.n_tasks))  # Energy consumption matrix per machine-task pair
        P_max = self.max_energy_consumption  # Maximum energy consumption per period

        res.update({'E': E, 'P_max': P_max})

        # Carbon Emission Parameters
        carbon_emissions = np.random.uniform(0.1, 2, size=self.n_cols)
        toll_flags = np.random.randint(0, 2, size=(self.n_cols, self.n_cols))

        res.update({'carbon_emissions': carbon_emissions, 'toll_flags': toll_flags})

        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        c = instance['c']
        indptr_csr = instance['indptr_csr']
        indices_csr = instance['indices_csr']
        adj_list = instance['adj_list']
        source_node = instance['source_node']
        sink_node = instance['sink_node']
        depot_capacity = instance['depot_capacity']
        depot_zones = instance['depot_zones']
        demand = instance['demand']
        emergency_routes = instance['emergency_routes']
        time_windows = instance['time_windows']
        E = instance['E']
        P_max = instance['P_max']
        carbon_emissions = instance['carbon_emissions']
        toll_flags = instance['toll_flags']

        model = Model("AdvancedLogisticsOptimization")
        var_names = {}

        for j in range(self.n_cols):
            var_names[j] = model.addVar(vtype="B", name=f"x_{j}", obj=c[j])
          
        flow_vars = {}
        route_vars = {}
        for u in adj_list:
            for v, _, capacity in adj_list[u]:
                flow_vars[(u, v)] = model.addVar(vtype='C', lb=0, ub=capacity, name=f"f_{u}_{v}")
                route_vars[(u, v)] = model.addVar(vtype='B', name=f"r_{u}_{v}")

        for row in range(self.n_rows):
            cols = indices_csr[indptr_csr[row]:indptr_csr[row + 1]]
            model.addCons(quicksum(var_names[j] for j in cols) >= 1, f"c_{row}")

        for node in adj_list:
            inflow = quicksum(flow_vars[(u, node)] for u, _, _ in adj_list[node] if (u, node) in flow_vars)
            outflow = quicksum(flow_vars[(node, v)] for v, _, _ in adj_list[node] if (node, v) in flow_vars)
            model.addCons(inflow - outflow == 0, f"flow_balance_{node}")

        depot_vars = {}
        for zone, cols in depot_zones.items():
            for col in cols:
                depot_vars[col] = model.addVar(vtype="B", name=f"d_{col}")
                model.addCons(var_names[col] <= depot_vars[col], f"allocate_{col}")

            model.addCons(quicksum(depot_vars[col] for col in cols) <= depot_capacity[zone], f"depot_limit_{zone}")

        vehicle_vars = {}
        for u in depot_zones:
            for col in depot_zones[u]:
                vehicle_vars[(u, col)] = model.addVar(vtype="B", name=f"v_{u}_{col}")

        time_vars = {}
        early_penalty_vars = {}
        late_penalty_vars = {}
        for j in range(self.n_cols):
            time_vars[j] = model.addVar(vtype='C', name=f"t_{j}")
            early_penalty_vars[j] = model.addVar(vtype='C', name=f"e_{j}")
            late_penalty_vars[j] = model.addVar(vtype='C', name=f"l_{j}")
            
            start_window, end_window = time_windows[j]
            model.addCons(time_vars[j] >= start_window, f"time_window_start_{j}")
            model.addCons(time_vars[j] <= end_window, f"time_window_end_{j}")
            
            model.addCons(early_penalty_vars[j] >= start_window - time_vars[j], f"early_penalty_{j}")
            model.addCons(late_penalty_vars[j] >= time_vars[j] - end_window, f"late_penalty_{j}")

        # Energy and Load management constraints
        P_vars = {}
        for t in range(self.n_periods):
            P_vars[t] = model.addVar(vtype='C', name=f"P_{t}")

        y_vars = {}
        for i in range(self.n_machines):
            for j in range(self.n_tasks):
                y_vars[(i, j)] = model.addVar(vtype='B', name=f"y_{i}_{j}")

        for t in range(self.n_periods):
            model.addCons(quicksum(E[i,j] * y_vars[(i,j)] for i in range(self.n_machines) for j in range(self.n_tasks)) <= P_max, name=f"energy_limit_{t}")

        eta = model.addVar(vtype='C', name="eta")
        model.addCons(eta >= quicksum(P_vars[t] for t in range(self.n_periods)), name="energy_efficiency")

        # Carbon Emission and Toll Road Constraints
        carbon_emission_vars = {}
        for j in range(self.n_cols):
            carbon_emission_vars[j] = model.addVar(vtype='C', name=f"emission_{j}")
            model.addCons(carbon_emission_vars[j] == var_names[j] * carbon_emissions[j], name=f"emission_calc_{j}")

        toll_usage_vars = {}
        for u in adj_list:
            for v, _, _ in adj_list[u]:
                toll_usage_vars[(u, v)] = model.addVar(vtype='B', name=f"toll_{u}_{v}")
                model.addCons(toll_usage_vars[(u, v)] >= route_vars[(u, v)] * toll_flags[u, v], name=f"toll_usage_{u}_{v}")

        total_toll_time = quicksum(route_vars[(u, v)] * toll_flags[u, v] for u in adj_list for v, _, _ in adj_list[u])
        model.addCons(total_toll_time <= 0.25 * quicksum(route_vars[(u, v)] for u in adj_list for v, _, _ in adj_list[u]), name="total_toll_limit")

        consecutive_toll_usage = {}
        for j in range(self.n_cols):
            consecutive_toll_usage[j] = quicksum(route_vars[(j, v)] * toll_flags[j, v] for v, _, _ in adj_list[j])
            model.addCons(consecutive_toll_usage[j] <= 3, name=f"toll_limit_{j}")

        cost_term = quicksum(var_names[j] * c[j] for j in range(self.n_cols))
        flow_term = quicksum(flow_vars[(u, v)] for u, v in flow_vars)
        depot_penalty_term = quicksum(depot_vars[col] for col in depot_vars)
        time_penalty_term = quicksum(early_penalty_vars[j] + late_penalty_vars[j] for j in range(self.n_cols))
        route_penalty_term = quicksum(route_vars[(u, v)] for u, v in route_vars)
        energy_term = quicksum(P_vars[t] for t in range(self.n_periods))
        efficiency_term = eta
        carbon_emission_term = quicksum(carbon_emission_vars[j] for j in range(self.n_cols))
        toll_usage_term = quicksum(toll_usage_vars[(u, v)] for u in adj_list for v, _, _ in adj_list[u])

        alpha = 0.5  # Weight for energy costs
        beta = 1.0  # Weight for energy efficiency penalty
        gamma = 0.2  # Weight for carbon emissions
        delta = 0.1  # Weight for toll usage
        objective_expr = cost_term - self.flow_weight * flow_term + self.depot_penalty_weight * depot_penalty_term + self.time_penalty_weight * time_penalty_term + self.route_penalty_weight * route_penalty_term + alpha * energy_term + beta * efficiency_term + gamma * carbon_emission_term + delta * toll_usage_term

        model.setObjective(objective_expr, "minimize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_rows': 3000,
        'n_cols': 157,
        'density': 0.31,
        'max_coef': 1124,
        'edge_prob': 0.38,
        'max_capacity': 2400,
        'max_flow': 350,
        'flow_weight': 0.38,
        'n_depots': 20,
        'n_depots_in_zone': 60,
        'max_depot_capacity': 1350,
        'depot_penalty_weight': 0.38,
        'max_demand': 2250,
        'route_penalty_weight': 0.24,
        'latest_delivery_time': 480,
        'time_penalty_weight': 0.17,
        'n_machines': 50,
        'n_tasks': 200,
        'n_periods': 120,
        'max_energy_consumption': 600,
        'emission_factor': 0.31,
    }

    advanced_logistics_optimization = AdvancedLogisticsOptimization(parameters, seed=seed)
    instance = advanced_logistics_optimization.generate_instance()
    solve_status, solve_time = advanced_logistics_optimization.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")