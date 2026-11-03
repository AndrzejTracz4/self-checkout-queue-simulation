import math
from dataclasses import replace

import numpy as np
import pandas as pd
from scipy import stats

import pos_data
import simulation
from params import Params

REPLICATIONS = 30
SATURATION_ARRIVALS = 400.0          # tylu klientów strefa na pewno nie obsłuży
LOAD_LEVELS = [0.50, 0.75, 0.90, 1.15]

# warianty strefy kasowej (W0 = stan obecny)
VARIANTS = {
    "W0": Params(),
    "W1": Params(assistants=2),
    "W2": Params(trad_checkouts=2),
    "W3": Params(sco_checkouts=5),
    "W4": Params(sco_checkouts=5, assistants=2),
}

def confidence_interval(values, level=0.95):
    # średnia i połowa szerokości przedziału ufności t-Studenta
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    t = stats.t.ppf(1 - (1 - level) / 2, n - 1)
    return values.mean(), t * values.std(ddof=1) / math.sqrt(n)

def summarize(df, p):
    # jedna replikacja -> jeden wiersz wyników; rozgrzewkę odrzucamy
    warmup = p.warmup_h * 3600
    measured_h = p.hours - p.warmup_h

    arrived = df[df["at_checkouts"] >= warmup]
    served = arrived[~arrived["balked"]]
    left = df[(df["left"] >= warmup) & ~df["balked"]]
    with_call = served[served["interventions"] > 0]

    return {
        "throughput_h": len(left) / measured_h,
        "wait_mean_s": served["wait_s"].mean(),
        "wait_p95_s": served["wait_s"].quantile(0.95),
        "wait_trad_s": served.loc[served["checkout"] == "TRAD", "wait_s"].mean(),
        "wait_sco_s": served.loc[served["checkout"] == "SCO", "wait_s"].mean(),
        "sco_share": (served["checkout"] == "SCO").mean(),
        "balked_share": arrived["balked"].mean(),
        "assistant_util": left["intervention_s"].sum() / (measured_h * 3600 * p.assistants),
        "assistant_wait_s": with_call["assistant_wait_s"].mean() if len(with_call) else np.nan,
    }

def replicate(p, replications=REPLICATIONS):
    # replikacja r ma ziarno r w każdym wariancie, więc ci sami klienci (CRN)
    rows = []
    for r in range(replications):
        row = summarize(simulation.run(p, seed=r), p)
        row["rep"] = r
        rows.append(row)
    return pd.DataFrame(rows)

def welch_curve(p, replications=REPLICATIONS, bin_min=10, window=7):
    # średnie czekanie w kolejnych 10-minutowych przedziałach, uśrednione po replikacjach
    bins = int(p.hours * 60 / bin_min)
    curves = np.full((replications, bins), np.nan)
    for r in range(replications):
        df = simulation.run(p, seed=r)
        df = df[~df["balked"]]
        b = (df["at_checkouts"] // (bin_min * 60)).astype(int)
        means = df.groupby(b)["wait_s"].mean()
        means = means[means.index < bins]
        curves[r, means.index] = means.values
    mean_curve = np.nanmean(curves, axis=0)
    smooth = pd.Series(mean_curve).rolling(window, center=True, min_periods=1).mean()
    minutes = (np.arange(bins) + 0.5) * bin_min
    return pd.DataFrame({"minute": minutes, "wait_mean_s": mean_curve, "smoothed_s": smooth})

def print_table(results, metric, title, fmt="{:.1f}"):
    print(title)
    for level, group in results.groupby("level", sort=False):
        cells = []
        for name in VARIANTS:
            mean, half = confidence_interval(group.loc[group["variant"] == name, metric])
            cells.append(f"{name} {fmt.format(mean)} ± {fmt.format(half)}")
        print(f"  {level:>4.0%}: " + " | ".join(cells))
    print()


def paired_differences(results, metric):
    # różnica wariant - W0 w tej samej replikacji (te same liczby losowe)
    print(f"różnica względem W0, {metric} (średnia ± 95% CI z różnic w parach)")
    for level, group in results.groupby("level", sort=False):
        base = group[group["variant"] == "W0"].set_index("rep")[metric]
        cells = []
        for name in list(VARIANTS)[1:]:
            other = group[group["variant"] == name].set_index("rep")[metric]
            mean, half = confidence_interval(other - base)
            cells.append(f"{name} {mean:+.1f} ± {half:.1f}")
        print(f"  {level:>4.0%}: " + " | ".join(cells))
    print()

if __name__ == "__main__":
    pos_data.RESULTS_DIR.mkdir(exist_ok=True)

    # 1. test nasycenia: przepustowość maksymalna każdego wariantu
    print(f"1. Test nasycenia ({SATURATION_ARRIVALS:.0f} klientów/h, {REPLICATIONS} replikacji)")
    capacity = {}
    for name, p in VARIANTS.items():
        res = replicate(replace(p, arrivals_per_hour=SATURATION_ARRIVALS))
        mean, half = confidence_interval(res["throughput_h"])
        capacity[name] = mean
        print(f"  {name}: {mean:.1f} ± {half:.1f} klientów/h")
    print()

    # 2. poziomy obciążenia liczone od przepustowości W0
    print("2. Poziomy obciążenia:", ", ".join(
        f"{lvl:.0%} = {lvl * capacity['W0']:.1f} kl./h" for lvl in LOAD_LEVELS))
    print()

    # 3. rozgrzewka: krzywa Welcha dla W0 przy 90% obciążenia
    p90 = replace(VARIANTS["W0"], arrivals_per_hour=0.90 * capacity["W0"])
    welch = welch_curve(p90)
    welch.to_csv(pos_data.RESULTS_DIR / "welch_curve.csv", index=False)
    print("3. Krzywa Welcha (W0, 90%): średnie czekanie w kolejnych godzinach")
    hourly = welch.groupby((welch["minute"] // 60).astype(int))["wait_mean_s"].mean()
    for hour, value in hourly.items():
        mark = "  <- rozgrzewka" if hour < p90.warmup_h else ""
        print(f"  {hour:2d}-{hour + 1:<2d} h: {value:6.1f} s{mark}")
    print()

    # 4. eksperyment główny: wszystkie warianty na każdym poziomie obciążenia
    rows = []
    for level in LOAD_LEVELS:
        arrivals = level * capacity["W0"]
        for name, p in VARIANTS.items():
            res = replicate(replace(p, arrivals_per_hour=arrivals))
            res["variant"], res["level"], res["arrivals_h"] = name, level, arrivals
            rows.append(res)
        print(f"  gotowe: poziom {level:.0%}")
    results = pd.concat(rows, ignore_index=True)
    results.to_csv(pos_data.RESULTS_DIR / "replications.csv", index=False)
    print(f"zapisano results/replications.csv ({len(results)} replikacji)")
    print()

    print_table(results, "wait_mean_s", "4. Średnie czekanie [s] (średnia ± 95% CI)")
    print_table(results, "throughput_h", "5. Przepustowość [klienci/h]")
    print_table(results, "balked_share", "6. Udział rezygnacji", fmt="{:.3f}")
    print_table(results, "assistant_util", "7. Zajętość asystenta", fmt="{:.3f}")
    paired_differences(results, "wait_mean_s")