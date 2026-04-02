import monomech as mm

trial = mm.Trial.from_video("example.mp4")

pose2d = mm.pose2d.process(trial)
world3d = mm.world3d.process(trial, pose2d=pose2d)
pnp = mm.pnp.solve(trial, pose2d=pose2d, world3d=world3d)
global_pose = mm.global_pose.estimate(trial, pose2d=pose2d, world3d=world3d, pnp=pnp)

force_set = mm.ForceSet([
    mm.ExternalForce.constant(
        name="right_grf",
        target="right_foot",
        magnitude=850.0,
        direction=(0.0, 1.0, 0.0),
        point="right_ankle",
    )
])
forces = mm.forces.build(trial, global_pose=global_pose, force_set=force_set)

print("Pose2D tables:", pose2d.tables.keys())
print("World3D tables:", world3d.tables.keys())
print("PnP tables:", pnp.tables.keys())
print("Global pose tables:", global_pose.tables.keys())
print("Force tables:", forces.tables.keys())

pipeline = mm.FullPipeline()
run = pipeline.run("example.mp4", output_dir="outputs/example")
print("Wrapper stages:", run.available_stages())
