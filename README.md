# Customer Cohort & Retention Analysis

Splits each year's motor TPL (compulsory third-party liability) portfolio into customer
cohorts to answer a simple question: **how much of this year's business is new, and how much
did we keep from previous years?**

## Categories

Each insured **(vehicle, owner)** pair in a year falls into exactly one category, based on the
two previous years:

| Category | Insured last year | Insured the year before | Meaning |
|---|:---:|:---:|---|
| **New** | ✗ | ✗ | new customer |
| **Retained** | ✓ | ✗ | second year with us |
| **Loyal** | ✓ | ✓ | 2+ years with us |
| **Win-back** | ✗ | ✓ | lapsed for a year, then came back |

The categories are **mutually exclusive and complete**, so New + Retained + Loyal + Win-back
always equals the total. The script checks this every year and stops with an error if the
numbers don't reconcile. An earlier version of this analysis silently dropped the Win-back
group, and this check exists to catch that kind of mistake.

### Why the key is (plate, owner)

If the key were only the plate number, a car sold to a new owner would look like a "loyal"
customer. Using the **(plate number, client id)** pair counts the new owner correctly as a
**new** customer.

## Output

For every year, client type (Individual / Corporate) and category: **vehicles, policies, GWP,
customers** and the category's share of policies. A summary sheet puts the years side by side.
Duplicated invoice rows in the export are removed before anything is counted.

## Quick start

```bash
pip install -r requirements.txt
python generate_sample_data.py
python cohort_analysis.py --years 2023 2024 2025
```

```
Loaded 22949 rows, removed 455 duplicated invoice rows
  2023: check passed (New + Retained + Loyal + Win-back = Total)
  2024: check passed (New + Retained + Loyal + Win-back = Total)
  2025: check passed (New + Retained + Loyal + Win-back = Total)

client_type category  Vehicles  Policies     GWP  Customers Share of policies
 Individual    Total      2794      2794 279,222       2794            100.0%
 Individual      New       931       931  93,839        931             33.3%
 Individual Retained       660       660  66,247        660             23.6%
 Individual    Loyal      1143      1143 113,428       1143             40.9%
 Individual Win-back        60        60   5,708         60              2.1%
```

## Tech

Python · pandas · XlsxWriter

> The data in this repository is randomly generated. No real company data is included.
