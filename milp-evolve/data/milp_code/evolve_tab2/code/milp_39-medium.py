import random
import time
import numpy as np
import networkx as nx
from itertools import combinations
from pyscipopt import Model, quicksum


class JobScheduling:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    def create_random_precedence_constraints(self, n_jobs, n_groups=20):
        group_size = n_jobs // n_groups
        jobs = list(range(n_jobs))
        random.shuffle(jobs)
        job_groups = [sorted(jobs[i * group_size:(i + 1) * group_size]) for i in range(n_groups)]
        constraints = []
        for group in job_groups:
            for i in range(len(group) - 1):
                constraints.append((group[i], group[i + 1]))
        return constraints

    def generate_instance(self):
        processing_times = [random.randint(1, 50) for _ in range(self.n_jobs)] 
        precedence_constraints = self.create_random_precedence_constraints(self.n_jobs, self.n_groups)
        machine_assignment = [random.randint(0, self.n_machines - 1) for _ in range(self.n_jobs)]
        
        # Affinity and priority constraints
        affinities = np.random.randint(1, 10, size=self.n_jobs)
        machine_limits = np.random.randint(10, 50, size=self.n_machines)

        # Create conflict graph edges
        conflict_graphs = {j: nx.erdos_renyi_graph(len([i for i in range(self.n_jobs) if machine_assignment[i] == j]), self.conflict_probability) for j in range(self.n_machines)}
        conflicts = {}
        for j, graph in conflict_graphs.items():
            conflicts[j] = list(graph.edges)
        
        # Generate job groups for set covering
        job_groups = [random.sample(range(self.n_jobs), random.randint(3, 7)) for _ in range(self.n_groups)]

        res = {
            'processing_times': processing_times,
            'precedence_constraints': precedence_constraints,
            'machine_assignment': machine_assignment,
            'affinities': affinities,
            'machine_limits': machine_limits,
            'conflicts': conflicts,
            'job_groups': job_groups
        }
        return res

    def solve(self, instance):
        processing_times = instance['processing_times']
        precedence_constraints = instance['precedence_constraints']
        machine_assignment = instance['machine_assignment']
        affinities = instance['affinities']
        machine_limits = instance['machine_limits']
        conflicts = instance['conflicts']
        job_groups = instance['job_groups']
        
        model = Model("JobShopScheduling")

        c = {}
        s = {}
        y = {}
        z = {}
        penalties = {}
        end_time = model.addVar("end_time", vtype="C", lb=0)
        
        for i in range(self.n_jobs):
            c[i] = model.addVar(f"c{i}", vtype="C", lb=0)
            s[i] = model.addVar(f"s{i}", vtype="C", lb=0)
            z[i] = model.addVar(f"z{i}", vtype="B")

        for i in range(self.n_jobs):
            for k in range(self.n_jobs):
                if i != k:
                    y[i, k] = model.addVar(f"y_{i}_{k}", vtype="B")
        
        # Penalty variables for job groups
        penalty_cost = self.penalty_cost
        for group_id, group in enumerate(job_groups):
            penalties[group_id] = model.addVar(f"penalty_{group_id}", vtype="B")

        for j in range(self.n_machines):
            for u, v in conflicts[j]:
                model.addCons(y[u, v] == 1, f"conflict_{u}_{v}_machine{j}")

        # Objective: Minimize end time and penalties for uncovered groups
        model.setObjective(end_time - quicksum(affinities[i] * z[i] for i in range(self.n_jobs)) + penalty_cost * quicksum(penalties[g] for g in penalties), "minimize")
        
        for i in range(self.n_jobs):
            model.addCons(c[i] >= s[i] + processing_times[i], f"time_{i}")

        for job_before, job_after in precedence_constraints:
            model.addCons(s[job_after] >= c[job_before], f"prec_{job_before}_to_{job_after}")

        for i in range(self.n_jobs):
            model.addCons(end_time >= c[i], f"makespan_{i}")

        M = 1e6
        for j in range(self.n_machines):
            jobs_on_machine = [i for i in range(self.n_jobs) if machine_assignment[i] == j]
            for i in range(len(jobs_on_machine)):
                for k in range(i + 1, len(jobs_on_machine)):
                    job_i = jobs_on_machine[i]
                    job_k = jobs_on_machine[k]
                    model.addCons(s[job_k] >= c[job_i] - M * (1 - y[job_i, job_k]), f"seq_{job_i}_{job_k}_machine{j}")
                    model.addCons(s[job_i] >= c[job_k] - M * y[job_i, job_k], f"seq_{job_k}_{job_i}_machine{j}")
                    model.addCons(y[job_i, job_k] + y[job_k, job_i] == 1, f"order_{job_i}_{job_k}")

        for j in range(self.n_machines):
            model.addCons(quicksum(z[i] for i in range(self.n_jobs) if machine_assignment[i]==j) <= machine_limits[j], f"machine_limit_{j}")
        
        # Set covering constraints for job groups
        for group_id, group in enumerate(job_groups):
            model.addCons(quicksum(z[j] for j in group) >= 1 - penalties[group_id], f"set_cover_{group_id}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42

    parameters = {
        'n_jobs': 112,
        'n_machines': 15,
        'n_groups': 10,
        'conflict_probability': 0.1,
        'penalty_cost': 50  # penalty for failing to cover a job group
    }

    job_scheduling = JobScheduling(parameters, seed=seed)
    instance = job_scheduling.generate_instance()
    solve_status, solve_time = job_scheduling.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")