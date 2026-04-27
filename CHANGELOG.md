# Changelog

## Unreleased

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
