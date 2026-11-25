"""
Census County Population Data Cleaning (2000–2019)

This script processes U.S. Census Bureau county-level population
estimates into a standardized county-year panel.

Data sources:
1. 2000–2010 Census Intercensal Population Estimates:
   https://www2.census.gov/programs-surveys/popest/datasets/2000-2010/intercensal/county/co-est00int-tot.csv

2. 2010–2019 Census Population Estimates:
   https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/counties/totals/co-est2019-alldata.csv

Cleaning steps:
- Keep county-level observations (SUMLEV = 50).
- Exclude Alaska according to project instructions.
- Construct standardized five-digit county FIPS codes.
- Reshape annual population estimates into long format.
- Use 2000–2009 from the earlier Census series and
  2010–2019 from the later series.
- Validate missing values, duplicates, FIPS, and population values.

Output:
    census_county_year.parquet

Output columns:
    county_fips, state_name, county_name, year, population

Notes:
- Historical FIPS changes exist for Shannon/Oglala Lakota
  County and Bedford city.
- The two Census estimation series contain different
  population estimates for 2010.
- Geographic harmonization will be addressed during
  data integration.

Usage:
    python census-dataset.py [path-to-census-data-folder]

Dependencies:
    pandas, pyarrow
"""

import sys
from pathlib import Path

import pandas as pd

# Default to the project's local raw-data folder
PROJECT_ROOT = Path(__file__).resolve().parent

RAW_DIR = (
    Path(sys.argv[1]).expanduser().resolve()
    if len(sys.argv) > 1
    else PROJECT_ROOT / "data" / "raw"
)

OUTPUT_DIR = PROJECT_ROOT


def load_census_data():
    """Load Census population data using official filenames."""
    old = pd.read_csv(
        RAW_DIR / "co-est00int-tot.csv",
        encoding="latin1",
        dtype={"STATE": str, "COUNTY": str},
        low_memory=False,
    )

    new = pd.read_csv(
        RAW_DIR / "co-est2019-alldata.csv",
        encoding="latin1",
        dtype={"STATE": str, "COUNTY": str},
        low_memory=False,
    )

    return old, new


def clean_counties(df):
    """Keep county observations and create five-digit FIPS."""
    df = df.loc[(df["SUMLEV"] == 50) & (df["STNAME"] != "Alaska")].copy()

    df["county_fips"] = df["STATE"].astype(str).str.zfill(2) + df["COUNTY"].astype(
        str
    ).str.zfill(3)

    return df


def reshape_population(df):
    """Convert annual population columns to county-year rows."""
    pop_cols = [col for col in df.columns if col.startswith("POPESTIMATE")]

    long_df = df.melt(
        id_vars=["county_fips", "STNAME", "CTYNAME"],
        value_vars=pop_cols,
        var_name="year",
        value_name="population",
    )

    long_df["year"] = (
        long_df["year"].str.replace("POPESTIMATE", "", regex=False).astype(int)
    )

    return long_df


def validate_population(df):
    """Check the cleaned population dataset."""
    assert df["county_fips"].str.fullmatch(r"\d{5}").all()
    assert df["county_fips"].notna().all()
    assert df["population"].notna().all()
    assert (df["population"] > 0).all()
    assert not df.duplicated(subset=["county_fips", "year"]).any()
    assert set(df["year"]) == set(range(2000, 2020))
    assert not (df["state_name"] == "Alaska").any()


def main():
    old, new = load_census_data()

    old = reshape_population(clean_counties(old))
    new = reshape_population(clean_counties(new))

    # Avoid overlapping 2010 records
    old = old.loc[old["year"] < 2010].copy()

    population = pd.concat(
        [old, new],
        ignore_index=True,
    )

    population = population.rename(
        columns={
            "STNAME": "state_name",
            "CTYNAME": "county_name",
        }
    )

    population = population.sort_values(["county_fips", "year"]).reset_index(drop=True)

    validate_population(population)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / "census_county_year.parquet"
    population.to_parquet(output_path, index=False)

    print(f"Saved: {output_path}")
    print(f"Shape: {population.shape}")
    print(f"Years: {population['year'].min()}–" f"{population['year'].max()}")
    print("All validation checks passed.")


if __name__ == "__main__":
    main()
