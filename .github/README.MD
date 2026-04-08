# MonoMech

**MonoMech** is a Python library for **monocular biomechanics** and **marker-based biomechanics**.

It is designed for researchers, clinicians, and biomechanists who want a practical workflow that goes from:

- **video → 2D pose → 3D pose → TRC → OpenSim scale / IK / ID**
- or from:
- **marker TRC → cleaning → OpenSim scale / IK / ID**

MonoMech is built to be:

- **easy to use in notebooks**
- **clear and explicit about file outputs**
- **flexible enough for both pose-based and mocap-based workflows**
- **organized around real biomechanics deliverables**

---

## What MonoMech does

### Monocular pipeline
- Load one or many videos
- Run 2D pose estimation
- Run 3D world pose estimation
- Estimate 3D global pose
- Export wide CSV outputs
- Export OpenSim-compatible TRC files
- Run OpenSim scaling
- Run inverse kinematics (IK)
- Run inverse dynamics (ID)
- Add manual or estimated external loads

### Marker / mocap pipeline
- Load marker-based TRC files
- Smooth and gap-fill markers
- Export cleaned TRCs
- Run OpenSim scaling
- Run inverse kinematics (IK)
- Run inverse dynamics (ID)

### Visualization
- Plot 2D pose on video frames
- Plot 3D pose frames
- Plot marker frames
- Plot IK joint coordinates
- Plot ID forces and moments

---

## Installation

### Recommended pip install

```bash
pip install monomech
