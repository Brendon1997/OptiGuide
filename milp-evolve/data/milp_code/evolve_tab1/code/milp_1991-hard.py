import random
import time
import numpy as np
import networkx as nx
from pyscipopt import Model, quicksum
from networkx.algorithms import bipartite

class MaxSatisfiability:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# Data Generation #################
    def generate_bipartite_graph(self, n1, n2, p):
        return bipartite.random_graph(n1, n2, p, seed=self.seed)

    def generate_maxsat_graph(self, n):
        divider = np.random.randint(1, 6)
        G = self.generate_bipartite_graph(n // divider, n - n // divider, self.er_prob)

        n_edges = len(G.edges)
        edges = list(G.edges)

        added_edges = 0
        while added_edges < n_edges * self.edge_addition_prob:
            i, j = np.random.randint(0, n), np.random.randint(0, n)
            if (i, j) not in edges and (j, i) not in edges:
                added_edges += 1
                edges.append((i, j))

        return edges

    def generate_instances(self):
        n = np.random.randint(self.min_n, self.max_n + 1)
        edges = self.generate_maxsat_graph(n)
        clauses = [(f'v{i},v{j}', 1) for i, j in edges] + [(f'-v{i},-v{j}', 1) for i, j in edges]

        res = {'clauses': clauses}

        res.update({
            'inventory_levels': np.random.randint(1, 10, size=n),
            'storage_capacity': np.random.randint(15, 50, size=n),
            'personnel_skill': np.random.randint(1, 5, size=n),
            'weather_impact': np.random.randint(0, 2, size=len(clauses)),
            'civil_unrest_impact': np.random.randint(0, 2, size=len(clauses)),
        })

        logical_dependencies = [(np.random.randint(0, len(clauses)), np.random.randint(0, len(clauses))) for _ in range(n // 2)]
        res.update({'logical_dependencies': logical_dependencies})

        # New stochastic and robust data generation
        uncertain_inventory = np.random.uniform(0.8, 1.2, size=n) * res['inventory_levels']
        robust_storage = np.random.uniform(0.9, 1.1, size=n) * res['storage_capacity']
        personnel_skill_variability = np.random.normal(0, 0.2, size=n) + res['personnel_skill']

        res.update({
            'stochastic_inventory_levels': uncertain_inventory.astype(int),
            'robust_storage_capacity': robust_storage.astype(int),
            'personnel_skill_variability': personnel_skill_variability.astype(int)
        })
        
        weather_scenarios = np.random.normal(1, 0.1, size=(len(clauses), self.num_scenarios))
        civil_unrest_scenarios = np.random.normal(1, 0.1, size=(len(clauses), self.num_scenarios))

        res.update({
            'weather_scenarios': weather_scenarios,
            'civil_unrest_scenarios': civil_unrest_scenarios
        })

        return res

    ################# PySCIPOpt Modeling #################
    def solve(self, instance):
        clauses = instance['clauses']
        inventory_levels = instance['inventory_levels']
        storage_capacity = instance['storage_capacity']
        personnel_skill = instance['personnel_skill']
        weather_impact = instance['weather_impact']
        civil_unrest_impact = instance['civil_unrest_impact']
        logical_dependencies = instance['logical_dependencies']
        stochastic_inventory_levels = instance['stochastic_inventory_levels']
        robust_storage_capacity = instance['robust_storage_capacity']
        personnel_skill_variability = instance['personnel_skill_variability']
        weather_scenarios = instance['weather_scenarios']
        civil_unrest_scenarios = instance['civil_unrest_scenarios']

        model = Model("MaxSatisfiability")
        var_names = {}  

        # Create variables for each literal and clause
        for idx, (clause, weight) in enumerate(clauses):
            for var in clause.split(','):
                literal = var[1:] if var.startswith('-') else var
                if literal not in var_names:
                    var_names[literal] = model.addVar(vtype="B", name=literal)
            clause_var = model.addVar(vtype="B", name=f"cl_{idx}")
            var_names[f"cl_{idx}"] = clause_var

        # Objective function - maximize the number of satisfied clauses
        objective_expr = quicksum(
            var_names[f"cl_{idx}"] * weight for idx, (clause, weight) in enumerate(clauses) if weight < np.inf
        )

        # Add constraints for each clause
        for idx, (clause, weight) in enumerate(clauses):
            vars_in_clause = clause.split(',')
            clause_var = var_names[f"cl_{idx}"]
            
            # Define the positive and negative parts
            positive_part = quicksum(var_names[var] for var in vars_in_clause if not var.startswith('-'))
            negative_part = quicksum(1 - var_names[var[1:]] for var in vars_in_clause if var.startswith('-'))
            
            # Total satisfied variables in the clause
            total_satisfied = positive_part + negative_part
            
            if weight < np.inf:
                model.addCons(total_satisfied >= clause_var, name=f"clause_{idx}")
            else:
                model.addCons(total_satisfied >= 1, name=f"clause_{idx}")

        # New constraints with stochastic and robust elements
        for idx, var in enumerate(var_names):
            if var.startswith("cl_"):  # for clause variables
                model.addCons(var_names[var] <= stochastic_inventory_levels[idx % len(stochastic_inventory_levels)], name=f"inventory_{var}")
                model.addCons(var_names[var] <= robust_storage_capacity[idx % len(robust_storage_capacity)], name=f"storage_{var}")
                model.addCons(var_names[var] <= personnel_skill_variability[idx % len(personnel_skill_variability)], name=f"personnel_{var}")

        for s in range(self.num_scenarios):
            for idx, (clause, _) in enumerate(clauses):
                model.addCons(var_names[f"cl_{idx}"] <= 1 + weather_scenarios[idx, s], name=f"weather_impact_{idx}_scenario{s}")
                model.addCons(var_names[f"cl_{idx}"] <= 1 + civil_unrest_scenarios[idx, s], name=f"civil_unrest_impact_{idx}_scenario{s}")

        # New logical dependencies constraints
        for (i, j) in logical_dependencies:
            model.addCons(var_names[f"cl_{i}"] <= var_names[f"cl_{j}"], name=f"logical_dependency_{i}_{j}")

        model.setObjective(objective_expr, "maximize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()
        
        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'min_n': 11,
        'max_n': 250,
        'er_prob': 0.31,
        'edge_addition_prob': 0.59,
        'num_scenarios': 2,
        'inventory_levels': (2, 25),
        'storage_capacity': (37, 125),
        'personnel_skill': (6, 30),
        'weather_impact': (0, 0),
        'civil_unrest_impact': (0, 0),
    }

    maxsat = MaxSatisfiability(parameters, seed=seed)
    instance = maxsat.generate_instances()
    solve_status, solve_time = maxsat.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")