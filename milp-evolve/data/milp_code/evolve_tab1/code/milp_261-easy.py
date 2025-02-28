import random
import time
import numpy as np
from itertools import combinations
from pyscipopt import Model, quicksum

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

class RobustIndependentSet:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)
        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)

    ################# data generation #################
    def generate_graph(self):
        if self.graph_type == 'erdos_renyi':
            graph = Graph.erdos_renyi(self.n_nodes, self.edge_probability)
        elif self.graph_type == 'barabasi_albert':
            graph = Graph.barabasi_albert(self.n_nodes, self.affinity)
        else:
            raise ValueError("Unsupported graph type.")
        return graph

    def generate_instance(self):
        graph = self.generate_graph()
        
        # Generate node existence probabilities
        node_existence_prob = np.random.uniform(0.8, 1, self.n_nodes)
        
        # Generate removable edges with single cost
        removable_edges = {edge: np.random.uniform(1, 10) for edge in graph.edges if np.random.random() < self.removable_edge_prob}
        
        # Generate node weights
        node_weights = np.random.randint(1, self.max_weight, self.n_nodes)
        knapsack_capacity = np.random.randint(self.min_capacity, self.max_capacity)
        
        cliques = graph.efficient_greedy_clique_partition()
        inequalities = set(graph.edges)
        for clique in cliques:
            clique = tuple(sorted(clique))
            for edge in combinations(clique, 2):
                inequalities.remove(edge)
            if len(clique) > 1:
                inequalities.add(clique)
        
        # Delivery time windows and traffic condition effects
        delivery_windows = {node: (np.random.randint(8, 10), np.random.randint(16, 18)) for node in graph.nodes}
        traffic_conditions = {(u, v): np.random.uniform(1, 1.5) for u, v in graph.edges}
        fuel_efficiency = {node: np.random.uniform(5, 15) for node in graph.nodes}  # distance per unit of fuel
        
        res = {'graph': graph,
               'inequalities': inequalities,
               'node_existence_prob': node_existence_prob,
               'removable_edges': removable_edges,
               'node_weights': node_weights,
               'knapsack_capacity': knapsack_capacity,
               'delivery_windows': delivery_windows,
               'traffic_conditions': traffic_conditions,
               'fuel_efficiency': fuel_efficiency}
        
        return res

    ################# PySCIPOpt modeling #################
    def solve(self, instance):
        graph = instance['graph']
        inequalities = instance['inequalities']
        node_existence_prob = instance['node_existence_prob']
        removable_edges = instance['removable_edges']
        node_weights = instance['node_weights']
        knapsack_capacity = instance['knapsack_capacity']
        delivery_windows = instance['delivery_windows']
        traffic_conditions = instance['traffic_conditions']
        fuel_efficiency = instance['fuel_efficiency']

        model = Model("RobustIndependentSet")
        var_names = {}
        edge_vars = {}
        time_vars = {}
        late_delivery_penalty = {}

        for node in graph.nodes:
            var_names[node] = model.addVar(vtype="B", name=f"x_{node}")
            time_vars[node] = model.addVar(vtype="C", name=f"s_{node}")
            late_delivery_penalty[node] = model.addVar(vtype="C", name=f"l_{node}")

        for edge in removable_edges:
            u, v = edge
            edge_vars[edge] = model.addVar(vtype="B", name=f"y_{u}_{v}")

        for count, group in enumerate(inequalities):
            if len(group) > 1:
                model.addCons(quicksum(var_names[node] for node in group) <= 1, name=f"clique_{count}")

        for u, v in removable_edges:
            model.addCons(var_names[u] + var_names[v] - edge_vars[(u, v)] <= 1, name=f"edge_{u}_{v}")

        # Simplified knapsack constraint using nominal weights only
        model.addCons(quicksum(node_weights[node] * var_names[node] for node in graph.nodes) <= knapsack_capacity, name="knapsack")
        
        # Time window constraints
        for node in graph.nodes:
            start, end = delivery_windows[node]
            model.addCons(time_vars[node] >= start * var_names[node], name=f"time_start_{node}")
            model.addCons(time_vars[node] <= end * var_names[node], name=f"time_end_{node}")
            model.addCons(late_delivery_penalty[node] >= (time_vars[node] - end) * var_names[node], name=f"late_penalty_{node}")

        # Objective function to maximize deliveries while minimizing delays and fuel costs
        objective_expr = quicksum(node_existence_prob[node] * var_names[node] for node in graph.nodes)
        objective_expr -= quicksum(removable_edges[edge] * edge_vars[edge] for edge in removable_edges)
        objective_expr -= quicksum(traffic_conditions[edge] * fuel_efficiency[edge[0]] * edge_vars[edge] for edge in removable_edges)
        objective_expr -= quicksum(late_delivery_penalty[node] for node in graph.nodes)

        model.setObjective(objective_expr, "maximize")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time

if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_nodes': 421,
        'edge_probability': 0.73,
        'affinity': 108,
        'graph_type': 'barabasi_albert',
        'removable_edge_prob': 0.42,
        'max_weight': 2700,
        'min_capacity': 10000,
        'max_capacity': 15000,
        'time_window_start': 8,
        'time_window_end': 18,
        'late_penalty_factor': 2.0,
    }

    robust_independent_set = RobustIndependentSet(parameters, seed=seed)
    instance = robust_independent_set.generate_instance()
    solve_status, solve_time = robust_independent_set.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")