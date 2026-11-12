"""Customer cohort (retention) analysis for motor TPL policies.

Every (vehicle, owner) pair insured in a given year is put into exactly one
category by looking at the two previous years:

    New        - not insured in either of the two previous years
    Retained   - insured last year, not the year before   (1 year with us)
    Loyal      - insured in both previous years            (2+ years with us)
    Win-back   - not insured last year, but the year before (came back)

The key is the (plate number, client id) pair, so when a car is sold to a new
owner it correctly counts as a NEW customer. The four categories add up to the
total; the script checks this and fails loudly if they don't.

For each year x client type x category it reports vehicles, policies, GWP and
customers. Duplicated invoice rows are removed first.

Usage:
    python cohort_analysis.py --years 2023 2024 2025
"""
import argparse
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
CATEGORIES = ["New", "Retained", "Loyal", "Win-back"]


def load(path: Path) -> pd.DataFrame:
    df = pd.concat(pd.read_excel(path, sheet_name=None, dtype={"client_id": str}).values(), ignore_index=True)
    df.columns = df.columns.str.strip()
    before = len(df)
    df = df.drop_duplicates("invoice_number")
    print(f"Loaded {before} rows, removed {before - len(df)} duplicated invoice rows")
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["year"] = df["start_date"].dt.year
    df["plate_number"] = df["plate_number"].astype(str).str.strip().str.upper()
    df["client_id"] = df["client_id"].astype(str).str.strip().str.upper()
    df["key"] = list(zip(df["plate_number"], df["client_id"]))
    return df


def categorize(df: pd.DataFrame, year: int) -> pd.DataFrame:
    cur = df[df["year"] == year].copy()
    prev1 = set(df.loc[df["year"] == year - 1, "key"])
    prev2 = set(df.loc[df["year"] == year - 2, "key"])
    in1, in2 = cur["key"].isin(prev1), cur["key"].isin(prev2)
    cur["category"] = "New"
    cur.loc[in1 & ~in2, "category"] = "Retained"
    cur.loc[in1 & in2, "category"] = "Loyal"
    cur.loc[~in1 & in2, "category"] = "Win-back"
    return cur


def stats(cur: pd.DataFrame) -> pd.DataFrame:
    g = cur.groupby(["client_type", "category"])
    out = pd.DataFrame({
        "Vehicles": g["plate_number"].nunique(),
        "Policies": g["policy_number"].nunique(),
        "GWP": g["gwp"].sum().round(2),
        "Customers": g["client_id"].nunique(),
    }).reset_index()
    total = cur.groupby("client_type").agg(Vehicles=("plate_number", "nunique"), Policies=("policy_number", "nunique"),
                                           GWP=("gwp", "sum"), Customers=("client_id", "nunique")).reset_index()
    total["category"] = "Total"
    out = pd.concat([out, total], ignore_index=True)
    out["category"] = pd.Categorical(out["category"], ["Total"] + CATEGORIES, ordered=True)
    out = out.sort_values(["client_type", "category"]).reset_index(drop=True)
    tot = out.groupby("client_type")["Policies"].transform(lambda s: s[out.loc[s.index, "category"] == "Total"].iloc[0])
    out["Share of policies"] = out["Policies"] / tot
    return out


def check(out: pd.DataFrame, year: int) -> None:
    for ct, part in out.groupby("client_type"):
        total = int(part.loc[part["category"] == "Total", "Policies"].iloc[0])
        parts = int(part.loc[part["category"] != "Total", "Policies"].sum())
        if total != parts:
            raise AssertionError(f"{year} {ct}: categories sum to {parts}, total is {total}")
    print(f"  {year}: check passed (New + Retained + Loyal + Win-back = Total)")


def write(out_path: Path, results: dict[int, pd.DataFrame]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wide = []
    for year, df in results.items():
        wide.append(df.set_index(["client_type", "category"])[["Vehicles", "Policies", "GWP", "Customers"]]
                    .rename(columns=lambda c: f"{year} {c}"))
    summary = pd.concat(wide, axis=1).reset_index()
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as xw:
        wb = xw.book
        head = wb.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1, "text_wrap": True, "align": "center"})
        bold = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "num_format": "#,##0"})
        num, pct = wb.add_format({"num_format": "#,##0"}), wb.add_format({"num_format": "0.0%"})

        summary.to_excel(xw, sheet_name="Summary", index=False)
        ws = xw.sheets["Summary"]
        for c, col in enumerate(summary.columns):
            ws.write(0, c, str(col), head)
            ws.set_column(c, c, 14, num if c >= 2 else None)
        for r, cat in enumerate(summary["category"], start=1):
            if cat == "Total":
                ws.set_row(r, None, bold)
        ws.freeze_panes(1, 2)

        for year, df in results.items():
            df.to_excel(xw, sheet_name=str(year), index=False)
            ws = xw.sheets[str(year)]
            for c, col in enumerate(df.columns):
                ws.write(0, c, col, head)
                ws.set_column(c, c, 16, pct if col == "Share of policies" else num if c >= 2 else None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=BASE / "data" / "tpl_policies.xlsx")
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--out", type=Path, default=BASE / "output" / "customer_cohorts.xlsx")
    a = ap.parse_args()

    df = load(a.input)
    results = {}
    for y in a.years:
        if not {y - 1, y - 2} <= set(df["year"].dropna().astype(int)):
            print(f"  {y}: skipped, needs data for {y - 2} and {y - 1}")
            continue
        results[y] = stats(categorize(df, y))
        check(results[y], y)

    write(a.out, results)
    last = max(results)
    print(f"\n{last}:")
    print(results[last].to_string(index=False, formatters={"GWP": "{:,.0f}".format, "Share of policies": "{:.1%}".format}))
    print(f"\nReport saved to {a.out.resolve()}")


if __name__ == "__main__":
    main()
