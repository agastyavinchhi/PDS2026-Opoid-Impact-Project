# Census Population Data Cleaning

## Overview

This script cleans and combines U.S. Census Bureau county-level population estimates for 2000–2019. The resulting dataset provides annual county populations for calculating per-capita opioid shipments and drug overdose mortality rates.

## Data Sources

- **2000–2010:** Census Intercensal County Population Estimates
- **2010–2019:** Census County Population Estimates

Both original CSV files are retained locally and excluded from Git tracking.

## Cleaning Process

1. Retain county-level observations (`SUMLEV == 50`).
2. Exclude Alaska according to project requirements.
3. Construct standardized five-digit county FIPS identifiers using state and county codes.
4. Reshape annual population estimates from wide to long format.
5. Use 2000–2009 estimates from the earlier Census series and 2010–2019 estimates from the later series.
6. Combine the datasets and standardize column names.
7. Validate FIPS formatting, population values, missing observations, duplicate county-year combinations, and year coverage.

## Data Quality Findings

### County FIPS Differences

Three county FIPS identifiers do not appear in both Census datasets:

- `46113`: Shannon County, South Dakota (earlier series)
- `46102`: Oglala Lakota County, South Dakota (later series)
- `51515`: Bedford city, Virginia (earlier series)

These differences are associated with historical changes in county names, identifiers, or administrative boundaries.

Original FIPS codes are preserved. Geographic harmonization should be considered during integration with ARCOS and mortality datasets.

### Overlapping 2010 Population Estimates

Both Census sources contain 2010 population estimates. Among 3,112 matched counties, 3,062 have different estimates.

To avoid duplicate county-year records, the cleaned dataset uses the later Census series for 2010–2019 and the earlier series for 2000–2009.

A limitation is that combining two estimation series may introduce inconsistencies around the 2009–2010 boundary.

## Final Output

**File:** `data/processed/census_population_clean.parquet`

| Column | Description |
|---|---|
| `county_fips` | Five-digit county FIPS identifier |
| `state_name` | State name |
| `county_name` | County name |
| `year` | Calendar year |
| `population` | Annual county population estimate |

**Final dataset statistics:**

- 62,270 county-year observations
- 3,115 distinct FIPS identifiers across the combined series
- Years 2000–2019
- No missing values
- No duplicate county-year combinations
- No zero or negative population values
- No invalid FIPS formats
- Alaska excluded

Three FIPS identifiers have only 10 years of coverage due to differences between the two Census series.

## Reproducibility

Install the required Python packages:

```bash
python -m pip install pandas pyarrow
```

Place the two original Census CSV files in `data/raw/` and run the script from the project root:

```bash
python src/census_cleaning.py
```

The script writes the cleaned Parquet file to `data/processed/` and performs automated validation checks.

## Next Steps

The cleaned population dataset can be joined to opioid shipment and mortality data using `county_fips` and `year`. Geographic identifier differences should be evaluated before final integration.