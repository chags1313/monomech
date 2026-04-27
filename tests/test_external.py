import monomech as mm
from monomech.external import ExternalLoadsSpec


def test_carried_load_accepts_applied_to_body_alias():
    load = mm.external.carried_load(
        mass_kg=12.5,
        applied_to_body="radius_r",
        point=(0.0, -0.2, 0.0),
        start_time=0.0,
        end_time=2.0,
        name="right_dumbbell",
    )

    assert isinstance(load, ExternalLoadsSpec)
    assert load.applied_to_body == "radius_r"
    assert load.point_expressed_in == "radius_r"
    assert load.force_columns == ("Fx", "Fy", "Fz")
    assert load.data["Fy"].iloc[0] == -12.5 * 9.81
    assert load.data["Py"].iloc[0] == -0.2


def test_with_estimated_grf_composes_pipeline_loads():
    dumbbell = mm.external.carried_load(
        mass_kg=5.0,
        body="radius_r",
        start_time=0.0,
        end_time=1.0,
    )

    loads = mm.external.with_estimated_grf(dumbbell)

    assert loads[0] == "estimate"
    assert loads[1] is dumbbell
