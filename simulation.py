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

    def __init__(self, env, p, seed):
        self.env = env
        self.p = p
        self.seed = seed
        # wspólne liczby losowe: osobny strumień na przyjścia i osobny na każdego klienta
        self.arrival_rng = np.random.default_rng([seed, 0])
        self.customers_created = 0

        # każda kasa tradycyjna ma swoją kolejkę, SCO mają jedną wspólną
        self.trad = [simpy.Resource(env, capacity=1) for _ in range(p.trad_checkouts)]
        self.sco = simpy.Resource(env, capacity=p.sco_checkouts)
        self.assistant = simpy.Resource(env, capacity=p.assistants)

        self.basket_n, self.basket_cdf = load_basket_cdf()
        self.shop_mu, self.shop_s = lognormal_params(p.shopping_mean_s, p.shopping_cv)
        self.exc_mu, self.exc_s = lognormal_params(p.trad_exception_mean_s, p.trad_exception_cv)
        self.int_mu, self.int_s = lognormal_params(p.intervention_mean_s, p.intervention_cv)

        self.records = []

    # --- losowanie cech klienta ---

    def draw_basket(self, rng):
        u = rng.random()
        i = np.searchsorted(self.basket_cdf, u)  # pierwsze n, dla którego F(n) >= u
        return int(self.basket_n[min(i, len(self.basket_n) - 1)])

    def draw_shopping_time(self, rng):
        return math.exp(self.shop_mu + self.shop_s * rng.normal())

    def prefers_sco(self, rng, n):
        z = self.p.logit_a + self.p.logit_b * math.log(n)
        p_sco = 1 / (1 + math.exp(-z))
        return rng.random() < p_sco

    def draw_interventions(self, rng):
        # liczba wezwań asystenta (Poisson) i czas każdego z nich (lognormalny)
        k = rng.poisson(self.p.intervention_rate)
        return [math.exp(self.int_mu + self.int_s * rng.normal()) for _ in range(k)]

    def draw_card_retry(self, rng):
        return self.p.card_retry_s if rng.random() < self.p.card_retry_p else 0.0

    # --- czasy obsługi ---

    def trad_service_time(self, rng, n):
        p = self.p
        t = math.exp(p.trad_b + p.trad_a * math.log(n) + p.trad_sigma * rng.normal())
        t += rng.gamma(p.trad_break_k, p.trad_break_theta)
        if rng.random() < p.trad_exception_p:
            t += math.exp(self.exc_mu + self.exc_s * rng.normal())
        return t

    def sco_service_time(self, rng, n):
        # zwraca osobno skanowanie i pakowanie, bo interwencja jest między nimi
        p = self.p
        scan = math.exp(p.sco_b + p.sco_a * math.log(n) + p.sco_sigma * rng.normal())
        pack = math.exp(p.pack_b + p.pack_a * math.log(n) + p.pack_sigma * rng.normal())
        return scan, pack

    # --- szacowanie czekania (to, co klient widzi przy kasach) ---

    def wait_estimate(self, resource, ahead):
        # ahead = ile osób stoi w kolejce przed klientem
        if resource is self.sco:
            c = self.p.sco_checkouts
            return max(0, resource.count + ahead - c + 1) * self.p.est_sco_s / c
        return (resource.count + ahead) * self.p.est_trad_s

    def queues(self):
        # wszystkie kolejki, do których można podejść
        return self.trad + [self.sco]

    def choose_queue(self, preferred_sco):
        # najkrótsza kolejka preferowanego typu, chyba że inna daje dużo krótsze czekanie
        est = {r: self.wait_estimate(r, len(r.queue)) for r in self.queues()}
        preferred = [self.sco] if preferred_sco else self.trad
        best_preferred = min(preferred, key=est.get)
        best_any = min(est, key=est.get)
        if est[best_preferred] - est[best_any] > self.p.switch_threshold_s:
            return best_any
        return best_preferred

    def better_queue(self, current, request):
        # czy klient czekający w kolejce zyska na przejściu do innej
        now = self.wait_estimate(current, current.queue.index(request))
        others = [r for r in self.queues() if r is not current]
        best = min(others, key=lambda r: self.wait_estimate(r, len(r.queue)))
        if now - self.wait_estimate(best, len(best.queue)) > self.p.switch_threshold_s:
            return best
        return None

    # --- procesy ---

    def arrivals(self):
        mean_gap = 3600 / self.p.arrivals_per_hour
        while True:
            yield self.env.timeout(self.arrival_rng.exponential(mean_gap))
            self.customers_created += 1
            self.env.process(self.customer(self.customers_created))

    def sco_session(self, scan, pack, interventions):
        # klient zajmuje terminal przez cały czas, także gdy czeka na asystenta
        yield self.env.timeout(scan)
        assistant_wait = 0.0
        for duration in interventions:
            called = self.env.now
            with self.assistant.request() as call:
                yield call
                assistant_wait += self.env.now - called
                yield self.env.timeout(duration)
        yield self.env.timeout(pack)
        return assistant_wait

    def customer(self, number):
        entered = self.env.now

        # klient nr i ma własny generator, więc ma te same cechy w każdym wariancie
        rng = np.random.default_rng([self.seed, 1, number])
        n = self.draw_basket(rng)
        shopping = self.draw_shopping_time(rng)
        preferred_sco = self.prefers_sco(rng, n)
        trad_time = self.trad_service_time(rng, n)
        scan, pack = self.sco_service_time(rng, n)
        interventions = self.draw_interventions(rng)
        card_retry = self.draw_card_retry(rng)

        yield self.env.timeout(shopping)
        at_checkouts = self.env.now

        queue = self.choose_queue(preferred_sco)

        # rezygnacja: przy zbyt długiej kolejce klient odkłada koszyk i wychodzi
        if self.wait_estimate(queue, len(queue.queue)) > self.p.balk_wait_s:
            self.records.append({"entered": entered, "at_checkouts": at_checkouts,
                                 "left": at_checkouts, "items": n, "balked": True})
            return
        request = queue.request()
        switches = 0

        # czekanie: co jockey_check_s sekund klient sprawdza, czy opłaca się zmienić kolejkę
        while True:
            yield request | self.env.timeout(self.p.jockey_check_s)
            if request.triggered:
                break
            better = self.better_queue(queue, request)
            if better is not None:
                request.cancel()
                queue = better
                request = queue.request()
                switches += 1

        # zapis w chwili rozpoczęcia obsługi: czekanie jest już znane, nawet jeśli
        # symulacja skończy się w trakcie obsługi (inaczej gubilibyśmy najdłużej czekających)
        started = self.env.now
        record = {
            "entered": entered,
            "at_checkouts": at_checkouts,
            "left": np.nan,
            "items": n,
            "balked": False,
            "preferred": "SCO" if preferred_sco else "TRAD",
            "checkout": "SCO" if queue is self.sco else "TRAD",
            "switches": switches,
            "wait_s": started - at_checkouts,
            "service_s": np.nan,
            "interventions": 0,
            "intervention_s": 0.0,
            "assistant_wait_s": 0.0,
        }
        self.records.append(record)
        assistant_wait = 0.0

        if queue is self.sco:
            assistant_wait = yield from self.sco_session(scan, pack, interventions)
            yield self.env.timeout(card_retry)
        else:
            interventions = []  # u kasjera nie ma wezwań asystenta
            yield self.env.timeout(trad_time + card_retry)
        queue.release(request)

        record["left"] = self.env.now
        record["service_s"] = self.env.now - started
        record["interventions"] = len(interventions)
        record["intervention_s"] = sum(interventions)
        record["assistant_wait_s"] = assistant_wait


def run(p=None, seed=0):
    p = p or Params()
    env = simpy.Environment()
    store = Store(env, p, seed)
    env.process(store.arrivals())
    env.run(until=p.hours * 3600)
    return pd.DataFrame(store.records)


if __name__ == "__main__":
    p = Params()
    df = run(p, seed=1)
    df = df[~df["balked"] & df["left"].notna()]   # tylko klienci, którzy skończyli zakupy

    print(f"W0: {p.trad_checkouts} kasa tradycyjna, {p.sco_checkouts} SCO, "
          f"{p.assistants} asystent, {p.arrivals_per_hour:.0f} klientów/h, {p.hours:.0f} h")
    print(f"obsłużonych klientów: {len(df)} ({len(df) / p.hours:.1f} na godzinę)")
    print(f"preferowało SCO: {(df['preferred'] == 'SCO').mean():.1%}, "
          f"skorzystało z SCO: {(df['checkout'] == 'SCO').mean():.1%}")
    print(f"wybrało inny typ kasy niż preferowany: {(df['preferred'] != df['checkout']).mean():.1%}")
    print(f"zmieniło kolejkę w trakcie czekania: {(df['switches'] > 0).mean():.1%}")
    print()

    summary = df.groupby("checkout").agg(
        klienci=("wait_s", "size"),
        czekanie_s=("wait_s", "mean"),
        obsluga_s=("service_s", "mean"),
        koszyk=("items", "mean"),
    )
    print(summary.round(1))
    print()

    sco = df[df["checkout"] == "SCO"]
    busy = df["intervention_s"].sum() / (p.hours * 3600 * p.assistants)
    print(f"interwencje: {sco['interventions'].sum()} na {len(sco)} transakcji SCO "
          f"({sco['interventions'].mean():.3f} na transakcję)")
    print(f"średni czas interwencji: {df['intervention_s'].sum() / max(1, sco['interventions'].sum()):.1f} s")
    print(f"czekanie na asystenta: średnio {sco.loc[sco['interventions'] > 0, 'assistant_wait_s'].mean():.1f} s "
          f"(u klientów z interwencją)")
    print(f"zajętość asystenta: {busy:.1%}")