"""Helpers for building ExternalLoads bundles."""

from __future__ import annotations

from pathlib import Path

from ..io.opensim import external_force_table, write_external_loads_xml, write_sto_table
from ..types import ExternalForceSpec, TrialResult
from ..utils.files import ensure_dir


def build_external_loads_bundle(
    trial: TrialResult,
    specs: list[ExternalForceSpec],
    output_dir: str | Path,
    stem: str | None = None,
) -> dict[str, Path]:
    out = ensure_dir(output_dir)
    stem = stem or trial.name
    force_table_path = out / f"{stem}_external_loads.sto"
    force_csv_path = out / f"{stem}_external_loads.csv"
    xml_path = out / f"{stem}_ExternalLoads.xml"

    df = external_force_table(trial, specs)
    write_sto_table(df, force_table_path, name=force_table_path.stem, in_degrees=False)
    df.to_csv(force_csv_path, index=False)
    write_external_loads_xml(specs, xml_path, data_file=force_table_path.name)
    return {"force_table": force_table_path, "force_table_csv": force_csv_path, "external_loads_xml": xml_path}
