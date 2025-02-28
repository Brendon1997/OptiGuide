import random
import time
import numpy as np
from pyscipopt import Model, quicksum

class ComplexAirlineSchedulingOptimization:
    def __init__(self, parameters, seed=None):
        for key, value in parameters.items():
            setattr(self, key, value)

        self.seed = seed
        if self.seed:
            random.seed(seed)
            np.random.seed(seed)
    
    def generate_instance(self):
        assert self.n_aircraft > 0 and self.n_trips > 0
        assert self.min_cost_aircraft >= 0 and self.max_cost_aircraft >= self.min_cost_aircraft
        assert self.min_cost_travel >= 0 and self.max_cost_travel >= self.min_cost_travel
        assert self.min_capacity_aircraft > 0 and self.max_capacity_aircraft >= self.min_capacity_aircraft
        assert self.min_trip_demand >= 0 and self.max_trip_demand >= self.min_trip_demand

        aircraft_usage_costs = np.random.randint(self.min_cost_aircraft, self.max_cost_aircraft + 1, self.n_aircraft)
        travel_costs = np.random.randint(self.min_cost_travel, self.max_cost_travel + 1, (self.n_aircraft, self.n_trips))
        capacities = np.random.randint(self.min_capacity_aircraft, self.max_capacity_aircraft + 1, self.n_aircraft)
        trip_demands = np.random.randint(self.min_trip_demand, self.max_trip_demand + 1, self.n_trips)
        no_flight_penalties = np.random.uniform(100, 300, self.n_trips).tolist()
        
        critical_trips_subsets = [random.sample(range(self.n_trips), int(0.2 * self.n_trips)) for _ in range(5)]
        min_coverage = np.random.randint(1, 5, 5)
        
        # Maintenance schedule and batch costs
        maintenance_schedule = np.random.choice([0, 1], size=self.n_aircraft).tolist()
        batch_transport_costs = np.random.uniform(50, 150, self.n_trips).tolist()

        # Facility-related data
        n_facilities = np.random.randint(self.min_n_facilities, self.max_n_facilities + 1)
        operating_cost = np.random.uniform(1000, 5000, n_facilities).tolist()
        facility_capacity = np.random.randint(self.facility_min_capacity, self.facility_max_capacity + 1, n_facilities).tolist()

        return {
            "aircraft_usage_costs": aircraft_usage_costs,
            "travel_costs": travel_costs,
            "capacities": capacities,
            "trip_demands": trip_demands,
            "no_flight_penalties": no_flight_penalties,
            "critical_trips_subsets": critical_trips_subsets,
            "min_coverage": min_coverage,
            "maintenance_schedule": maintenance_schedule,
            "batch_transport_costs": batch_transport_costs,
            "n_facilities": n_facilities,
            "operating_cost": operating_cost,
            "facility_capacity": facility_capacity
        }

    def solve(self, instance):
        aircraft_usage_costs = instance['aircraft_usage_costs']
        travel_costs = instance['travel_costs']
        capacities = instance['capacities']
        trip_demands = instance['trip_demands']
        no_flight_penalties = instance['no_flight_penalties']
        critical_trips_subsets = instance['critical_trips_subsets']
        min_coverage = instance['min_coverage']
        maintenance_schedule = instance['maintenance_schedule']
        batch_transport_costs = instance['batch_transport_costs']
        n_facilities = instance['n_facilities']
        operating_cost = instance['operating_cost']
        facility_capacity = instance['facility_capacity']

        model = Model("ComplexAirlineSchedulingOptimization")
        n_aircraft = len(aircraft_usage_costs)
        n_trips = len(trip_demands)
        
        aircraft_vars = {a: model.addVar(vtype="B", name=f"Aircraft_{a}") for a in range(n_aircraft)}
        trip_assignment_vars = {(a, t): model.addVar(vtype="C", name=f"Trip_{a}_Trip_{t}") for a in range(n_aircraft) for t in range(n_trips)}
        unmet_trip_vars = {t: model.addVar(vtype="C", name=f"Unmet_Trip_{t}") for t in range(n_trips)}
        maintenance_vars = {a: model.addVar(vtype="B", name=f"Maintenance_{a}") for a in range(n_aircraft)}

        # Facility variables
        facility_vars = {f: model.addVar(vtype="B", name=f"Facility_{f}") for f in range(n_facilities)}
        facility_trip_vars = {(f, t): model.addVar(vtype="C", name=f"Facility_{f}_Trip_{t}") for f in range(n_facilities) for t in range(n_trips)}

        # Objective
        model.setObjective(
            quicksum(aircraft_usage_costs[a] * aircraft_vars[a] for a in range(n_aircraft)) +
            quicksum(travel_costs[a][t] * trip_assignment_vars[a, t] for a in range(n_aircraft) for t in range(n_trips)) +
            quicksum(no_flight_penalties[t] * unmet_trip_vars[t] for t in range(n_trips)) +
            quicksum(batch_transport_costs[t] * trip_assignment_vars[a, t] for a in range(n_aircraft) for t in range(n_trips)) +
            quicksum(operating_cost[f] * facility_vars[f] for f in range(n_facilities)),
            "minimize"
        )

        # Constraints
        # Trip demand satisfaction (total flights and unmet trips must cover total demand)
        for t in range(n_trips):
            model.addCons(quicksum(trip_assignment_vars[a, t] for a in range(n_aircraft)) + unmet_trip_vars[t] == trip_demands[t], f"Trip_Demand_Satisfaction_{t}")
        
        # Capacity limits for each aircraft
        for a in range(n_aircraft):
            model.addCons(quicksum(trip_assignment_vars[a, t] for t in range(n_trips)) <= capacities[a] * aircraft_vars[a], f"Aircraft_Capacity_{a}")

        # Trip assignment only if aircraft is operational
        for a in range(n_aircraft):
            for t in range(n_trips):
                model.addCons(trip_assignment_vars[a, t] <= trip_demands[t] * aircraft_vars[a], f"Operational_Constraint_{a}_{t}")

        # Set covering constraints: ensure minimum number of critical trips covered by some aircraft
        for i, subset in enumerate(critical_trips_subsets):
            model.addCons(quicksum(trip_assignment_vars[a, t] for a in range(n_aircraft) for t in subset) >= min_coverage[i], f"Set_Covering_Constraint_{i}")

        # Maintenance constraints: aircraft only used if not in maintenance
        for a in range(n_aircraft):
            model.addCons(aircraft_vars[a] <= 1 - maintenance_schedule[a] * maintenance_vars[a], f"Maintenance_Schedule_{a}")

        # Facility capacity constraints
        for f in range(n_facilities):
            model.addCons(quicksum(facility_trip_vars[f, t] for t in range(n_trips)) <= facility_capacity[f] * facility_vars[f], f"Facility_Capacity_{f}")

        start_time = time.time()
        model.optimize()
        end_time = time.time()

        return model.getStatus(), end_time - start_time, model.getObjVal()
    
if __name__ == '__main__':
    seed = 42
    parameters = {
        'n_aircraft': 1000,
        'n_trips': 45,
        'min_cost_aircraft': 5000,
        'max_cost_aircraft': 10000,
        'min_cost_travel': 450,
        'max_cost_travel': 1200,
        'min_capacity_aircraft': 750,
        'max_capacity_aircraft': 1800,
        'min_trip_demand': 450,
        'max_trip_demand': 750,
        'min_n_facilities': 5,
        'max_n_facilities': 30,
        'facility_min_capacity': 1000,
        'facility_max_capacity': 3000,
    }

    airline_optimizer = ComplexAirlineSchedulingOptimization(parameters, seed=42)
    instance = airline_optimizer.generate_instance()
    solve_status, solve_time, objective_value = airline_optimizer.solve(instance)

    print(f"Solve Status: {solve_status}")
    print(f"Solve Time: {solve_time:.2f} seconds")
    print(f"Objective Value: {objective_value:.2f}")