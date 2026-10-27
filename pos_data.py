from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "pos"
RESULTS_DIR = BASE_DIR / "results"

SCO_GROUP_ID = 8 # w danych pos SCO jest pod ID 8

def load_transactions():
    files = sorted(DATA_DIR.glob("POS_transactions_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["checkout"] = "TRAD"
    df.loc[df["WorkstationGroupID"] == SCO_GROUP_ID, "checkout"] = "SCO"
    df["start"] = pd.to_datetime(df["BeginDateTime"])
    return df

def clean(df):
    # rekordy z czasem 0 albo bez produktów to błędy zapisu
    valid = (df["TranTime"] > 0) & (df["ArtNum"] > 0)
    return df[valid].copy()

def basket_distribution(df):
    counts = df["ArtNum"].value_counts().sort_index()
    dist = pd.DataFrame({"n": counts.index, "count": counts.values})
    dist["share"] = dist["count"] / dist["count"].sum()
    dist["cdf"] = dist["share"].cumsum()   # dystrybuanta F(n)
    return dist

if __name__ == "__main__":
    raw = load_transactions()
    df = clean(raw)

    print("transakcji w plikach:", len(raw))
    print("po czyszczeniu:", len(df), f"(usunięto {len(raw) - len(df)})")
    print("w tym na SCO:", (df["checkout"] == "SCO").sum(),
          f"= {(df['checkout'] == 'SCO').mean():.1%}")
    print("okres danych:", df["start"].min().date(), "-", df["start"].max().date())

    dist = basket_distribution(df)
    print()
    print("średni koszyk:", round(df["ArtNum"].mean(), 1))
    print("mediana:", df["ArtNum"].median())
    print("największy koszyk:", df["ArtNum"].max())
    print()
    for n in [1, 2, 3, 4, 5, 10, 20, 50, 100]:
        row = dist[dist["n"] == n].iloc[0]
        print(f"F({n}) = {row['cdf']:.1%}")

    print()
    print(df.groupby("checkout")["ArtNum"].mean())

    RESULTS_DIR.mkdir(exist_ok=True)
    dist.to_csv(RESULTS_DIR / "basket_distribution.csv", index=False)
    print("\nzapisano results/basket_distribution.csv")

