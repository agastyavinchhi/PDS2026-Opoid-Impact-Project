"""
Merge the three cleaned county-year datasets into one.

Inputs (repo root):
  - census_county_year.parquet     county_fips, state_name, county_name, year, population (2000-2019)
  - shipments_county_year.parquet  BUYER_STATE, BUYER_COUNTY, year, MME (2006-2019, no FIPS)
  - mortality_county_year.parquet  fips, county_name, state_abbr, year, overdose_deaths,
                                   overdose_reported (2003-2015)

Steps:
  1. Give ARCOS counties a FIPS code by matching against
     the Census county list.
  2. Start from the Census data and left-join
     shipments and mortality onto it by county FIPS and year.
"""

import re
import unicodedata
import pandas as pd


def normalize_county(name):
    """
    Turn a county name into a match key so ARCOS and Census are the same (using regex).
    Examples:
    "SAINT JOHNS" -> "STJOHNS",
    """
    name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    )
    name = re.sub(r"\b(COUNTY|PARISH)\b", "", name)
    name = re.sub(r"\b(SAINTE|SAINT|STE)\b", "ST", name)
    return re.sub(r"[^A-Z0-9]", "", name)


def add_state_abbr(census, mortality):
    """Add state abbreviations to Census using the state FIPS -> abbr pairs in mortality."""
    pairs = mortality.assign(st=mortality["county_fips"].str[:2]).drop_duplicates("st")
    abbr = pairs.set_index("st")["state_abbr"]
    return census.assign(state_abbr=census["county_fips"].str[:2].map(abbr))


def add_fips_to_shipments(shipments, census):
    """Match ARCOS county names to Census FIPS; unmatched names are dropped."""
    crosswalk = census.drop_duplicates("county_fips")[
        ["county_fips", "state_abbr", "county_name"]
    ]
    crosswalk = crosswalk.assign(key=crosswalk["county_name"].map(normalize_county))
    shipments = shipments.assign(key=shipments["BUYER_COUNTY"].map(normalize_county))
    shipments = shipments.merge(
        crosswalk,
        left_on=["BUYER_STATE", "key"],
        right_on=["state_abbr", "key"],
        validate="many_to_one",
    )
    return shipments[["county_fips", "year", "MME"]].rename(columns={"MME": "mme"})


def merge_panel(census, shipments, mortality):
    """Left-join shipments and mortality onto Census county-years (2003-2019)."""
    panel = census[census["year"].between(2003, 2019)]
    panel = panel.merge(
        shipments, on=["county_fips", "year"], how="left", validate="1:1"
    )
    return panel.merge(
        mortality[["county_fips", "year", "overdose_deaths", "overdose_reported"]],
        on=["county_fips", "year"],
        how="left",
        validate="1:1",
    )


def add_outcomes(panel, mortality):
    """Add the mortality coverage flag and per-capita outcomes."""
    panel["mortality_in_coverage"] = panel["year"].between(2003, 2015) & panel[
        "county_fips"
    ].isin(mortality["county_fips"])
    panel["overdose_reported"] = panel["overdose_reported"].fillna(False).astype(bool)
    panel["mme_per_capita"] = panel["mme"] / panel["population"]
    panel["overdose_deaths_per_100k"] = (
        panel["overdose_deaths"] / panel["population"] * 100_000
    )
    return panel


def main():
    census = pd.read_parquet("census_county_year.parquet")
    shipments = pd.read_parquet("shipments_county_year.parquet")
    mortality = pd.read_parquet("mortality_county_year.parquet")
    mortality = mortality.rename(columns={"fips": "county_fips"})

    census = add_state_abbr(census, mortality)
    shipments = add_fips_to_shipments(shipments, census)
    panel = add_outcomes(merge_panel(census, shipments, mortality), mortality)

    assert panel["state_abbr"].notna().all()
    assert not panel.duplicated(["county_fips", "year"]).any()

    panel.to_parquet("merged_county_year.parquet", index=False)
    print(f"Done: merged_county_year.parquet {panel.shape}")


if __name__ == "__main__":
    main()
