# Pose2D

The 2D pose stage reads a video and estimates image-space landmarks.

```python
import monomech as mm

trial = mm.load_video("subject01.mp4")
pose2d = trial.estimate_pose2d()
```

Most users can start with the combined pose helper:

```python
pose = mm.estimate_pose("subject01.mp4")
```

## Requirements

Install the pose extra:

```bash
python -m pip install "monomech[pose]"
```

This installs MediaPipe and OpenCV support.

## Configuration

```python
pose2d = trial.estimate_pose2d(
    fps=30,
    stride=1,
    smooth=True,
)
```

Use `Pose2DConfig` for a reusable configuration object:

```python
config = mm.Pose2DConfig(stride=2, sample_fps=15)
pose2d = trial.estimate_pose2d(config=config)
```

## Outputs

The returned `Pose2DResult` can be exported or converted to tables:

```python
pose2d.to_csv("outputs/subject01_pose2d.csv")
df = pose2d.to_wide_df()
```
