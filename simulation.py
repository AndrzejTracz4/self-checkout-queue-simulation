import math

import numpy as np
import pandas as pd
import simpy

import pos_data
from params import Params


def lognormal_params(mean, cv):
    # zamiana średniej i CV na mu i s rozkładu lognormalnego
    s2 = math.log(1 + cv ** 2)
    return math.log(mean) - s2 / 2, math.sqrt(s2)


def load_basket_cdf():
    dist = pd.read_csv(pos_data.RESULTS_DIR / "basket_distribution.csv")
    return dist["n"].to_numpy(), dist["cdf"].to_numpy()


class Store:

    def __init__(self, env, p, rng):
        self.env = env
        self.p = p
        self.rng = rng

        # każda kasa tradycyjna ma swoją kolejkę, SCO mają jedną wspólną
        self.trad = [simpy.Resource(env, capacity=1) for _ in range(p.trad_checkouts)]
        self.sco = simpy.Resource(env, capacity=p.sco_checkouts)

        self.basket_n, self.basket_cdf = load_basket_cdf()
        self.shop_mu, self.shop_s = lognormal_params(p.shopping_mean_s, p.shopping_cv)
        self.exc_mu, self.exc_s = lognormal_params(p.trad_exception_mean_s, p.trad_exception_cv)

        self.records = []

    # --- losowanie cech klienta ---

    def draw_basket(self):
        u = self.rng.random()
        i = np.searchsorted(self.basket_cdf, u)   # pierwsze n, dla którego F(n) >= u
        return int(self.basket_n[min(i, len(self.basket_n) - 1)])

    def draw_shopping_time(self):
        return math.exp(self.shop_mu + self.shop_s * self.rng.normal())

    def prefers_sco(self, n):
        z = self.p.logit_a + self.p.logit_b * math.log(n)
        p_sco = 1 / (1 + math.exp(-z))
        return self.rng.random() < p_sco

    # --- czasy obsługi ---

    def trad_service_time(self, n):
        p = self.p
        t = math.exp(p.trad_b + p.trad_a * math.log(n) + p.trad_sigma * self.rng.normal())
        t += self.rng.gamma(p.trad_break_k, p.trad_break_theta)
        if self.rng.random() < p.trad_exception_p:
            t += math.exp(self.exc_mu + self.exc_s * self.rng.normal())
        return t

    def sco_service_time(self, n):
        p = self.p
        scan = math.exp(p.sco_b + p.sco_a * math.log(n) + p.sco_sigma * self.rng.normal())
        pack = math.exp(p.pack_b + p.pack_a * math.log(n) + p.pack_sigma * self.rng.normal())
        return scan + pack

    # --- procesy ---

    def arrivals(self):
        mean_gap = 3600 / self.p.arrivals_per_hour
        while True:
            yield self.env.timeout(self.rng.exponential(mean_gap))
            self.env.process(self.customer())

    def customer(self):
        entered = self.env.now
        n = self.draw_basket()
        yield self.env.timeout(self.draw_shopping_time())

        at_checkouts = self.env.now
        if self.prefers_sco(n):
            checkout_type = "SCO"
            resource = self.sco
            service = self.sco_service_time(n)
        else:
            checkout_type = "TRAD"
            # najkrótsza kolejka spośród kas tradycyjnych
            resource = min(self.trad, key=lambda r: r.count + len(r.queue))
            service = self.trad_service_time(n)

        with resource.request() as request:
            yield request
            wait = self.env.now - at_checkouts
            yield self.env.timeout(service)

        self.records.append({
            "entered": entered,
            "at_checkouts": at_checkouts,
            "left": self.env.now,
            "items": n,
            "checkout": checkout_type,
            "wait_s": wait,
            "service_s": service,
        })


def run(p=None, seed=0):
    p = p or Params()
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    store = Store(env, p, rng)
    env.process(store.arrivals())
    env.run(until=p.hours * 3600)
    return pd.DataFrame(store.records)


if __name__ == "__main__":
    p = Params()
    df = run(p, seed=1)

    print(f"W0: {p.trad_checkouts} kasa tradycyjna, {p.sco_checkouts} SCO, "
          f"{p.arrivals_per_hour:.0f} klientów/h, {p.hours:.0f} h")
    print(f"obsłużonych klientów: {len(df)} ({len(df) / p.hours:.1f} na godzinę)")
    print(f"udział SCO: {(df['checkout'] == 'SCO').mean():.1%}")
    print(f"średni koszyk: {df['items'].mean():.1f}")
    print()
    summary = df.groupby("checkout").agg(
        klienci=("wait_s", "size"),
        czekanie_s=("wait_s", "mean"),
        obsluga_s=("service_s", "mean"),
        koszyk=("items", "mean"),
    )
    print(summary.round(1))