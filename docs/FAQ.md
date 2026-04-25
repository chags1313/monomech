# FAQ

## Why does a base install not include MediaPipe or OpenSim?

MediaPipe, OpenCV, and OpenSim-compatible bindings are native dependencies. They can be platform-sensitive, so `monomech` keeps the base install importable and lets users opt into those stacks when needed.

Use:

```bash
python -m pip install "monomech[pose]"
python -m pip install "monomech[opensim]"
python -m pip install "monomech[all]"
```

## Which Python versions are supported?

`monomech` supports Python 3.10, 3.11, and 3.12.

## How do I verify my install?

```bash
python -c "import monomech as mm; print(mm.list_builtin_osim_models())"
```

For video pose support:

```bash
python -c "import mediapipe, cv2; print('pose stack ready')"
```

For OpenSim support:

```bash
python -c "import monomech.opensim_runtime as rt; print(rt.require_opensim())"
```

## Where do built-in models live?

Use `get_builtin_osim_model()` instead of hard-coding package paths:

```python
import monomech as mm

model_path = mm.get_builtin_osim_model("pose")
```

This returns a stable filesystem path that works whether the package is installed from a wheel, source tree, or zip-style environment.

## Why does OpenSim fail even though monomech imports?

OpenSim is only needed when you call OpenSim methods. A base `import monomech` does not prove that OpenSim is installed or configured.

Install an OpenSim-compatible binding and then call the OpenSim methods again.

## How is PyPI publishing configured?

GitHub Actions publishes only from version tags such as `v0.15.1`. The PyPI project must also configure Trusted Publishing for:

- repository: `chags1313/monomech`
- workflow: `publish.yml`
- environment: blank, unless the workflow uses an environment
