# Changelog

## Unreleased

## 0.15.19

### Added
- added `create_glb_viewer()` for a tiny notebook-friendly HTML shell that path-loads an existing GLB

### Changed
- made `save_animation_viewer()` reference the GLB path by default instead of embedding the whole binary in the HTML

## 0.15.18

### Fixed
- made the fast no-GLB visualizer auto-stride OpenSim marker extraction before evaluation instead of extracting every IK frame and only downsampling afterward

## 0.15.17

### Added
- added `animate(render="fast")` and `fast_viewer()` for a no-GLB notebook visualizer
- added `save_opensim_fast_visualizer()` for HTML-only IK/ID review with OpenSim body proxy meshes
- added `save_opensim_glb()` as an explicit GLB-only export alias

### Changed
- the IK/ID visualizer now renders fast OpenSim body proxies when no GLB is provided, while uploaded or exported GLBs still provide full anatomical surface meshes

## 0.15.16

### Fixed
- made carried-load and body-local external-force arrows display at the moving OpenSim body instead of the ground origin
- embedded external-load frame metadata in the visualizer payload so displayed force arrows match the OpenSim `ExternalLoads.xml` body and frame definitions

## 0.15.15

### Changed
- made notebook visualizer display use Jupyter's file-serving route by default for faster GLB loading
- kept `viewer.show(inline_glb=True)` as an explicit fallback for notebook environments that cannot serve local files

## 0.15.14

### Fixed
- made notebook visualizer display inject the GLB as an in-memory browser blob instead of relying on notebook local-file fetches

## 0.15.13

### Changed
- made convenience carried and constant loads apply for the full IK trial by default

### Fixed
- expanded full-trial loads to the actual IK time vector when writing OpenSim external-load MOT files
- added OpenSim body-name validation before inverse dynamics writes external-load XML

## 0.15.12

### Added
- added source-frame overlays to `vis_2d()` and a mid-hip to mid-shoulder trunk connection in 2D and 3D previews
- added `animate()` quality presets and direct speed/file-size controls

### Changed
- made `animate()` and the full IK/ID visualizer reference sibling GLB files by default instead of embedding the binary in the HTML
- widened the Three.js visualizer floor for full-body motion review
- recentered docs and README examples around the simplified notebook-first API

## 0.15.11

### Fixed
- made `vis_2d()` and `vis_3d()` use white backgrounds with black skeleton lines and markers by default
- corrected `vis_2d()` orientation and made `vis_3d()` display with model Y as the vertical axis

## 0.15.10

### Added
- added notebook-first workflow helpers: `estimate_pose()`, `smooth()`, `gap_fill()`, `run_scaling()`, `run_ik()`, `run_id()`, `animate()`, `video_pipeline()`, and `marker_pipeline()`
- added `mm.load(...)`, `mm.estimate_grf(...)`, and `mm.external_forces(...)` convenience helpers for external loads
- added `vis_2d()` and `vis_3d()` pose/marker previews plus `StorageResult.plot()` and `StorageResult.to_csv()`

## 0.15.9

### Added
- added `mm.external.with_estimated_grf(...)` to combine estimated ground-reaction forces with carried or measured loads in the video-to-ID pipeline
- added `mm.display_visualizer(...)` plus `result.display()` / `viewer.display()` notebook shortcuts
- allowed `external_forces=["estimate", load]` in `video_to_inverse_dynamics()`

### Changed
- removed the blue model bone overlay from generated and online visualizers
- made `external.carried_load()` accept `applied_to_body=` and an application `point=`

## 0.15.8

### Added
- packaged individual lumbar, thoracic, and cervical spine mesh files for the built-in pose model
- embedded complete IK, inverse-dynamics, marker, and external-force visualizer data in exported GLB files

### Changed
- `get_builtin_osim_model("pose")` now returns the original geometry-bearing OSIM by default

### Fixed
- avoided substituting the generic `hat_spine.vtp` mesh for individual vertebra display geometry when exact spine meshes are available

## 0.15.7

### Added
- packaged default full-body OpenSim geometry and automatic geometry discovery for animation exports
- added `get_builtin_geometry_dir()` for workflows that need the packaged mesh directory

### Fixed
- preferred torso/thoracic attachment for the shared packaged spine mesh

## 0.15.6

### Added
- added production pipeline names: `video_to_trc()`, `trc_to_inverse_dynamics()`, and `video_to_inverse_dynamics()`

### Fixed
- removed duplicate body geometry and repeated shared spine aliases from OpenSim GLB exports

## 0.15.5

### Added
- added one-line `pose_to_trc()`, `markers_to_id()`, and `video_to_id()` pipeline helpers

### Fixed
- resolved common full-body OpenSim geometry filename variants so leg and spine meshes export into GLB animations
- made the GitHub Pages visualizer start empty and wait for user-uploaded GLB files

## 0.15.3

### Added
- added notebook-ready IK/ID visualizer with animated markers, external-force arrows, IK plots, ID plots, and a docs demo

## 0.15.2

### Added
- added OpenSim IK animation export to GLB with optional ID metadata, marker-position output, and an HTML viewer helper

## 0.15.1

### Fixed
- made MediaPipe/OpenCV and OpenSim bindings optional extras so `import monomech` works after a base install on machines without those native dependencies
- added packaged pose/model assets required by the wheel
- removed tracked Python bytecode from the source tree

### Added
- import and packaging regression coverage for optional native dependencies

## 0.15.0

### Added
- single-camera biomechanics package scaffold with video, marker, OpenSim, plotting, and packaged resource helpers

### Added
- expanded GitHub repository documentation
- issue templates and pull request template
- contributor, security, and release guides
- docs index and troubleshooting guide

## 0.4.0
- publish-ready GitHub Actions workflows for CI and PyPI/TestPyPI Trusted Publishing
- notebook-first modular API
- full pipeline wrapper
- GATMA exact-model preset
- CSV companions for OpenSim-native outputs
