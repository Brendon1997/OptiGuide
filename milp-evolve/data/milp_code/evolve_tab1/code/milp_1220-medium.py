import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class NetworkHandoffOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_instance(self):
        assert self.n_cell_towers > 0 and self.n_user_groups > 0
        assert self.min_cost_handoff >= 0 and self.max_cost_handoff >= self.min_cost_handoff
        assert self.min_cost_transmission >= 0 and self.max_cost_transmission >= self.min_cost_transmission
        assert self.min_capacity_tower > 0 and self.max_capacity_tower >= self.min_capacity_tower
        assert self.min_user_demand >= 0 and self.max_user_demand >= self.min_user_demand
        
        handoff_costs = np.random.randint(self.min_cost_handoff, self.max_cost_handoff + 1, self.n_cell_towers)
        transmission_costs = np.random.randint(self.min_cost_transmission, self.max_cost_transmission + 1, (self.n_cell_towers, self.n_user_groups))
        capacities = np.random.randint(self.min_capacity_tower, self.max_capacity_tower + 1, self.n_cell_towers)
        demands = np.random.randint(self.min_user_demand, self.max_user_demand + 1, (self.n_periods, self.n_user_groups))
        tower_penalty_costs = np.random.uniform(10, 50, (self.n_periods, self.n_user_groups)).tolist()
        interference_costs = np.random.randint(self.min_cost_interference, self.max_cost_interference + 1, (self.n_cell_towers, self.n_cell_towers))
        handoff_penalty_costs = np.random.uniform(1, 10, (self.n_cell_towers, self.n_user_groups)).tolist()
        handoff_delay_penalties = np.random.uniform(20, 60, (self.n_periods, self.n_user_groups)).tolist()

        signal_strengths = np.random.randint(1, 10, self.n_user_groups).tolist()
        user_movements = np.random.normal(1, 0.2, (self.n_periods, self.n_user_groups)).tolist()
        cell_utilization = np.random.uniform(0.5, 1, (self.n_periods, self.n_cell_towers)).tolist()
        network_interference_levels = np.random.uniform(0.1, 0.3, (self.n_cell_towers, self.n_user_groups)).tolist()
        signal_interference_factors = np.random.uniform(0.05, 0.1, (self.n_cell_towers, self.n_user_groups)).tolist()
        
        return {
            "handoff_costs": handoff_costs,
            "transmission_costs": transmission_costs,
            "capacities": capacities,
            "demands": demands,
            "tower_penalty_costs": tower_penalty_costs,
            "interference_costs": interference_costs,
            "handoff_penalty_costs": handoff_penalty_costs,
            "handoff_delay_penalties": handoff_delay_penalties,
            "signal_strengths": signal_strengths,
            "user_movements": user_movements,
            "cell_utilization": cell_utilization,
            "network_interference_levels": network_interference_levels,
            "signal_interference_factors": signal_interference_factors
        }

    def solve(self, instance):
        handoff_costs = instance['handoff_costs']
        transmission_costs = instance['transmission_costs']
        capacities = instance['capacities']
        demands = instance['demands']
        tower_penalty_costs = instance['tower_penalty_costs']
        interference_costs = instance['interference_costs']
        handoff_penalty_costs = instance['handoff_penalty_costs']
        handoff_delay_penalties = instance['handoff_delay_penalties']
        signal_strengths = instance['signal_strengths']
        user_movements = instance['user_movements']
        cell_utilization = instance['cell_utilization']
        network_interference_levels = instance['network_interference_levels']
        signal_interference_factors = instance['signal_interference_factors']

        model = Model("NetworkHandoffOptimization")
        n_cell_towers = len(handoff_costs)
        n_user_groups = len(transmission_costs[0])
        n_periods = len(demands)

        cell_vars = {(c, t): model.addVar(vtype="B", name=f"Cell_{c}_Period_{t}") for c in range(n_cell_towers) for t in range(n_periods)}
        transmission_vars = {(c, u, t): model.addVar(vtype="C", name=f"Transmission_{c}_User_{u}_Period_{t}") for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)}
        unmet_demand_vars = {(u, t): model.addVar(vtype="C", name=f"Unmet_Demand_{u}_Period_{t}") for u in range(n_user_groups) for t in range(n_periods)}
        delay_vars = {(u, t): model.addVar(vtype="C", name=f"Delay_User_{u}_Period_{t}") for u in range(n_user_groups) for t in range(n_periods)}
        usage_vars = {(c, t): model.addVar(vtype="C", name=f"Usage_{c}_Period_{t}") for c in range(n_cell_towers) for t in range(n_periods)}
        interference_vars = {(i, j, t): model.addVar(vtype="C", name=f"Interference_{i}_to_{j}_Period_{t}") for i in range(n_cell_towers) for j in range(n_cell_towers) if i != j for t in range(n_periods)}

        network_interference_vars = {(c, u, t): model.addVar(vtype="C", name=f"Network_Interference_{c}_User_{u}_Period_{t}") for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)}
        signal_interference_vars = {(c, u, t): model.addVar(vtype="C", name=f"Signal_Interference_{c}_User_{u}_Period_{t}") for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)}

        # Enhanced objective: Minimize total cost with additional unmet demand penalty
        model.setObjective(
            quicksum(handoff_costs[c] * cell_vars[c, t] for c in range(n_cell_towers) for t in range(n_periods)) +
            quicksum(transmission_costs[c][u] * transmission_vars[c, u, t] for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(tower_penalty_costs[t][u] * unmet_demand_vars[u, t] for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(handoff_penalty_costs[c][u] * usage_vars[c, t] for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(handoff_delay_penalties[t][u] * delay_vars[u, t] for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(interference_costs[i][j] * interference_vars[i, j, t] for i in range(n_cell_towers) for j in range(n_cell_towers) if i != j for t in range(n_periods)) +
            quicksum(network_interference_levels[c][u] * network_interference_vars[c, u, t] for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(signal_interference_factors[c][u] * signal_interference_vars[c, u, t] for c in range(n_cell_towers) for u in range(n_user_groups) for t in range(n_periods)) +
            quicksum(2 * unmet_demand_vars[u, t] for u in range(n_user_groups) for t in range(n_periods)),
            "minimize"
        )

        # Constraints for demand satisfaction per user group per period
        for u in range(n_user_groups):
            for t in range(n_periods):
                model.addCons(
                    quicksum(transmission_vars[c, u, t] for c in range(n_cell_towers)) + 
                    unmet_demand_vars[u, t] + delay_vars[u, t] == demands[t][u], 
                    f"Demand_Satisfaction_{u}_Period_{t}"
                )

        # Capacity constraints for each cell tower in each period
        for c in range(n_cell_towers):
            for t in range(n_periods):
                model.addCons(
                    quicksum(transmission_vars[c, u, t] for u in range(n_user_groups)) + 
                    quicksum(interference_vars[c, j, t] for j in range(n_cell_towers) if j != c) <= 
                    capacities[c] * cell_vars[c, t] * quicksum(cell_utilization[t][i] for i in range(n_user_groups)), 
                    f"Tower_Capacity_{c}_Period_{t}"
                )
        
        # Transmission constraints dependent on operational status, signal strength, and user movements
        for c in range(n_cell_towers):
            for u in range(n_user_groups):
                for t in range(n_periods):
                    model.addCons(
                        transmission_vars[c, u, t] <= demands[t][u] * cell_vars[c, t] * signal_strengths[u] * user_movements[t][u], 
                        f"Operational_Constraint_{c}_{u}_Period_{t}"
                    )

        # Disjunctive constraints: traffic could be rerouted via different links based on cell utilization and interference levels
        for c in range(n_cell_towers):
            for t in range(1, n_periods):
                model.addCons(
                    usage_vars[c, t] >= 
                    usage_vars[c, t-1] + 
                    quicksum(transmission_vars[c, u, t-1] for u in range(n_user_groups)) - 
                    quicksum(transmission_vars[c, u, t] for u in range(n_user_groups)) + 
                    quicksum(interference_vars[i, c, t-1] for i in range(n_cell_towers) if i != c) - 
                    quicksum(interference_vars[c, j, t] for j in range(n_cell_towers) if j != c), 
                    f"Disjunctive_Usage_1_{c}_Period_{t}"
                )

        # Initial usage constraints ensuring zero initial load
        for c in range(n_cell_towers):
            model.addCons(usage_vars[c, 0] == 0, f"Initial_Usage_{c}")
        
        # Delay and unmet demand relationship constraints
        for u in range(n_user_groups):
            for t in range(1, n_periods):
                model.addCons(
                    delay_vars[u, t] == 
                    unmet_demand_vars[u, t-1], 
                    f"Delay_Balance_{u}_Period_{t}"
                )
        
        # Symmetry breaking to handle equivalent configurations
        for c in range(n_cell_towers - 1):
            for t in range(n_periods):
                model.addCons(
                    quicksum(cell_vars[c, p] * (n_periods - p) for p in range(n_periods)) >= 
                    quicksum(cell_vars[c + 1, q] * (n_periods - q) for q in range(n_periods)),
                    f"Symmetry_Break_{c}_{c+1}_Period_{t}"
                )
        
        # Network interference constraint establishment
        for c in range(n_cell_towers):
            for u in range(n_user_groups):
                for t in range(n_periods):
                    model.addCons(
                        network_interference_vars[c, u, t] == network_interference_levels[c][u] * transmission_vars[c, u, t],
                        f"Network_Interference_{c}_{u}_Period_{t}"
                    )
                    model.addCons(
                        signal_interference_vars[c, u, t] == signal_interference_factors[c][u] * transmission_vars[c, u, t],
                        f"Signal_Interference_{c}_{u}_Period_{t}"
                    )

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_cell_towers': 7,
        'n_user_groups': 2,
        'n_periods': 66,
        'min_cost_handoff': 3000,
        'max_cost_handoff': 5000,
        'min_cost_transmission': 135,
        'max_cost_transmission': 306,
        'min_cost_interference': 94,
        'max_cost_interference': 1125,
        'min_capacity_tower': 656,
        'max_capacity_tower': 3000,
        'min_user_demand': 90,
        'max_user_demand': 800,
        'max_signal_strength': 1250,
        'min_network_interference': 0.1,
        'max_network_interference': 0.59,
        'min_signal_factor': 0.59,
        'max_signal_factor': 0.73,
    }

    network_optimizer = NetworkHandoffOptimization(parameters, seed=42)
    instance = network_optimizer.generate_instance()
    solve_status, solve_time, objective_value = network_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")