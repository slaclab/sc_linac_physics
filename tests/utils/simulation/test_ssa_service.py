from unittest.mock import AsyncMock, Mock, patch

import pytest

from sc_linac_physics.utils.simulation.ssa_service import SSAPVGroup


@pytest.fixture
def ssa():
    group = SSAPVGroup("TEST:SSA:", cavityGroup=Mock())
    group.log = Mock()
    return group


class TestCalibration:
    @pytest.mark.asyncio
    async def test_start_sets_running_returns_zero_and_schedules_run(self, ssa):
        with patch.object(
            ssa, "_finish_calibration", new_callable=AsyncMock
        ) as finish:
            result = await ssa.cal_start.putter(None, 1)
            await ssa._calibration_task

        assert result == 0
        assert ssa.cal_status.value == "Running"
        finish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_ignored_while_running(self, ssa):
        running = Mock()
        running.done.return_value = False
        ssa._calibration_task = running

        result = await ssa.cal_start.putter(None, 1)

        assert result == 0
        assert ssa._calibration_task is running
        ssa.log.warning.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "roll, expected", [(0.9, "Success"), (0.1, "Crash")]
    )
    async def test_results_written_before_complete(self, ssa, roll, expected):
        """A client that sees CALSTS Complete must read this run's results."""
        seen_at_complete = {}
        real_write = ssa.cal_status.write

        async def record_then_write(value, *args, **kwargs):
            if value == "Complete":
                seen_at_complete.update(
                    slope=ssa.slope_new.value, cal_stat=ssa.cal_stat.value
                )
            return await real_write(value, *args, **kwargs)

        with (
            patch(
                "sc_linac_physics.utils.simulation.ssa_service.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "sc_linac_physics.utils.simulation.ssa_service.uniform",
                return_value=1.23,
            ),
            patch(
                "sc_linac_physics.utils.simulation.ssa_service.random",
                return_value=roll,
            ),
            patch.object(
                ssa.cal_status, "write", side_effect=record_then_write
            ),
        ):
            await ssa._finish_calibration()

        assert ssa.cal_status.value == "Complete"
        assert seen_at_complete == {"slope": 1.23, "cal_stat": expected}


@pytest.mark.asyncio
async def test_concurrent_starts_schedule_one_calibration(ssa):
    """Two CALSTRT puts at once: the status write yields between them."""
    import asyncio

    release = asyncio.Event()

    async def slow_finish():
        await release.wait()

    real_write = ssa.cal_status.write

    async def yielding_write(*args, **kwargs):
        # With subscribed clients, caproto's write yields while publishing.
        await asyncio.sleep(0)
        return await real_write(*args, **kwargs)

    with (
        patch.object(ssa, "_finish_calibration", side_effect=slow_finish) as f,
        patch.object(ssa.cal_status, "write", side_effect=yielding_write),
    ):
        await asyncio.gather(
            ssa.cal_start.putter(None, 1), ssa.cal_start.putter(None, 1)
        )
        release.set()
        await ssa._calibration_task
    assert f.call_count == 1
