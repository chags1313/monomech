<section class="mono-hero" markdown>

# monomech

Notebook-first biomechanics for single-camera video, marker data, OpenSim-ready files, and analysis tables you can inspect at every step.

<div class="mono-badges" markdown>
<span class="mono-badge">Python 3.10-3.12</span>
<span class="mono-badge">Video to pose to TRC</span>
<span class="mono-badge">Marker cleanup</span>
<span class="mono-badge">OpenSim workflows</span>
</div>

</section>

`monomech` is built for researchers, students, and developers who want a clear path from raw motion data to reproducible biomechanical artifacts. The library keeps the workflow modular, so you can inspect each result before moving to the next stage.

## Choose Your Path

<div class="grid cards" markdown>

-   **Video first**

    Start with a single camera video, estimate pose, export CSV/TRC, and continue into OpenSim when the marker mapping is ready.

    [:octicons-arrow-right-24: Start the guide](getting-started.md#video-first-workflow)

-   **Marker first**

    Load an existing TRC file, summarize markers, fill gaps, smooth trajectories, and export a cleaned TRC.

    [:octicons-arrow-right-24: Clean marker data](getting-started.md#marker-first-workflow)

-   **OpenSim ready**

    Use bundled model paths, scale a model, run inverse kinematics, and add inverse dynamics when external loads are available.

    [:octicons-arrow-right-24: OpenSim stage](stages/opensim.md)

-   **Learn by notebook**

    Open the example notebooks and run one small section at a time with your own video or TRC path.

    [:octicons-arrow-right-24: Example notebooks](examples.md)

</div>

## The Workflow

<div class="mono-path" markdown>
<div class="mono-step" markdown>
**Install only what you need**

Base installs import without native video or OpenSim packages. Add extras when a workflow needs them.
</div>
<div class="mono-step" markdown>
**Load a trial**

Use `mm.load_video()` for video workflows or `mm.load_trc()` for marker workflows.
</div>
<div class="mono-step" markdown>
**Inspect intermediate results**

Convert result objects to DataFrames, summaries, CSV files, or TRC files before downstream analysis.
</div>
<div class="mono-step" markdown>
**Move into OpenSim**

Use trial methods for scale, inverse kinematics, and inverse dynamics after checking the marker data.
</div>
</div>

## Quick Start

```python
import monomech as mm

trial = mm.load_video("subject01.mp4")

pose2d = trial.estimate_pose2d()
pose3d_world = trial.estimate_pose3d_world()
pose3d_global = trial.estimate_pose3d_global()

pose3d_global.to_csv("outputs/subject01_global.csv")
pose3d_global.to_trc("outputs/subject01_global.trc")
```

For marker-first work:

```python
import monomech as mm

trial = mm.load_trc("walk.trc")
print(trial.summary())

trial.clean_markers(cutoff_hz=6.0)
trial.to_trc("outputs/walk_clean.trc")
```

## Install

=== "Base"

    ```bash
    python -m pip install monomech
    ```

=== "Video pose"

    ```bash
    python -m pip install "monomech[pose]"
    ```

=== "OpenSim bindings"

    ```bash
    python -m pip install "monomech[opensim]"
    ```

=== "Everything"

    ```bash
    python -m pip install "monomech[all]"
    ```

<div class="mono-callout" markdown>
Base installation is intentionally lightweight. If `import monomech` fails after install, upgrade to `0.15.1` or newer so optional native dependencies are not required at import time.
</div>

## Where To Go Next

<div class="grid cards" markdown>

-   :material-run-fast: **First complete run**

    [Getting started](getting-started.md) walks through installation, verification, exports, and troubleshooting.

-   :material-notebook-outline: **Notebook examples**

    [Examples](examples.md) links to ready-to-edit notebooks for video, marker cleanup, and OpenSim setup.

-   :material-folder-table-outline: **Outputs**

    [Outputs and files](outputs.md) explains CSV, TRC, MOT, STO, model, and package artifacts.

-   :material-source-branch: **Modular stages**

    [Stage guides](stages/index.md) explain each processing step separately.

</div>
