from pathlib import Path

import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def load_census_data():
    """Load the two original Census population datasets."""
    old = pd.read_csv(
        RAW_DIR / "census_2000_2010.csv",
        encoding="latin1",
        low_memory=False,
    )

    new = pd.read_csv(
        RAW_DIR / "census_2010_2019.csv",
        encoding="latin1",
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

    output_path = OUTPUT_DIR / "census_population_clean.parquet"
    population.to_parquet(output_path, index=False)

    print(f"Saved: {output_path}")
    print(f"Shape: {population.shape}")
    print(f"Years: {population['year'].min()}–" f"{population['year'].max()}")
    print("All validation checks passed.")


if __name__ == "__main__":
    main()
