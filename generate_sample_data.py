"""Generate six years (2020-2025) of synthetic compulsory motor (TPL) policies.

Customers renew, lapse, come back after a gap, change cars or sell them to
other people, so every cohort category appears in the data. All identifiers
are random and fictional.
"""
from pathlib import Path

import numpy as np
import pandas as pd

YEARS = range(2020, 2026)


def plate(rng) -> str:
    return f"{rng.integers(10, 99)}-{chr(65 + rng.integers(0, 26))}{chr(65 + rng.integers(0, 26))}-{rng.integers(100, 999)}"


def main(out: Path, seed: int = 5) -> None:
    rng = np.random.default_rng(seed)
    out.parent.mkdir(parents=True, exist_ok=True)

    # population of (client, vehicle) pairs
    pairs = []
    for i in range(6000):
        ctype = "Individual" if rng.random() < 0.8 else "Corporate"
        client = f"{'I' if ctype == 'Individual' else 'C'}{rng.integers(1_000_000, 9_999_999)}"
        for _ in range(1 if ctype == "Individual" else int(rng.integers(1, 6))):
            pairs.append({"client_id": client, "client_type": ctype, "plate_number": plate(rng),
                          "first_year": int(rng.choice(list(YEARS), p=[0.3, 0.14, 0.14, 0.14, 0.14, 0.14]))})

    rows, pid = [], 1
    for p in pairs:
        active, stay = True, 0.72 if p["client_type"] == "Individual" else 0.8
        for y in YEARS:
            if y < p["first_year"]:
                continue
            if y > p["first_year"]:
                active = rng.random() < (stay if active else 0.12)   # 12% of lapsed ones come back
            if not active:
                continue
            if rng.random() < 0.03:                                  # car sold to a new owner
                p = {**p, "client_id": f"I{rng.integers(1_000_000, 9_999_999)}", "client_type": "Individual"}
            start = pd.Timestamp(f"{y}-01-01") + pd.Timedelta(days=int(rng.integers(0, 365)))
            premium = round(float(rng.uniform(50, 150)), 2)
            rows.append({"policy_number": f"TPL-{y}-{pid:07d}", "invoice_number": f"INV-{pid:08d}",
                         "start_date": start, "client_id": p["client_id"], "client_type": p["client_type"],
                         "plate_number": p["plate_number"], "gwp": premium})
            if rng.random() < 0.02:                                  # duplicated invoice row in the export
                rows.append(rows[-1].copy())
            pid += 1

    df = pd.DataFrame(rows)
    with pd.ExcelWriter(out) as xw:
        for y1, y2 in [(2020, 2021), (2022, 2023), (2024, 2025)]:   # exports come in 2-year files
            part = df[df["start_date"].dt.year.between(y1, y2)]
            part.to_excel(xw, sheet_name=f"{y1}-{y2}", index=False)
    print(f"{len(df)} policy rows written to {out.resolve()}")


if __name__ == "__main__":
    main(Path(__file__).parent / "data" / "tpl_policies.xlsx")
