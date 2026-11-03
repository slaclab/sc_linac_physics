import pytest

from sc_linac_physics.utils.sc_linac import tuner_response
from sc_linac_physics.utils.sc_linac.tuner_response import TunerResponse

HL_PREFIXES = [f"ACCL:L1B:H{cm}{cav}0:" for cm in (1, 2) for cav in range(1, 9)]


@pytest.fixture
def curve():
    # 0.1 Hz/microstep from -300 to -200 kHz, then 0.05 Hz/microstep to 0.
    return TunerResponse(
        [-300_000, -200_000, 0],
        [0, 1_000_000, 5_000_000],
        [True, False, True],
    )


class TestPackagedCurves:
    def test_every_hl_cavity_has_a_curve(self):
        for prefix in HL_PREFIXES:
            assert TunerResponse.for_cavity(prefix) is not None, prefix

    def test_no_curve_for_a_1p3_ghz_cavity(self):
        assert TunerResponse.for_cavity("ACCL:L0B:0110:") is None

    def test_curves_reach_resonance(self):
        for prefix in HL_PREFIXES:
            response = TunerResponse.for_cavity(prefix)
            assert response.detune_hz[0] < -500_000 < 0 < response.detune_hz[-1]

    def test_takes_a_cavity_object(self):
        class FakeCavity:
            pv_prefix = "ACCL:L1B:H110:"

        assert TunerResponse.for_cavity(FakeCavity()) is (
            TunerResponse.for_cavity("ACCL:L1B:H110:")
        )

    def test_loaded_once(self):
        tuner_response._load_curves.cache_clear()
        TunerResponse.for_cavity("ACCL:L1B:H110:")
        TunerResponse.for_cavity("ACCL:L1B:H120:")
        assert tuner_response._load_curves.cache_info().misses == 1


class TestTunerResponse:
    def test_position_interpolates(self, curve):
        assert curve.position(-250_000) == pytest.approx(500_000)
        assert curve.position(-100_000) == pytest.approx(3_000_000)

    def test_position_extends_end_slopes(self, curve):
        assert curve.position(-310_000) == pytest.approx(-100_000)
        assert curve.position(10_000) == pytest.approx(5_200_000)

    def test_steps_between_is_signed(self, curve):
        assert curve.steps_between(-300_000, 0) == pytest.approx(5_000_000)
        assert curve.steps_between(0, -300_000) == pytest.approx(-5_000_000)

    def test_hz_per_microstep_is_local(self, curve):
        assert curve.hz_per_microstep(-250_000) == pytest.approx(0.1)
        assert curve.hz_per_microstep(-50_000) == pytest.approx(0.05)
        assert curve.hz_per_microstep(-400_000) == pytest.approx(0.1)

    def test_covered(self, curve):
        assert curve.covered(-300_000, -300_000)
        assert not curve.covered(-300_000, 0)
        assert not curve.covered(-310_000, -300_000)

    def test_rejects_a_curve_that_does_not_rise(self):
        with pytest.raises(ValueError):
            TunerResponse([0, 1, 2], [0, 5, 5], [True] * 3)

    def test_sorts_by_detune(self):
        curve = TunerResponse([0, -100], [10, 0], [True, True])
        assert curve.position(-50) == pytest.approx(5)
