# Changelog

## Unreleased

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
