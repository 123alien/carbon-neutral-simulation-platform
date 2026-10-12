"""Prepare a small, traceable CBECS 2018 annual-energy validation slice."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cbecs2018" / "raw"
OUT = ROOT / "cbecs2018"
SELECTED = [1331, 1839, 4220]
KBTU_PER_MMBTU = 1000.0
AR4_CH4, AR4_N2O = 25.0, 298.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    raw_path = SOURCE / "cbecs2018_final_public.csv"
    codebook_path = SOURCE / "2018microdata_codebook.xlsx"
    frame = pd.read_csv(raw_path)
    selected = frame[frame.PUBID.isin(SELECTED)].copy().sort_values("PUBID")
    if selected.PUBID.tolist() != SELECTED:
        raise RuntimeError("selected CBECS buildings were not found")
    for column in ("ZELCNS", "ZNGCNS", "ZFKCNS", "ZDHBTU"):
        if selected[column].ne(0).any():
            raise RuntimeError(f"{column} contains imputed selected values")
    if selected.FKTYPE.ne(2).any():
        raise RuntimeError("selected fuel oil is not CBECS code 2 (diesel)")

    cleaned_dir, normalized_dir = OUT / "cleaned", OUT / "normalized"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    keep = ["PUBID", "PBA", "SQFT", "ELCNS", "ELBTU", "NGCNS", "NGBTU", "FKTYPE", "FKCNS", "FKBTU", "DHBTU", "MFBTU", "ZELCNS", "ZNGCNS", "ZFKCNS", "ZDHBTU"]
    selected[keep].to_csv(cleaned_dir / "cbecs2018_selected_buildings.csv", index=False)

    pba = {2: "OFFICE", 18: "LODGING"}
    buildings = []
    activities = []
    field_map = [
        ("electricity", "ELCNS", "kWh", "SCOPE_2"),
        ("natural_gas", "NGBTU", "kBtu", "SCOPE_1"),
        ("oil", "FKBTU", "kBtu", "SCOPE_1"),
        ("heat", "DHBTU", "kBtu", "SCOPE_2"),
    ]
    for row in selected.itertuples(index=False):
        buildings.append({
            "building_code": f"CBECS-{row.PUBID}", "name": f"CBECS Public Building {row.PUBID}",
            "building_type": pba.get(row.PBA, f"CBECS_PBA_{row.PBA}"), "floor_area_sqft": row.SQFT,
            "floor_area_m2": round(row.SQFT * 0.09290304, 6), "survey_year": 2018,
            "data_class": "REAL_PUBLIC_OFFICIAL",
        })
        for energy_type, field, unit, scope in field_map:
            activities.append({
                "building_code": f"CBECS-{row.PUBID}", "timestamp": "2018-01-01T00:00:00Z",
                "period_end": "2019-01-01T00:00:00Z", "period_granularity": "ANNUAL",
                "energy_type": energy_type, "value": float(getattr(row, field)), "unit": unit,
                "scope": scope, "source_field": field, "data_class": "REAL_PUBLIC_OFFICIAL",
            })
    pd.DataFrame(buildings).to_csv(normalized_dir / "buildings.csv", index=False)
    pd.DataFrame(activities).to_csv(normalized_dir / "accounting_activities.csv", index=False)

    factors = {
        "natural_gas": 53.06 + 0.001 * AR4_CH4 + 0.0001 * AR4_N2O,
        "oil": 73.96 + 0.003 * AR4_CH4 + 0.0006 * AR4_N2O,
        "heat": 66.33 + 0.001250 * AR4_CH4 + 0.000125 * AR4_N2O,
        "electricity": (947.2 + 0.085 * AR4_CH4 + 0.012 * AR4_N2O) * 0.45359237 / 1000,
    }
    factor_units = {"electricity": "kgCO2/kWh", "natural_gas": "kgCO2/MMBtu", "oil": "kgCO2/MMBtu", "heat": "kgCO2/MMBtu"}
    emissions = {key: 0.0 for key in factors}
    for activity in activities:
        canonical = activity["value"] if activity["unit"] == "kWh" else activity["value"] / KBTU_PER_MMBTU
        emissions[activity["energy_type"]] += canonical * factors[activity["energy_type"]] / 1000
    manifest = {
        "dataset": "EIA CBECS 2018 Final Public Use Microdata", "data_class": "REAL_PUBLIC_OFFICIAL",
        "source_url": "https://www.eia.gov/consumption/commercial/data/2018/index.php?view=microdata",
        "raw_rows": int(len(frame)), "selected_buildings": SELECTED, "selected_building_count": len(selected),
        "activity_records": len(activities), "time_granularity": "ANNUAL", "year": 2018,
        "missing_selected_values": int(selected[["ELCNS", "NGBTU", "FKBTU", "DHBTU"]].isna().sum().sum()),
        "negative_selected_values": int((selected[["ELCNS", "NGBTU", "FKBTU", "DHBTU"]] < 0).sum().sum()),
        "zero_selected_values": int((selected[["ELCNS", "NGBTU", "FKBTU", "DHBTU"]] == 0).sum().sum()),
        "imputed_selected_values": 0, "fuel_type": "Diesel (CBECS FKTYPE=2)",
        "raw_sha256": sha256(raw_path), "codebook_sha256": sha256(codebook_path),
        "factors": {key: {"value": value, "unit": factor_units[key]} for key, value in factors.items()},
        "expected_emissions_tco2e": emissions, "expected_total_tco2e": sum(emissions.values()),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
