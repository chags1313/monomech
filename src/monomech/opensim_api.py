from __future__ import annotations

import importlib
import xml.etree.ElementTree as ET
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

from .config import OpenSimIDConfig, OpenSimIKConfig, OpenSimScaleConfig
from .external import ExternalLoadsSpec
from .io.storage import read_storage
from .io.trc import load_trc, write_trc
from .opensim_runtime import require_opensim
from .results import OpenSimScaleResult, StorageResult
from .utils import ensure_dir


@contextmanager
def _opensim_logging(osim, *, quiet: bool, log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    previous_level = None
    logger = getattr(osim, "Logger", None)
    if logger is not None and hasattr(logger, "setLevelString"):
        for getter in ("getLevelString", "get_level_string"):
            if hasattr(logger, getter):
                try:
                    previous_level = getattr(logger, getter)()
                    break
                except Exception:
                    pass
        if quiet:
            try:
                logger.setLevelString("Error")
            except Exception:
                try:
                    logger.setLevelString("error")
                except Exception:
                    pass

    with log_path.open("a", encoding="utf-8", newline="\n") as log_file:
        with redirect_stdout(log_file), redirect_stderr(log_file):
            try:
                yield
            finally:
                can_restore_level = (
                    previous_level is not None
                    and logger is not None
                    and hasattr(logger, "setLevelString")
                )
                if can_restore_level:
                    try:
                        logger.setLevelString(previous_level)
                    except Exception:
                        pass


def _finite_interp(values: np.ndarray, time: np.ndarray) -> tuple[np.ndarray, dict]:
    values = np.asarray(values, dtype=float)
    time = np.asarray(time, dtype=float)
    out = values.copy()
    invalid = ~np.isfinite(out)
    report = {
        "nan_count": int(invalid.sum()),
        "all_missing": bool(invalid.all()),
        "filled": False,
    }

    if not invalid.any():
        return out, report

    valid = np.isfinite(out) & np.isfinite(time)
    if valid.sum() >= 2:
        out[invalid] = np.interp(time[invalid], time[valid], out[valid])
    elif valid.sum() == 1:
        out[invalid] = out[valid][0]
    else:
        out[:] = 0.0
    report["filled"] = True
    return out, report


def _sanitize_marker_result_for_opensim(
    markers,
    *,
    output_dir: Path,
    prefix: str,
) -> tuple[Path | None, dict]:
    data = np.asarray(markers.data, dtype=float).copy()
    time = np.asarray(markers.time, dtype=float)
    report = {
        "input_nan_count": int((~np.isfinite(data)).sum()),
        "input_time_nan_count": int((~np.isfinite(time)).sum()),
        "all_missing_channels": [],
        "filled_channels": [],
    }

    if report["input_nan_count"] == 0 and report["input_time_nan_count"] == 0:
        return None, report

    if report["input_time_nan_count"]:
        if np.isfinite(time).sum() < 2:
            raise ValueError("OpenSim marker data must contain at least 2 finite time samples.")
        time, time_report = _finite_interp(time, np.arange(len(time), dtype=float))
        report["time_fill"] = time_report

    for marker_idx, marker_name in enumerate(markers.landmark_names):
        for dim_idx, dim_name in enumerate(markers.dims):
            filled, channel_report = _finite_interp(data[:, marker_idx, dim_idx], time)
            if channel_report["nan_count"]:
                label = f"{marker_name}_{dim_name}"
                report["filled_channels"].append(
                    {
                        "channel": label,
                        "nan_count": channel_report["nan_count"],
                        "all_missing": channel_report["all_missing"],
                    }
                )
                if channel_report["all_missing"]:
                    report["all_missing_channels"].append(label)
                data[:, marker_idx, dim_idx] = filled

    clean_path = (output_dir / f"{prefix}_opensim_ready.trc").resolve()
    write_trc(
        clean_path,
        time=time,
        data=data,
        marker_names=markers.landmark_names,
        units=(markers.metadata or {}).get("units", "m"),
        fps=markers.fps,
    )
    return clean_path, report


def _prepare_trc_for_opensim(
    trc_path: str | Path,
    *,
    output_dir: Path,
    prefix: str,
    sanitize: bool,
) -> tuple[Path, dict]:
    trc_path = Path(trc_path).resolve()
    marker_trial = load_trc(trc_path)
    markers = marker_trial.markers
    if markers is None:
        raise ValueError(f"TRC file did not contain marker data: {trc_path}")

    if not sanitize:
        nan_count = int((~np.isfinite(markers.data)).sum())
        if nan_count:
            raise ValueError(
                f"TRC file contains {nan_count} non-finite marker values. "
                "Pass a config with sanitize_marker_data=True or clean the TRC before OpenSim."
            )
        return trc_path, {"sanitized": False, "input_nan_count": 0}

    clean_path, report = _sanitize_marker_result_for_opensim(
        markers,
        output_dir=output_dir,
        prefix=prefix,
    )
    report["sanitized"] = clean_path is not None
    report["source_trc_path"] = str(trc_path)
    if clean_path is None:
        return trc_path, report
    report["prepared_trc_path"] = str(clean_path)
    return clean_path, report


def _write_storage_from_dataframe(path: Path, df: pd.DataFrame, *, name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"name {name}",
        f"datacolumns {len(df.columns)}",
        f"datarows {len(df)}",
        f"range {float(df.iloc[0, 0]):.6f} {float(df.iloc[-1, 0]):.6f}",
        "endheader",
    ]
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in header:
            f.write(line + "\n")
        f.write("\t".join(df.columns) + "\n")
        df.to_csv(f, sep="\t", index=False, header=False, float_format="%.8f")
    return path


def _summarize_ik_marker_errors(output_dir: Path) -> dict | None:
    candidates = sorted(output_dir.glob("*marker_errors.sto"))
    if not candidates:
        return None

    path = candidates[0]
    df = read_storage(path)
    if df.empty:
        return {"path": str(path), "rows": 0}

    summary: dict[str, object] = {"path": str(path), "rows": int(len(df))}
    for col in ("total_squared_error", "marker_error_RMS", "marker_error_max"):
        if col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        summary[col] = {
            "mean": float(np.mean(finite)),
            "median": float(np.median(finite)),
            "max": float(np.max(finite)),
        }
    if "marker_error_RMS" in df.columns:
        idx = pd.to_numeric(df["marker_error_RMS"], errors="coerce").idxmax()
        if np.isfinite(idx):
            summary["worst_rms_time"] = float(df.loc[idx, "time"]) if "time" in df.columns else None
    return summary


def _prepare_storage_for_opensim(
    storage_path: str | Path,
    *,
    output_dir: Path,
    prefix: str,
    sanitize: bool,
) -> tuple[Path, dict]:
    storage_path = Path(storage_path).resolve()
    df = read_storage(storage_path)
    if df.empty:
        raise ValueError(f"Storage file is empty: {storage_path}")

    time_col = "time" if "time" in df.columns else df.columns[0]
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    nonfinite_counts = {
        col: int((~np.isfinite(df[col].to_numpy(dtype=float))).sum()) for col in df.columns
    }
    total_nonfinite = sum(nonfinite_counts.values())

    if total_nonfinite == 0:
        return storage_path, {"sanitized": False, "input_nan_count": 0}
    if not sanitize:
        raise ValueError(
            f"Storage file contains {total_nonfinite} non-finite values. "
            "Pass a config with sanitize_coordinates=True or clean IK coordinates before ID."
        )

    time = df[time_col].to_numpy(dtype=float)
    if np.isfinite(time).sum() < 2:
        raise ValueError("OpenSim storage data must contain at least 2 finite time samples.")
    if not np.isfinite(time).all():
        time, _ = _finite_interp(time, np.arange(len(time), dtype=float))
        df[time_col] = time

    filled_columns = []
    for col in df.columns:
        if col == time_col:
            continue
        filled, report = _finite_interp(df[col].to_numpy(dtype=float), time)
        if report["nan_count"]:
            filled_columns.append(
                {
                    "column": col,
                    "nan_count": report["nan_count"],
                    "all_missing": report["all_missing"],
                }
            )
            df[col] = filled

    clean_path = (output_dir / f"{prefix}_coordinates_opensim_ready.mot").resolve()
    _write_storage_from_dataframe(clean_path, df, name=f"{prefix}_coordinates_opensim_ready")
    return clean_path, {
        "sanitized": True,
        "input_nan_count": int(total_nonfinite),
        "source_storage_path": str(storage_path),
        "prepared_storage_path": str(clean_path),
        "filled_columns": filled_columns,
    }


def _write_external_loads_data(
    loads,
    out_dir: Path,
    prefix: str,
    *,
    time_vector: np.ndarray | None = None,
) -> tuple[Path, Path]:
    out_dir = ensure_dir(Path(out_dir).resolve())
    specs = loads if isinstance(loads, list) else [loads]

    merged: pd.DataFrame | None = None
    force_specs = []

    for spec in specs:
        df = spec.data.copy()
        if time_vector is not None and (spec.metadata or {}).get("use_trial_time"):
            if len(time_vector) < 2:
                raise ValueError("A full-trial external load needs at least two IK time samples.")
            df = df.iloc[[0, -1]].copy().reset_index(drop=True)
            df["time"] = [float(time_vector[0]), float(time_vector[-1])]

        if spec.time_column != "time":
            df = df.rename(columns={spec.time_column: "time"})

        rename = {
            spec.force_columns[0]: f"{spec.name}_vx",
            spec.force_columns[1]: f"{spec.name}_vy",
            spec.force_columns[2]: f"{spec.name}_vz",
            spec.point_columns[0]: f"{spec.name}_px",
            spec.point_columns[1]: f"{spec.name}_py",
            spec.point_columns[2]: f"{spec.name}_pz",
        }

        df = df.rename(columns=rename)

        # Always provide torque columns, even if they are zero.
        if spec.torque_columns is not None:
            df = df.rename(
                columns={
                    spec.torque_columns[0]: f"{spec.name}_tx",
                    spec.torque_columns[1]: f"{spec.name}_ty",
                    spec.torque_columns[2]: f"{spec.name}_tz",
                }
            )
        else:
            df[f"{spec.name}_tx"] = 0.0
            df[f"{spec.name}_ty"] = 0.0
            df[f"{spec.name}_tz"] = 0.0

        keep = [
            "time",
            f"{spec.name}_vx", f"{spec.name}_vy", f"{spec.name}_vz",
            f"{spec.name}_px", f"{spec.name}_py", f"{spec.name}_pz",
            f"{spec.name}_tx", f"{spec.name}_ty", f"{spec.name}_tz",
        ]
        df = df[keep].copy()

        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)

        for col in keep:
            if col != "time":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        if time_vector is not None:
            df = _resample_load_df_to_time(df, time_vector)

        if merged is None:
            merged = df
        else:
            merged = (
                merged.merge(df, on="time", how="outer")
                .sort_values("time")
                .reset_index(drop=True)
            )
            merged = merged.fillna(0.0)

        force_specs.append(spec)

    if merged is None or merged.empty:
        raise ValueError("No valid external loads were provided.")
    merged = merged.replace([np.inf, -np.inf], 0.0).fillna(0.0)

    mot_path = (out_dir / f"{prefix}_external_loads.mot").resolve()
    xml_path = (out_dir / f"{prefix}_ExternalLoads.xml").resolve()

    header = [
        "name MonoMechExternalLoads",
        f"datacolumns {len(merged.columns)}",
        f"datarows {len(merged)}",
        f"range {float(merged['time'].iloc[0]):.6f} {float(merged['time'].iloc[-1]):.6f}",
        "endheader",
    ]

    with mot_path.open("w", encoding="utf-8", newline="\n") as f:
        for line in header:
            f.write(line + "\n")
        f.write("\t".join(merged.columns) + "\n")
        merged.to_csv(f, sep="\t", index=False, header=False, float_format="%.8f")

    root = ET.Element("OpenSimDocument", Version="40000")
    external_loads = ET.SubElement(root, "ExternalLoads", name="ExternalLoads")
    ET.SubElement(external_loads, "datafile").text = str(mot_path)

    objects = ET.SubElement(external_loads, "objects")
    for spec in force_specs:
        external = ET.SubElement(objects, "ExternalForce", name=spec.name)
        ET.SubElement(external, "applied_to_body").text = str(spec.applied_to_body)
        ET.SubElement(external, "force_expressed_in_body").text = str(spec.force_expressed_in)
        ET.SubElement(external, "point_expressed_in_body").text = str(spec.point_expressed_in)
        ET.SubElement(external, "force_identifier").text = f"{spec.name}_v"
        ET.SubElement(external, "point_identifier").text = f"{spec.name}_p"
        ET.SubElement(external, "torque_identifier").text = f"{spec.name}_t"

    ET.SubElement(external_loads, "groups")

    ET.indent(ET.ElementTree(root), space="  ")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    return mot_path, xml_path


def _validate_external_load_bodies(osim, model_path: Path, loads) -> dict:
    specs = loads if isinstance(loads, list) else [loads]
    specs = [spec for spec in specs if isinstance(spec, ExternalLoadsSpec)]
    if not specs:
        return {"validated": False, "load_count": 0, "body_names": []}

    model = osim.Model(str(model_path))
    body_set = model.getBodySet()
    body_names = {body_set.get(i).getName() for i in range(body_set.getSize())}
    body_names.add("ground")
    missing = sorted(
        {spec.applied_to_body for spec in specs if spec.applied_to_body not in body_names}
    )
    if missing:
        sample = ", ".join(sorted(body_names)[:12])
        raise ValueError(
            "External load applied_to_body does not match the OpenSim model: "
            f"{missing}. Use one of the model body names, for example: {sample}"
        )
    return {
        "validated": True,
        "load_count": len(specs),
        "applied_to_body": [spec.applied_to_body for spec in specs],
    }


def _resolve_scale_time_range(
    trc_path: str | Path,
    config: OpenSimScaleConfig,
) -> tuple[float, float]:
    marker_trial = load_trc(trc_path)
    time = marker_trial.markers.time

    if time is None or len(time) < 2:
        raise ValueError(f"TRC file must contain at least 2 valid time samples: {trc_path}")

    trc_start = float(time[0])
    trc_end = float(time[-1])

    time_window = getattr(config, "time_window", "auto")

    if time_window == "auto":
        start_time = trc_start
        end_time = trc_end
    else:
        start_time, end_time = time_window
        start_time = float(start_time)
        end_time = float(end_time)

    if not end_time > start_time:
        raise ValueError(
            f"Invalid scale time range: start_time={start_time}, end_time={end_time}"
        )

    return start_time, end_time


def _find_array_double_type(osim):
    """
    Find the OpenSim ArrayDouble class across official bindings, pyopensim,
    and possible submodules.
    """
    candidates = []

    # Top-level proxy/module.
    candidates.append(osim)

    # If the proxy keeps the base or tools modules, include those too.
    for attr in ("_base", "_tools"):
        mod = getattr(osim, attr, None)
        if mod is not None:
            candidates.append(mod)

    # Common likely import paths for official opensim / pyopensim layouts.
    module_names = [
        getattr(osim, "__name__", None),
        "pyopensim",
        "pyopensim.tools",
        "pyopensim.common",
        "pyopensim.simbody",
        "opensim",
        "opensim.common",
        "opensim.simbody",
    ]

    seen = set()
    for name in module_names:
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            candidates.append(importlib.import_module(name))
        except Exception:
            pass

    for mod in candidates:
        if hasattr(mod, "ArrayDouble"):
            return mod.ArrayDouble

    return None


def _make_osim_time_range(osim, start_time: float, end_time: float):
    """
    Build the OpenSim Array<double> object expected by setTimeRange().
    """
    array_double = _find_array_double_type(osim)
    if array_double is None:
        raise AttributeError(
            "Could not find ArrayDouble in the active OpenSim bindings. "
            "The binding does not appear to expose the OpenSim Array<double> type."
        )

    values = [float(start_time), float(end_time)]

    # Try a few common construction patterns.
    errors = []

    # Pattern 1: empty constructor + append
    try:
        arr = array_double()
        try:
            arr.append(values[0])
            arr.append(values[1])
            return arr
        except Exception:
            pass
        try:
            arr.set(0, values[0])
            arr.set(1, values[1])
            return arr
        except Exception:
            pass
    except Exception as exc:
        errors.append(f"ArrayDouble(): {exc}")

    # Pattern 2: construct with first value, then append second
    try:
        arr = array_double(values[0])
        try:
            arr.append(values[1])
            return arr
        except Exception:
            pass
    except Exception as exc:
        errors.append(f"ArrayDouble(start): {exc}")

    # Pattern 3: construct from a Python sequence if the binding supports it
    for candidate in (values, tuple(values)):
        try:
            arr = array_double(candidate)
            return arr
        except Exception as exc:
            errors.append(f"ArrayDouble({type(candidate).__name__}): {exc}")

    raise TypeError(
        "Could not construct an OpenSim ArrayDouble for setTimeRange(). "
        f"Errors: {errors}"
    )


def _set_time_range(target, osim, start_time: float, end_time: float) -> None:
    time_range = _make_osim_time_range(osim, start_time, end_time)
    errors = []

    for setter_name in ("setTimeRange", "set_time_range"):
        if not hasattr(target, setter_name):
            continue

        setter = getattr(target, setter_name)
        try:
            setter(time_range)
            return
        except Exception as exc:
            errors.append(f"{setter_name}({type(time_range).__name__}): {exc}")

    raise TypeError(
        "Could not set OpenSim time range with the constructed ArrayDouble. "
        f"Errors: {errors}"
    )



def run_scale(
    *,
    trc_path: str | Path,
    model_path: str | Path,
    output_dir: str | Path,
    config: OpenSimScaleConfig | None = None,
) -> OpenSimScaleResult:
    osim = require_opensim()
    config = config or OpenSimScaleConfig()

    trc_path = Path(trc_path).resolve()
    model_path = Path(model_path).resolve()
    output_dir = ensure_dir(Path(output_dir).resolve())

    if not trc_path.exists():
        raise FileNotFoundError(f"TRC file not found: {trc_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    prefix = config.output_prefix or trc_path.stem
    trc_path, preflight = _prepare_trc_for_opensim(
        trc_path,
        output_dir=output_dir,
        prefix=prefix,
        sanitize=bool(config.sanitize_marker_data),
    )
    scaled_model_path = (output_dir / f"{prefix}_scaled.osim").resolve()
    setup_xml_path = (output_dir / f"{prefix}_scale_setup.xml").resolve()

    # Resolve time range first
    t0, t1 = _resolve_scale_time_range(trc_path, config)

    # Create tool BEFORE using it
    scale_tool = osim.ScaleTool()
    scale_tool.setName(prefix)

    # Input files
    scale_tool.getGenericModelMaker().setModelFileName(str(model_path))
    scale_tool.getModelScaler().setMarkerFileName(str(trc_path))
    scale_tool.getMarkerPlacer().setMarkerFileName(str(trc_path))

    # Output files
    scale_tool.getModelScaler().setOutputModelFileName(str(scaled_model_path))
    scale_tool.getMarkerPlacer().setOutputModelFileName(str(scaled_model_path))

    # Time range
    _set_time_range(scale_tool.getModelScaler(), osim, t0, t1)
    _set_time_range(scale_tool.getMarkerPlacer(), osim, t0, t1)

    # Optional config hook
    if hasattr(config, "preserve_mass_distribution"):
        try:
            scale_tool.getModelScaler().setPreserveMassDist(
                bool(config.preserve_mass_distribution)
            )
        except Exception:
            pass

    scale_tool.printToXML(str(setup_xml_path))
    log_path = (output_dir / f"{prefix}_scale.log").resolve()
    with _opensim_logging(osim, quiet=bool(config.quiet), log_path=log_path):
        scale_tool.run()

    return OpenSimScaleResult(
        scaled_model_path=scaled_model_path,
        setup_xml_path=setup_xml_path,
        log_path=log_path,
        metadata={
            "trc_path": str(trc_path),
            "model_path": str(model_path),
            "time_range": [t0, t1],
            "output_dir": str(output_dir),
            "preflight": preflight,
            "log_path": str(log_path),
            "quiet": bool(config.quiet),
        },
    )


def run_ik(
    *,
    trc_path: str | Path,
    model_path: str | Path,
    output_dir: str | Path,
    config: OpenSimIKConfig | None = None,
) -> StorageResult:
    osim = require_opensim()
    config = config or OpenSimIKConfig()

    trc_path = Path(trc_path).resolve()
    model_path = Path(model_path).resolve()
    output_dir = ensure_dir(Path(output_dir).resolve())

    if not trc_path.exists():
        raise FileNotFoundError(f"TRC file not found: {trc_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    prefix = config.output_prefix or trc_path.stem
    trc_path, preflight = _prepare_trc_for_opensim(
        trc_path,
        output_dir=output_dir,
        prefix=prefix,
        sanitize=bool(config.sanitize_marker_data),
    )
    mot_path = output_dir / f"{prefix}_ik.mot"
    setup_xml_path = output_dir / f"{prefix}_ik_setup.xml"

    # Read TRC so IK uses the full marker time range
    trc_trial = load_trc(trc_path)
    time = trc_trial.markers.time
    if time is None or len(time) < 2:
        raise ValueError(f"TRC file must contain at least 2 valid time samples: {trc_path}")

    start_time = float(time[0])
    end_time = float(time[-1])

    ik = osim.InverseKinematicsTool()

    # Model file
    if hasattr(ik, "setModelFileName"):
        ik.setModelFileName(str(model_path))
    elif hasattr(ik, "set_model_file"):
        ik.set_model_file(str(model_path))
    else:
        raise AttributeError(
            "Could not find a compatible model-file setter on InverseKinematicsTool."
        )

    # Marker data
    if hasattr(ik, "setMarkerDataFileName"):
        ik.setMarkerDataFileName(str(trc_path))
    elif hasattr(ik, "set_marker_data_file_name"):
        ik.set_marker_data_file_name(str(trc_path))
    else:
        raise AttributeError(
            "Could not find a compatible marker-data setter on InverseKinematicsTool."
        )

    # Output motion
    if hasattr(ik, "setOutputMotionFileName"):
        ik.setOutputMotionFileName(str(mot_path))
    elif hasattr(ik, "set_output_motion_file_name"):
        ik.set_output_motion_file_name(str(mot_path))
    else:
        raise AttributeError(
            "Could not find a compatible output-motion setter on InverseKinematicsTool."
        )

    # Results dir
    if hasattr(ik, "setResultsDir"):
        ik.setResultsDir(str(output_dir))
    elif hasattr(ik, "set_results_dir"):
        ik.set_results_dir(str(output_dir))

    # Marker weights
    for marker, weight in config.marker_weights.items():
        task = osim.IKMarkerTask(marker)
        task.setWeight(float(weight))
        ik.getIKTaskSet().cloneAndAppend(task)

    # Accuracy
    if hasattr(ik, "set_accuracy"):
        ik.set_accuracy(float(config.accuracy))
    elif hasattr(ik, "setAccuracy"):
        ik.setAccuracy(float(config.accuracy))
    else:
        raise AttributeError(
            "InverseKinematicsTool has neither set_accuracy nor setAccuracy in this OpenSim build."
        )

    # IMPORTANT: explicitly set full TRC time range
    if hasattr(ik, "setStartTime"):
        ik.setStartTime(start_time)
        ik.setEndTime(end_time)
    elif hasattr(ik, "set_start_time"):
        ik.set_start_time(start_time)
        ik.set_end_time(end_time)
    else:
        raise AttributeError(
            "InverseKinematicsTool has neither setStartTime/setEndTime "
            "nor set_start_time/set_end_time in this OpenSim build."
        )

    ik.printToXML(str(setup_xml_path))
    log_path = (output_dir / f"{prefix}_ik.log").resolve()
    with _opensim_logging(osim, quiet=bool(config.quiet), log_path=log_path):
        ik.run()
    marker_error_summary = _summarize_ik_marker_errors(output_dir)

    return StorageResult(
        path=mot_path,
        dataframe=read_storage(mot_path),
        metadata={
            "setup_xml_path": str(setup_xml_path),
            "trc_path": str(trc_path),
            "time_range": [start_time, end_time],
            "preflight": preflight,
            "marker_error_summary": marker_error_summary,
            "log_path": str(log_path),
            "quiet": bool(config.quiet),
        },
    )


def run_id(
    *,
    ik_path: str | Path,
    model_path: str | Path,
    output_dir: str | Path,
    external_forces: ExternalLoadsSpec | list[ExternalLoadsSpec] | None = None,
    config: OpenSimIDConfig | None = None,
) -> StorageResult:
    osim = require_opensim()
    config = config or OpenSimIDConfig()

    ik_path = Path(ik_path).resolve()
    model_path = Path(model_path).resolve()
    output_dir = ensure_dir(Path(output_dir).resolve())

    if not ik_path.exists():
        raise FileNotFoundError(f"IK file not found: {ik_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    prefix = config.output_prefix or ik_path.stem.replace("_ik", "")
    ik_path, coordinate_preflight = _prepare_storage_for_opensim(
        ik_path,
        output_dir=output_dir,
        prefix=prefix,
        sanitize=bool(config.sanitize_coordinates),
    )
    sto_name = f"{prefix}_id.sto"
    sto_path = (output_dir / sto_name).resolve()
    setup_xml_path = (output_dir / f"{prefix}_id_setup.xml").resolve()

    external_mot = None
    external_xml = None
    external_loads_validation = None

    if external_forces is not None:
        ik_time = _read_storage_time_vector(ik_path)
        external_loads_validation = _validate_external_load_bodies(
            osim, model_path, external_forces
        )
        external_mot, external_xml = _write_external_loads_data(
            external_forces,
            output_dir,
            prefix,
            time_vector=ik_time,
        )

    tool = osim.InverseDynamicsTool()
    tool.setName(prefix)
    tool.setModelFileName(str(model_path))
    tool.setCoordinatesFileName(str(ik_path))

    # For ID, prefer basename + results dir.
    if hasattr(tool, "setResultsDir"):
        tool.setResultsDir(str(output_dir))
    elif hasattr(tool, "set_results_dir"):
        tool.set_results_dir(str(output_dir))

    tool.setOutputGenForceFileName(sto_name)

    if getattr(config, "lowpass_cutoff_hz", -1) >= 0:
        tool.setLowpassCutoffFrequency(float(config.lowpass_cutoff_hz))

    ik_df = read_storage(ik_path)
    time_col = "time" if "time" in ik_df.columns else ik_df.columns[0]
    start_time = float(ik_df[time_col].iloc[0])
    end_time = float(ik_df[time_col].iloc[-1])

    time_window = getattr(config, "time_window", "auto")
    if time_window != "auto":
        start_time, end_time = time_window
        start_time = float(start_time)
        end_time = float(end_time)

    if hasattr(tool, "setStartTime"):
        tool.setStartTime(start_time)
        tool.setEndTime(end_time)
    elif hasattr(tool, "set_start_time"):
        tool.set_start_time(start_time)
        tool.set_end_time(end_time)
    else:
        raise AttributeError(
            "Could not find compatible start/end time setters on InverseDynamicsTool."
        )

    if external_xml is not None:
        if hasattr(tool, "setExternalLoadsFileName"):
            tool.setExternalLoadsFileName(str(external_xml))
        elif hasattr(tool, "set_external_loads_file_name"):
            tool.set_external_loads_file_name(str(external_xml))
        else:
            raise AttributeError(
                "Could not find a compatible external loads setter on InverseDynamicsTool."
            )

    tool.printToXML(str(setup_xml_path))
    log_path = (output_dir / f"{prefix}_id.log").resolve()
    with _opensim_logging(osim, quiet=bool(config.quiet), log_path=log_path):
        ok = tool.run()

    # Expected location first.
    final_sto = sto_path

    # Fallback: OpenSim sometimes writes a different STO name into the results dir.
    if not final_sto.exists():
        candidates = sorted(output_dir.glob("*.sto"))
        if len(candidates) == 1:
            final_sto = candidates[0]
        elif len(candidates) > 1:
            preferred = [p for p in candidates if prefix in p.stem]
            if len(preferred) == 1:
                final_sto = preferred[0]
            else:
                raise FileNotFoundError(
                    f"InverseDynamicsTool ran but expected output was not found: {sto_path}. "
                    f"Found multiple .sto files instead: {[str(p) for p in candidates]}"
                )
        else:
            raise FileNotFoundError(
                f"InverseDynamicsTool ran but expected output was not found: {sto_path}. "
                f"No .sto files were found in {output_dir}."
            )

    return StorageResult(
        path=final_sto,
        dataframe=read_storage(final_sto),
        metadata={
            "setup_xml_path": str(setup_xml_path),
            "external_loads_xml_path": None if external_xml is None else str(external_xml),
            "external_loads_mot_path": None if external_mot is None else str(external_mot),
            "external_loads_validation": external_loads_validation,
            "run_return": ok,
            "coordinate_preflight": coordinate_preflight,
            "log_path": str(log_path),
            "quiet": bool(config.quiet),
        },
    )

def _read_storage_time_vector(storage_path: str | Path) -> np.ndarray:
    storage_path = Path(storage_path)
    df = read_storage(storage_path)
    time_col = "time" if "time" in df.columns else ("Time" if "Time" in df.columns else None)
    if time_col is None:
        raise ValueError(f"Could not find time column in storage file: {storage_path}")

    time = pd.to_numeric(df[time_col], errors="coerce").dropna().to_numpy(dtype=float)
    if len(time) < 2:
        raise ValueError(f"Storage file must contain at least 2 time samples: {storage_path}")

    return time


def _resample_load_df_to_time(df: pd.DataFrame, time_vector: np.ndarray) -> pd.DataFrame:
    df = df.sort_values("time").reset_index(drop=True)
    out = pd.DataFrame({"time": time_vector})

    src_t = pd.to_numeric(df["time"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(src_t)
    src_t = src_t[valid]

    if len(src_t) < 2:
        raise ValueError("External load data must contain at least two valid time samples.")

    active_start = float(src_t[0])
    active_end = float(src_t[-1])

    for col in df.columns:
        if col == "time":
            continue

        src_y = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)[valid]
        finite_y = np.isfinite(src_y)
        if finite_y.sum() >= 2:
            interp_t = src_t[finite_y]
            interp_y = src_y[finite_y]
        elif finite_y.sum() == 1:
            interp_t = np.array([src_t[0], src_t[-1]], dtype=float)
            interp_y = np.array([src_y[finite_y][0], src_y[finite_y][0]], dtype=float)
        else:
            out[col] = 0.0
            continue

        y = np.interp(time_vector, interp_t, interp_y, left=0.0, right=0.0)

        # Make the behavior explicit: outside the provided load window, use zero.
        outside = (time_vector < active_start) | (time_vector > active_end)
        y[outside] = 0.0

        out[col] = y

    return out
