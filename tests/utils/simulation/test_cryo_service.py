# test_cryo_service.py
import asyncio
from unittest.mock import Mock, AsyncMock

import pytest

from sc_linac_physics.utils.simulation.cryo_service import (
    HeaterPVGroup,
    JTPVGroup,
    LiquidLevelPVGroup,
    CryomodulePVGroup,
)


@pytest.fixture
def mock_cm_group():
    """Create a mock CryomodulePVGroup"""
    cm_group = Mock(spec=CryomodulePVGroup)
    cm_group.total_power = 0.0
    cm_group.ll_group = Mock(spec=LiquidLevelPVGroup)
    cm_group.ll_group.downstream = Mock()
    cm_group.ll_group.downstream.value = 93.0
    cm_group.ll_group.downstream.write = AsyncMock()
    cm_group.ll_group.min_ll = 0
    cm_group.ll_group.max_ll = 100
    cm_group.heater = Mock()  # Add heater attribute for JTPVGroup
    return cm_group


@pytest.fixture
async def heater_group(mock_cm_group):
    """Create HeaterPVGroup instance"""
    heater = HeaterPVGroup("TEST:HEATER:", mock_cm_group)
    heater.async_lib = Mock()
    heater.async_lib.library = asyncio
    await heater.readback.write(0.0)
    await heater.mode.write(2)  # Start in SEQUENCER mode
    return heater


@pytest.fixture
async def jt_group(mock_cm_group):
    """Create JTPVGroup instance"""
    jt = JTPVGroup("TEST:JT:", mock_cm_group)
    jt.async_lib = Mock()
    jt.async_lib.library = asyncio
    # Override heater_group after initialization
    jt.heater_group = Mock(spec=HeaterPVGroup)
    jt.heater_group.net_heat = 0.0
    jt.heater_group.ll_delta = 0.0
    return jt


class TestHeaterPVGroup:
    """Tests for HeaterPVGroup"""

    @pytest.mark.asyncio
    async def test_heat_calculations(self, heater_group, mock_cm_group):
        """Test heat calculations"""
        mock_cm_group.total_power = 100.0
        await heater_group.readback.write(50.0)

        # Total heat
        assert heater_group.total_heat == 150.0

        # Net heat in SEQUENCER mode = 0
        await heater_group.mode.write(2)
        assert heater_group.net_heat == 0.0

        # Net heat in MANUAL mode
        await heater_group.mode.write(0)
        assert heater_group.net_heat == 102.0  # (100+50) - 48

        # LL delta calculation
        expected_delta = -8.174374050765241e-05 * 102.0
        assert abs(heater_group.ll_delta - expected_delta) < 1e-10

    @pytest.mark.asyncio
    async def test_mode_switching(self, heater_group):
        """Test switching between MANUAL and SEQUENCER modes"""
        # Switch to MANUAL
        await heater_group.manual.write(1)
        assert heater_group.mode.value == 0
        assert heater_group.mode_string.value == "MANUAL"
        assert heater_group.sequencer.value == 0

        # Switch to SEQUENCER
        await heater_group.sequencer.write(1)
        assert heater_group.mode.value == 2
        assert heater_group.mode_string.value == "SEQUENCER"
        assert heater_group.manual.value == 0

    @pytest.mark.asyncio
    async def test_manual_mode_updates_ll(self, heater_group, mock_cm_group):
        """Test manual mode updates liquid level based on heat"""
        await heater_group.mode.write(0)
        heater_group.cm_group.total_power = 100.0
        await heater_group.readback.write(0.0)
        mock_cm_group.ll_group.downstream.value = 50.0

        # Run manual mode briefly
        task = asyncio.create_task(heater_group.manual_mode_start())
        await asyncio.sleep(2.5)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have updated LL at least twice
        assert mock_cm_group.ll_group.downstream.write.call_count >= 2


class TestJTPVGroup:
    """Tests for JTPVGroup"""

    @pytest.mark.asyncio
    async def test_mode_switching(self, jt_group):
        """Test switching between AUTO and MANUAL modes"""
        # Switch to MANUAL
        await jt_group.manual.write(1)
        assert jt_group.mode.value == 0
        assert jt_group.mode_string.value == "MANUAL"
        assert jt_group.auto.value == 0

        # Switch to AUTO
        await jt_group.auto.write(1)
        assert jt_group.mode.value == 1
        assert jt_group.mode_string.value == "AUTO"
        assert jt_group.manual.value == 0

    @pytest.mark.asyncio
    async def test_auto_feedback(self, jt_group, mock_cm_group):
        """Test AUTO mode feedback toward setpoint"""
        await jt_group.mode.write(1)
        await jt_group.ds_setpoint.write(95.0)
        mock_cm_group.ll_group.downstream.value = 85.0

        # Run auto feedback
        task = asyncio.create_task(jt_group.auto_feedback_start())
        await asyncio.sleep(2)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have moved toward setpoint
        calls = mock_cm_group.ll_group.downstream.write.call_args_list
        if len(calls) > 1:
            final_value = calls[-1][0][0]
            assert final_value > 85.0  # Moving up toward 95
            assert final_value <= 95.0  # Not overshooting

    @pytest.mark.asyncio
    async def test_manual_mode_jt_effects(self, jt_group, mock_cm_group):
        """Test MANUAL mode JT position effects on LL"""
        await jt_group.mode.write(0)
        jt_group.heater_group.net_heat = 0.0
        mock_cm_group.ll_group.downstream.value = 50.0

        # Test JT above stable (should increase LL)
        await jt_group.readback.write(50.0)  # Above stable_jt_pos (40.0)

        task = asyncio.create_task(jt_group.manual_mode_start())
        await asyncio.sleep(2)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Level should increase
        if mock_cm_group.ll_group.downstream.write.call_count > 0:
            final_value = (
                mock_cm_group.ll_group.downstream.write.call_args_list[-1][0][0]
            )
            assert final_value > 50.0

    @pytest.mark.asyncio
    async def test_manual_position_updates(self, jt_group):
        """Test manual position updates readback"""
        await jt_group.mode.write(0)  # MANUAL
        await jt_group.manual_pos.write(55.0)
        assert jt_group.readback.value == 55.0


class TestLiquidLevelPVGroup:
    """Tests for LiquidLevelPVGroup"""

    @pytest.mark.asyncio
    async def test_initialization_and_updates(self):
        """Test initialization and value updates"""
        ll = LiquidLevelPVGroup("TEST:LL:")

        assert ll.upstream.value == 75.0
        assert ll.downstream.value == 93.0
        assert ll.max_ll == 100
        assert ll.min_ll == 0

        await ll.upstream.write(80.0)
        await ll.downstream.write(95.0)

        assert ll.upstream.value == 80.0
        assert ll.downstream.value == 95.0


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_heater_jt_interaction(self, mock_cm_group):
        """Test heater and JT valve interaction in manual mode"""
        heater = HeaterPVGroup("TEST:HEATER:", mock_cm_group)
        heater.async_lib = Mock()
        heater.async_lib.library = asyncio

        jt = JTPVGroup("TEST:JT:", mock_cm_group)
        jt.async_lib = Mock()
        jt.async_lib.library = asyncio
        jt.heater_group = heater

        # Both in manual mode
        await heater.mode.write(0)
        await jt.mode.write(0)

        # High heat (decreases LL) and high JT (increases LL)
        mock_cm_group.total_power = 100.0
        await heater.readback.write(30.0)
        await jt.readback.write(50.0)
        mock_cm_group.ll_group.downstream.value = 50.0

        # Run JT manual mode
        task = asyncio.create_task(jt.manual_mode_start())
        await asyncio.sleep(2)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have made updates considering both effects
        assert mock_cm_group.ll_group.downstream.write.call_count > 0

    @pytest.mark.asyncio
    async def test_boundary_conditions(self, jt_group, mock_cm_group):
        """Test liquid level respects boundaries"""
        await jt_group.mode.write(1)  # AUTO
        await jt_group.ds_setpoint.write(105.0)  # Above max
        mock_cm_group.ll_group.downstream.value = 98.0

        task = asyncio.create_task(jt_group.auto_feedback_start())
        await asyncio.sleep(2)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should not exceed max
        calls = mock_cm_group.ll_group.downstream.write.call_args_list
        for call in calls:
            assert call[0][0] <= 100


class TestEdgeCases:
    """Edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_zero_net_heat(self, heater_group):
        """Test zero net heat condition"""
        await heater_group.mode.write(0)
        heater_group.cm_group.total_power = 48.0  # Exactly stable
        await heater_group.readback.write(0.0)

        assert heater_group.net_heat == 0.0
        assert abs(heater_group.ll_delta) < 1e-10

    @pytest.mark.asyncio
    async def test_negative_net_heat(self, heater_group):
        """Test negative net heat (cooling)"""
        await heater_group.mode.write(0)
        heater_group.cm_group.total_power = 0.0
        await heater_group.readback.write(20.0)

        assert heater_group.net_heat == -28.0
        assert heater_group.ll_delta > 0  # Level rises when cooling

    @pytest.mark.asyncio
    async def test_rapid_mode_switching(self, jt_group):
        """Test rapid mode changes"""
        await jt_group.auto.write(1)
        await jt_group.manual.write(1)
        await jt_group.auto.write(1)
        await jt_group.manual.write(1)

        # Should end in manual mode
        assert jt_group.mode.value == 0
        assert jt_group.manual.value == 1
