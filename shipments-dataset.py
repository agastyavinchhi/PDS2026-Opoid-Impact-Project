"""
Stream the ARCOS opioid shipments data in chunks and aggregate MME by state, county and year.

Dataset Filters:
  - Sales only (TRANSACTION_CODE == "S")
  - Patient-facing buyers only (pharmacies, hospitals, practitioners, addiction treatment)
  - 50 states + DC (drops Alaska, territories, military mail codes)
  - Drop rows missing county or MME
"""

import zipfile
import pandas as pd

ZIP_PATH = "arcos_all.zip"
OUT_PATH = "shipments_county_year.parquet"
CHUNKSIZE = 5_000_000

COLS = [
    "TRANSACTION_CODE",
    "BUYER_BUS_ACT",
    "BUYER_STATE",
    "BUYER_COUNTY",
    "TRANSACTION_DATE",
    "MME",
]

STATES = [
    "AL",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]  # 50 states + DC, no AK

BUYERS = [
    # Pharmacies
    "CHAIN PHARMACY",
    "RETAIL PHARMACY",
    "M/O PHARMACY",
    "CENTRAL FILL PHARMACY",
    "PHARMACY - FED",
    "PHARMACY- MIL",
    "AUTOMATED DISPENSING SYSTEM",
    # Hospitals / clinics
    "HOSPITAL/CLINIC",
    "HOSP/CLINIC-VA",
    "HOSP/CLINIC- MIL",
    "HOSP/CLINIC FED",
    "HOSP/CLINIC NG",
    "CHAIN HOSP/CLINIC",
    # Practitioners
    "PRACTITIONER",
    "PRACTITIONER-DW/30",
    "PRACTITIONER-DW/100",
    "PRACTITIONER-DW/275",
    "PRACTITIONER FED",
    "PRACTITIONER-MILITARY",
    "MILITARY-PRACTITIONER",
    # Mid-level practitioners
    "MLP-NURSE PRACTITIONER",
    "MLP-NURSE PRACTITIONER-DW/30",
    "MLP-NURSE PRACTITIONER-DW/30SW",
    "MLP-NURSE PRACTITIONER-DW/100",
    "MLP-PHYSICIAN ASSISTANT",
    "MLP-PHYSICIAN ASSISTANT-DW/30",
    "MLP-PHYSICIAN ASSISTANT-DW/100",
    "MLP-PHYSICIAN ASSISTANT FED",
    "MLP-AMBULANCE SERVICE",
    "MLP-REGISTERED PHARMACIST",
    "MLP-NATUROPATHIC PHYSICIAN",
    "MLP-OPTOMETRIST",
    "MLP-MILITARY",
    # Addiction treatment
    "MAINT & DETOX",
    "MAINTENANCE",
    "DETOXIFICATION",
    "COMP/MAINT/DETOX",
    "COMPOUND/MAINT",
    "COMPOUND/DETOX",
]


def filter_chunk(chunk):
    """Keep sales to patient-facing buyers in the 50 states + DC, with county and MME present."""
    return chunk[
        (chunk["TRANSACTION_CODE"] == "S")
        & chunk["BUYER_BUS_ACT"].isin(BUYERS)
        & chunk["BUYER_STATE"].isin(STATES)
    ].dropna(subset=["BUYER_COUNTY", "MME"])


def aggregate_chunk(chunk):
    """Sum MME by state, county and year."""
    year = chunk["TRANSACTION_DATE"].str[:4].astype(int).rename("year")
    return chunk.groupby(["BUYER_STATE", "BUYER_COUNTY", year])["MME"].sum()


def process_chunk(i, chunk):
    kept = filter_chunk(chunk)
    print(f"chunk {i}: {len(chunk):,} read, {len(kept):,} kept", flush=True)
    return aggregate_chunk(kept)


def build_shipments(zip_path):
    """Stream the zipped file in chunks and return county-year MME totals."""
    with zipfile.ZipFile(zip_path) as zf, zf.open("arcos_all.tsv") as f:
        reader = pd.read_csv(
            f,
            sep="\t",
            usecols=COLS,
            dtype={"MME": "float64"},
            chunksize=CHUNKSIZE,
            low_memory=False,
        )
        parts = [process_chunk(i, chunk) for i, chunk in enumerate(reader)]
    return pd.concat(parts).groupby(level=[0, 1, 2]).sum().reset_index()


def main():
    shipments = build_shipments(ZIP_PATH)
    shipments.to_parquet(OUT_PATH, index=False)
    print(f"done: {len(shipments):,} rows saved")


if __name__ == "__main__":
    main()
