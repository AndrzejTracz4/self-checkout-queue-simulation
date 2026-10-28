import numpy as np
import pandas as pd
from scipy import optimize

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

if __name__ == "__main__":
    df = pos_data.clean(pos_data.load_transactions())
    table = checkout_choice_table(df)
    dist = pos_data.basket_distribution(df)

    a, b = fit_logit(table)
    print(f"logit z danych: a = {a:.4f}, b = {b:.4f}")
    print(f"udział SCO wg modelu: {sco_share(a, b, dist):.1%}")

    a_new = shift_a(b, dist)
    print(f"\npo przesunięciu: a = {a_new:.4f}, b = {b:.4f}")
    print(f"udział SCO wg modelu: {sco_share(a_new, b, dist):.1%}")

    print("\nn    dane   model(dane)  model(54%)")
    for n in [1, 5, 10, 20, 30, 50]:
        row = table[table["n"] == n].iloc[0]
        data_share = row["sco"] / row["total"]
        print(f"{n:<4} {data_share:5.0%}   {p_sco(n, a, b):6.0%}       {p_sco(n, a_new, b):6.0%}")

    pos_data.RESULTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame({"a_data": [a], "a_shifted": [a_new], "b": [b]}).to_csv(
        pos_data.RESULTS_DIR / "logit_params.csv", index=False)
    print("\nzapisano results/logit_params.csv")