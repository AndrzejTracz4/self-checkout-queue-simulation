import math

import numpy as np

import model


def erlang_c_wait(arrivals_per_hour, mean_service_s, servers):
    # średni czas czekania w kolejce w systemie M/M/c (wzór Erlanga C)
    lam = arrivals_per_hour / 3600     # klienci na sekundę
    mu = 1 / mean_service_s            # obsługi na sekundę na jedną kasę
    c = servers
    A = lam / mu                       # obciążenie w erlangach
    rho = A / c                        # obciążenie jednej kasy

    top = A ** c / math.factorial(c) / (1 - rho)
    bottom = sum(A ** k / math.factorial(k) for k in range(c)) + top
    p_wait = top / bottom              # szansa, że klient musi czekać
    return p_wait / (c * mu - lam)


def confidence_interval(values):
    values = np.asarray(values)
    half = 2.045 * values.std(ddof=1) / math.sqrt(len(values))   # t(0,975; 29)
    return values.mean(), half


if __name__ == "__main__":
    lam, service, c = 80, 150, 4
    replications = 30

    results = [model.run(c, lam, service, hours=10, seed=r) for r in range(replications)]

    theory = erlang_c_wait(lam, service, c)
    waits = [r["mean_wait_s"] for r in results]
    mean_wait, half = confidence_interval(waits)

    print(f"M/M/{c}, lambda = {lam}/h, obsługa {service} s, obciążenie {lam * service / 3600 / c:.0%}")
    print(f"Erlang C (wzór):   {theory:.1f} s")
    print(f"symulacja:         {mean_wait:.1f} ± {half:.1f} s")
    ok = abs(mean_wait - theory) <= half
    print("wzór mieści się w przedziale ufności:", "TAK" if ok else "NIE")

    L = np.mean([r["mean_in_system"] for r in results])
    W = np.mean([r["mean_time_in_system_s"] for r in results])
    print(f"\nprawo Little'a: L = {L:.3f}, lambda * W = {lam / 3600 * W:.3f}")