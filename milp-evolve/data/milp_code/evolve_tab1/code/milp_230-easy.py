import random
import time
import numpy as np
from pyscipopt import Model, quicksum
import networkx as nx
from itertools import combinations

############# Helper function #############
class Graph:
    """
    Helper function: Container for a graph.
    """
    def __init__(self, number_of_nodes, edges, degrees, neighbors):
        self.number_of_nodes = number_of_nodes
        self.nodes = np.arange(number_of_nodes)
        self.edges = edges
        self.degrees = degrees
        self.neighbors = neighbors

    def efficient_greedy_clique_partition(self):
        """
        Partition the graph into cliques using an efficient greedy algorithm.
        """
        cliques = []
        leftover_nodes = (-self.degrees).argsort().tolist()
        while leftover_nodes:
            clique_center, leftover_nodes = leftover_nodes[0], leftover_nodes[1:]
            clique = {clique_center}
            neighbors = self.neighbors[clique_center].intersection(leftover_nodes)
            densest_neighbors = sorted(neighbors, key=lambda x: -self.degrees[x])
            for neighbor in densest_neighbors:
                if all([neighbor in self.neighbors[clique_node] for clique_node in clique]):
                    clique.add(neighbor)
            cliques.append(clique)
            leftover_nodes = [node for node in leftover_nodes if node not in clique]

        return cliques

    @staticmethod
    def erdos_renyi(number_of_nodes, edge_probability):
        """
        Generate an Erdös-Rényi random graph with a given edge probability.
        """
        edges = set()
        degrees = np.zeros(number_of_nodes, dtype=int)
        neighbors = {node: set() for node in range(number_of_nodes)}
        for edge in combinations(np.arange(number_of_nodes), 2):
            if np.random.uniform() < edge_probability:
                edges.add(edge)
                degrees[edge[0]] += 1
                degrees[edge[1]] += 1
                neighbors[edge[0]].add(edge[1])
                neighbors[edge[1]].add(edge[0])
        graph = Graph(number_of_nodes, edges, degrees, neighbors)
        return graph

    @staticmethod
    def barabasi_albert(number_of_nodes, affinity):
        """
        Generate a Barabási-Albert random graph with a given edge probability.
        """
        assert affinity >= 1 and affinity < number_of_nodes

        edges = set()
        degrees = np.zeros(number_of_nodes, dtype=int)
        neighbors = {node: set() for node in range(number_of_nodes)}
        for new_node in range(affinity, number_of_nodes):
            if new_node == affinity:
                neighborhood = np.arange(new_node)
            else:
                neighbor_prob = degrees[:new_node] / (2 * len(edges))
                neighborhood = np.random.choice(new_node, affinity, replace=False, p=neighbor_prob)
            for node in neighborhood:
                edges.add((node, new_node))
                degrees[node] += 1
                degrees[new_node] += 1
                neighbors[node].add(new_node)
                neighbors[new_node].add(node)

        graph = Graph(number_of_nodes, edges, degrees, neighbors)
        return graph
############# Helper function #############

class AdvancedCombinatorialAuctionWithFLPMutualExclusivity:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_instance(self):
        assert self.min_value >= 0 and self.max_value >= self.min_value
        assert self.add_item_prob >= 0 and self.add_item_prob <= 1

        values = self.min_value + (self.max_value - self.min_value) * np.random.rand(self.n_items)
        bids = []

        while len(bids) < self.n_bids:
            bundle_size = np.random.randint(1, self.max_bundle_size + 1)
            bundle = np.random.choice(self.n_items, size=bundle_size, replace=False)
            price = values[bundle].sum()
            complexity = np.random.poisson(lam=5)

            if price < 0:
                continue

            bids.append((bundle.tolist(), price, complexity))

        bids_per_item = [[] for _ in range(self.n_items)]
        for i, bid in enumerate(bids):
            bundle, price, complexity = bid
            for item in bundle:
                bids_per_item[item].append(i)

        n_facilities = np.random.randint(self.facility_min_count, self.facility_max_count)
        operating_cost = np.random.gamma(shape=2.0, scale=1.0, size=n_facilities).tolist()
        assignment_cost = np.random.normal(loc=5, scale=2, size=len(bids)).tolist()
        capacity = np.random.randint(10, 50, size=n_facilities).tolist()
        setup_cost = np.random.uniform(100, 500, size=n_facilities).tolist()
        maintenance_cost = np.random.lognormal(mean=3, sigma=1.0, size=n_facilities).tolist()

        mutual_exclusivity_pairs = []
        for _ in range(self.n_exclusive_pairs):
            fac1 = random.randint(0, n_facilities - 1)
            fac2 = random.randint(0, n_facilities - 1)
            if fac1 != fac2:
                mutual_exclusivity_pairs.append((fac1, fac2))

        # New - Generate set packing constraints
        set_packing_constraints = []
        if self.knapsack_constraints > 0:
            for _ in range(self.knapsack_constraints):
                knapsack_bids = np.random.choice(len(bids), size=np.random.randint(2, 5), replace=False).tolist()
                max_items = np.random.randint(1, len(knapsack_bids))
                set_packing_constraints.append((knapsack_bids, max_items))

        # New - Generate graph and node existence probabilities for bids
        if self.graph_type == 'erdos_renyi':
            bid_graph = Graph.erdos_renyi(self.n_bids, self.edge_probability)
        elif self.graph_type == 'barabasi_albert':
            bid_graph = Graph.barabasi_albert(self.n_bids, self.affinity)
        else:
            raise ValueError("Unsupported graph type.")

        node_existence_prob = np.random.uniform(0.8, 1, self.n_bids)
        
        cliques = bid_graph.efficient_greedy_clique_partition()
        inequalities = set(bid_graph.edges)
        for clique in cliques:
            clique = tuple(sorted(clique))
            for edge in combinations(clique, 2):
                inequalities.remove(edge)
            if len(clique) > 1:
                inequalities.add(clique)
        
        return {
            "bids": bids,
            "bids_per_item": bids_per_item,
            "n_facilities": n_facilities,
            "operating_cost": operating_cost,
            "assignment_cost": assignment_cost,
            "capacity": capacity,
            "setup_cost": setup_cost,
            "maintenance_cost": maintenance_cost,
            "mutual_exclusivity_pairs": mutual_exclusivity_pairs,
            "set_packing_constraints": set_packing_constraints,
            "bid_graph": bid_graph,
            "inequalities": inequalities,
            "node_existence_prob": node_existence_prob,
            "clique_indices": {i: clique for i, clique in enumerate(cliques)}
        }

    def solve(self, instance):
        bids = instance['bids']
        bids_per_item = instance['bids_per_item']
        n_facilities = instance['n_facilities']
        operating_cost = instance['operating_cost']
        assignment_cost = instance['assignment_cost']
        capacity = instance['capacity']
        setup_cost = instance['setup_cost']
        maintenance_cost = instance['maintenance_cost']
        mutual_exclusivity_pairs = instance['mutual_exclusivity_pairs']
        set_packing_constraints = instance['set_packing_constraints']
        bid_graph = instance['bid_graph']
        inequalities = instance['inequalities']
        node_existence_prob = instance['node_existence_prob']
        clique_indices = instance['clique_indices']

        model = Model("AdvancedCombinatorialAuctionWithFLPMutualExclusivity")

        bid_vars = {i: model.addVar(vtype="B", name=f"Bid_{i}") for i in range(len(bids))}
        y_vars = {j: model.addVar(vtype="B", name=f"y_{j}") for j in range(n_facilities)}
        x_vars = {(i, j): model.addVar(vtype="C", name=f"x_{i}_{j}", lb=0, ub=1) for i in range(len(bids)) for j in range(n_facilities)}
        facility_workload = {j: model.addVar(vtype="I", name=f"workload_{j}", lb=0) for j in range(n_facilities)}

        # New - Independent Set Constraints and Variables
        lambda_vars = [model.addVar(vtype="B", name=f"lambda_{i}") for i in clique_indices]
        for count, group in enumerate(inequalities):
            if len(group) > 1:
                model.addCons(quicksum(bid_vars[node] for node in group) <= 1, name=f"clique_{count}")
        for i in clique_indices:
            for node in clique_indices[i]:
                model.addCons(bid_vars[node] <= lambda_vars[i], name=f"convex_{i}_{node}")

        objective_expr = quicksum(price * bid_vars[i] for i, (bundle, price, complexity) in enumerate(bids)) \
                         - quicksum(operating_cost[j] * y_vars[j] for j in range(n_facilities)) \
                         - quicksum(assignment_cost[i] * x_vars[i, j] for i in range(len(bids)) for j in range(n_facilities)) \
                         - quicksum(setup_cost[j] * y_vars[j] for j in range(n_facilities)) \
                         - quicksum(maintenance_cost[j] * facility_workload[j] for j in range(n_facilities)) \
                         - quicksum(complexity * bid_vars[i] for i, (bundle, price, complexity) in enumerate(bids)) \
                         + quicksum(node_existence_prob[node] * bid_vars[node] for node in bid_graph.nodes)

        for item, bid_indices in enumerate(bids_per_item):
            model.addCons(quicksum(bid_vars[bid_idx] for bid_idx in bid_indices) <= 1, f"Item_{item}")

        for i in range(len(bids)):
            model.addCons(quicksum(x_vars[i, j] for j in range(n_facilities)) == bid_vars[i], f"BidFacility_{i}")

        for j in range(n_facilities):
            model.addCons(quicksum(x_vars[i, j] for i in range(len(bids))) <= capacity[j] * y_vars[j], f"FacilityCapacity_{j}")

        for j in range(n_facilities):
            model.addCons(facility_workload[j] == quicksum(x_vars[i, j] * bids[i][2] for i in range(len(bids))), f"Workload_{j}")

        max_complexity = quicksum(bids[i][2] for i in range(len(bids))) / 2
        model.addCons(quicksum(bids[i][2] * bid_vars[i] for i in range(len(bids))) <= max_complexity, "MaxComplexity")

        for fac1, fac2 in mutual_exclusivity_pairs:
            model.addCons(y_vars[fac1] + y_vars[fac2] <= 1, f"MutualExclusivity_{fac1}_{fac2}")

        # New - Set Packing Constraints
        for constraint_num, (knapsack_bids, max_items) in enumerate(set_packing_constraints):
            model.addCons(quicksum(bid_vars[bid] for bid in knapsack_bids) <= max_items, f"SetPacking_{constraint_num}")

        model.setObjective(objective_expr, "maximize")
        
        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_items': 1406,
        'n_bids': 37,
        'min_value': 150,
        'max_value': 5000,
        'max_bundle_size': 262,
        'add_item_prob': 0.66,
        'facility_min_count': 900,
        'facility_max_count': 1406,
        'complexity_mean': 75,
        'complexity_stddev': 22,
        'n_exclusive_pairs': 111,
        'knapsack_constraints': 150,
        'graph_type': 'barabasi_albert',
        'edge_probability': 0.66,
        'affinity': 20,
    }

    auction = AdvancedCombinatorialAuctionWithFLPMutualExclusivity(parameters, seed=42)
    instance = auction.generate_instance()
    solve_status, solve_time = auction.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")