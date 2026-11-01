import numpy as np
import simpy


class Store:
    # uproszczony sklep: c identycznych kas i jedna wspólna kolejka (M/M/c)

    def __init__(self, env, servers, arrivals_per_hour, mean_service_s, rng):
        self.env = env
        self.checkouts = simpy.Resource(env, capacity=servers)
        self.arrivals_per_hour = arrivals_per_hour
        self.mean_service_s = mean_service_s
        self.rng = rng

        self.waits = []          # czas czekania każdego klienta w kolejce
        self.times_in_system = []
        self.served = 0

        # do prawa Little'a: pole pod wykresem liczby klientów w sklepie
        self.in_system = 0
        self.last_change = 0.0
        self.area = 0.0

    def _update_area(self):
        self.area += self.in_system * (self.env.now - self.last_change)
        self.last_change = self.env.now

    def arrivals(self):
        mean_gap = 3600 / self.arrivals_per_hour
        while True:
            yield self.env.timeout(self.rng.exponential(mean_gap))
            self.env.process(self.customer())

    def customer(self):
        arrived = self.env.now
        self._update_area()
        self.in_system += 1

        with self.checkouts.request() as request:
            yield request
            self.waits.append(self.env.now - arrived)
            yield self.env.timeout(self.rng.exponential(self.mean_service_s))

        self._update_area()
        self.in_system -= 1
        self.served += 1
        self.times_in_system.append(self.env.now - arrived)

def run(servers, arrivals_per_hour, mean_service_s, hours=10, seed=0):
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    store = Store(env, servers, arrivals_per_hour, mean_service_s, rng)
    env.process(store.arrivals())
    env.run(until=hours * 3600)
    store._update_area()

    return {
        "mean_wait_s": np.mean(store.waits),
        "mean_time_in_system_s": np.mean(store.times_in_system),
        "mean_in_system": store.area / env.now,
        "throughput_per_hour": store.served / hours,
    }


if __name__ == "__main__":
    result = run(servers=4, arrivals_per_hour=80, mean_service_s=150, seed=1)
    for name, value in result.items():
        print(f"{name}: {value:.2f}")