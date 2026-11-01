import numpy as np
import pandas as pd
from scipy import optimize, stats

import pos_data

# udział SCO dzisiaj wg raportu ECR Retail Loss 2026
TARGET_SCO_SHARE = 0.54

def checkout_choice_table(df):
    # dla każdej liczby produktów: ile transakcji w sumie i ile na SCO
    table = df.groupby("ArtNum").agg(
        total=("checkout", "size"),
        sco=("checkout", lambda s: (s == "SCO").sum()),
    ).reset_index()
    table = table.rename(columns={"ArtNum": "n"})
    return table

def p_sco(n, a, b):
    return 1 / (1 + np.exp(-(a + b * np.log(n))))

def fit_logit(table):
    x = np.log(table["n"].to_numpy(dtype=float))
    k = table["sco"].to_numpy()
    m = table["total"].to_numpy()

    def minus_log_likelihood(params):
        a, b = params
        z = a + b * x
        # ln L = suma k*ln(p) + (m-k)*ln(1-p), zapisane w stabilnej postaci
        return -np.sum(k * z - m * np.logaddexp(0, z))

    result = optimize.minimize(minus_log_likelihood, x0=[0.0, -0.5])
    a, b = result.x
    return a, b

def sco_share(a, b, dist):
    return np.sum(dist["share"] * p_sco(dist["n"], a, b))


def shift_a(b, dist, target=TARGET_SCO_SHARE):
    def gap(a):
        return sco_share(a, b, dist) - target

    return optimize.brentq(gap, -5, 5)

def service_time_regression(df, checkout):
    g = df[df["checkout"] == checkout].copy()
    x = np.log(g["ArtNum"].to_numpy(dtype=float))
    y = np.log(g["TranTime"].to_numpy(dtype=float))

    # pierwsza regresja na wszystkich transakcjach
    first = stats.linregress(x, y)
    residuals = y - (first.intercept + first.slope * x)

    # reguła Tukeya: wyjątek = reszta powyżej Q3 + 1.5 * IQR
    q1, q3 = np.percentile(residuals, [25, 75])
    threshold = q3 + 1.5 * (q3 - q1)
    is_exception = residuals > threshold

    # druga regresja już bez wyjątków
    reg = stats.linregress(x[~is_exception], y[~is_exception])
    fitted = reg.intercept + reg.slope * x
    sigma = np.std(y[~is_exception] - fitted[~is_exception], ddof=1)

    # ile dłużej trwały wyjątki niż typowa transakcja z takim koszykiem
    typical_mean = np.exp(fitted + sigma ** 2 / 2)
    extra = g["TranTime"].to_numpy()[is_exception] - typical_mean[is_exception]
    extra = extra[extra > 0]
    ln_extra = np.log(extra)

    return {
        "b": reg.intercept,
        "a": reg.slope,
        "sigma": sigma,
        "r2": reg.rvalue ** 2,
        "q1": q1,
        "q3": q3,
        "threshold": threshold,
        "exception_share": is_exception.mean(),
        "exceptions": int(is_exception.sum()),
        "extra_mean": np.exp(ln_extra.mean() + ln_extra.var(ddof=1) / 2),
        "extra_cv": np.sqrt(np.exp(ln_extra.var(ddof=1)) - 1),
        "extra_median": np.median(extra),
    }

def peak_hours(df, per_period=20):
    # 20 najbardziej ruchliwych godzin w każdym z trzech okresów danych
    period = np.where(df["start"] < "2018-06-01", "2017-12",
                      np.where(df["start"] < "2019-03-15", "2019-02", "2019-03"))
    counts = (df.assign(period=period)
                .groupby(["period", "hour"]).size()
                .rename("n").reset_index())
    top = counts.sort_values("n", ascending=False).groupby("period").head(per_period)
    return top["hour"]

def breaks_between_customers(df):
    peak = df[df["hour"].isin(peak_hours(df)) & (df["BreakTime"] > 0)]
    result = {}
    for checkout in ["TRAD", "SCO"]:
        g = peak[peak["checkout"] == checkout]
        # bardzo długie przerwy to pusta kasa, a nie obsługa
        q1, q3 = g["BreakTime"].quantile([0.25, 0.75])
        g = g[g["BreakTime"] <= q3 + 1.5 * (q3 - q1)]

        if checkout == "TRAD":
            k, _, theta = stats.gamma.fit(g["BreakTime"], floc=0)
            result["TRAD"] = {"k": k, "theta": theta, "mean": k * theta}
        else:
            # na SCO przerwa to pakowanie, rośnie z koszykiem
            x = np.log(g["ArtNum"].to_numpy(dtype=float))
            y = np.log(g["BreakTime"].to_numpy(dtype=float))
            reg = stats.linregress(x, y)
            sigma = np.std(y - (reg.intercept + reg.slope * x), ddof=1)
            result["SCO"] = {"b": reg.intercept, "a": reg.slope, "sigma": sigma,
                             "mean": g["BreakTime"].mean()}
    return result

if __name__ == "__main__":
    df = pos_data.clean(pos_data.load_transactions())
    table = checkout_choice_table(df)
    dist = pos_data.basket_distribution(df)

    # etap 2: logit
    a, b = fit_logit(table)
    a_new = shift_a(b, dist)
    print(f"logit: a = {a:.4f} (dane), a = {a_new:.4f} (54% SCO), b = {b:.4f}")

    # etap 3: czasy obsługi
    print()
    rows = []
    for checkout in ["TRAD", "SCO"]:
        r = service_time_regression(df, checkout)
        print(f"{checkout}: ln T = {r['b']:.4f} + {r['a']:.4f} ln n, "
              f"sigma = {r['sigma']:.4f}, R2 = {r['r2']:.2f}")
        print(f"  wyjątki: {r['exceptions']} ({r['exception_share']:.2%}), "
              f"dodatkowo średnio {r['extra_mean']:.1f} s, mediana {r['extra_median']:.0f} s")
        rows.append({"checkout": checkout, **r})

    br = breaks_between_customers(df)
    print(f"\nprzerwa TRAD: gamma k = {br['TRAD']['k']:.3f}, theta = {br['TRAD']['theta']:.3f} s, "
          f"średnio {br['TRAD']['mean']:.1f} s")
    print(f"pakowanie SCO: ln T = {br['SCO']['b']:.4f} + {br['SCO']['a']:.4f} ln n, "
          f"sigma = {br['SCO']['sigma']:.4f}, średnio {br['SCO']['mean']:.1f} s")

    pos_data.RESULTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame({"a_data": [a], "a_shifted": [a_new], "b": [b]}).to_csv(
        pos_data.RESULTS_DIR / "logit_params.csv", index=False)
    pd.DataFrame(rows).to_csv(pos_data.RESULTS_DIR / "service_params.csv", index=False)
    pd.DataFrame(br).T.to_csv(pos_data.RESULTS_DIR / "break_params.csv")
    print("\nzapisano results/logit_params.csv, service_params.csv, break_params.csv")