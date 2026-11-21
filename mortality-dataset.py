import sys
from pathlib import Path
import pandas as pd


# Folder with the raw CDC mortality files (kept outside the repo).
# The path must be passed as an argument, so the script runs on any machine:
#     py mortality-dataset.py "<path-to-your-US_VitalStatistics-folder>"
if len(sys.argv) < 2:
    sys.exit(
        "Error: please provide the path to the US_VitalStatistics folder.\n"
        'Usage: py mortality-dataset.py "<path-to-your-US_VitalStatistics-folder>"'
    )
SOURCE_DIR = Path(sys.argv[1])
if not SOURCE_DIR.is_dir():
    sys.exit(f"Error: folder not found: {SOURCE_DIR}")

# Drug poisoning (overdose) cause codes: D1 unintentional, D2 suicide,
# D3 homicide, D4 undetermined. D9 ("All other drug-induced causes")
# is not an overdose, so it is excluded.
OVERDOSE_CODES = ["D1", "D2", "D3", "D4"]

# Output file, saved in the repo root (same place as the script)
OUTPUT_PATH = Path(__file__).parent / "mortality_county_year.parquet"


def load_raw_files(source_dir: Path) -> pd.DataFrame:
    """Read all yearly mortality files and stack them into one table."""
    files = sorted(source_dir.glob("Underlying Cause of Death, *.txt"))
    assert len(files) == 13, f"Expected 13 files (2003-2015), found {len(files)}"

    frames = []
    for f in files:
        df = pd.read_csv(f, sep="\t", dtype=str)
        frames.append(df)

    # Every file must have the same columns before we stack them
    first_cols = list(frames[0].columns)
    for f, df in zip(files, frames):
        assert list(df.columns) == first_cols, f"Column mismatch in {f.name}"

    return pd.concat(frames, ignore_index=True)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Drop footnotes, keep needed columns, fix types, drop Alaska."""
    # 1. Real data rows have an empty Notes column; footnote rows do not
    df = raw[raw["Notes"].isna()].copy()

    # 2. Keep only the columns we need and give them short names
    df = df.rename(
        columns={
            "County": "county_name",
            "County Code": "fips",
            "Year": "year",
            "Drug/Alcohol Induced Cause Code": "cause_code",
            "Deaths": "deaths",
        }
    )[["county_name", "fips", "year", "cause_code", "deaths"]]

    # 2b. "Missing" means the county did not exist that year (e.g. merged
    #     Virginia cities, reorganized Alaska areas in 2015). This is not
    #     the same as suppressed (<10) data, so we drop these rows.
    missing = df["deaths"] == "Missing"
    print(f"Dropping {missing.sum()} rows with Deaths == 'Missing'")
    df = df[~missing]

    # 3. FIPS as a 5-character string: "1001" -> "01001"
    df["fips"] = df["fips"].str.strip().str.zfill(5)

    # 4. Numeric types: "2003.0" -> 2003, "397.0" -> 397
    df["year"] = pd.to_numeric(df["year"]).astype("int64")
    df["deaths"] = pd.to_numeric(df["deaths"]).astype("int64")

    # 5. Drop Alaska (state FIPS "02"), as required by the instructions
    df = df[~df["fips"].str.startswith("02")]

    # Sanity checks
    assert df["fips"].str.len().eq(5).all(), "Some FIPS codes are not 5 characters"
    assert df["year"].between(2003, 2015).all(), "Unexpected year values"
    assert not df.duplicated(["fips", "year", "cause_code"]).any(), "Duplicate rows"

    return df.reset_index(drop=True)


def aggregate_overdoses(df: pd.DataFrame) -> pd.DataFrame:
    """Sum overdose deaths across overdose cause codes for each county-year."""
    od = df[df["cause_code"].isin(OVERDOSE_CODES)]
    od = (
        od.groupby(["fips", "year"], as_index=False)["deaths"]
        .sum()
        .rename(columns={"deaths": "overdose_deaths"})
    )
    assert not od.duplicated(["fips", "year"]).any(), "Duplicate county-years"
    return od


def build_panel(cleaned: pd.DataFrame, overdoses: pd.DataFrame) -> pd.DataFrame:
    """
    Build a balanced county-year panel: every county appears once per year.
    County-years with no reported overdose deaths keep NaN and are flagged.
    """
    # All counties that appear in any year, under any cause code
    counties = (
        cleaned[["fips", "county_name"]]
        .drop_duplicates("fips")
        .assign(state_abbr=lambda d: d["county_name"].str[-2:])
    )
    years = pd.DataFrame({"year": sorted(cleaned["year"].unique())})

    # Every county x every year
    panel = counties.merge(years, how="cross")

    # Attach overdose counts; missing county-years become NaN
    panel = panel.merge(overdoses, on=["fips", "year"], how="left")

    # True  = at least one overdose category was reported
    # False = all overdose categories suppressed (<10 each) or truly zero
    panel["overdose_reported"] = panel["overdose_deaths"].notna()

    assert not panel.duplicated(["fips", "year"]).any(), "Duplicate county-years"
    assert len(panel) == len(counties) * len(years), "Panel is not balanced"

    return panel.sort_values(["fips", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    raw = load_raw_files(SOURCE_DIR)
    print("Combined shape:", raw.shape)

    cleaned = clean(raw)
    print("Cleaned shape:", cleaned.shape)

    overdoses = aggregate_overdoses(cleaned)
    print("Overdose county-years:", overdoses.shape)

    panel = build_panel(cleaned, overdoses)
    print("\nPanel shape:", panel.shape)
    print("Counties:", panel["fips"].nunique(), "| Years:", panel["year"].nunique())
    print(panel.head(15).to_string())
    print("\nShare of county-years with reported overdose deaths:",
          round(panel["overdose_reported"].mean(), 3))
    
    panel.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nSaved to {OUTPUT_PATH}")

    # Read the file back to confirm it was saved correctly
    check = pd.read_parquet(OUTPUT_PATH)
    assert check.shape == panel.shape, "Saved file does not match the panel"
    print("Read-back check passed:", check.shape)
    print(check.dtypes)