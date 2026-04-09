from datetime import datetime
from unittest.mock import Mock

from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_data_fetcher import (
    CavityFaultResult,
    FaultDataFetcher,
)

from tests.displays.cavity_display.frontend.heatmap.conftest import (
    make_machine,
    make_result,
)


class TestCavityFaultResult:
    def test_successful_result_counts(self):
        result = make_result(alarm=5, warning=2, invalid=1, ok=100)
        assert result.alarm_count == 5
        assert result.warning_count == 2
        assert result.invalid_count == 1
        assert result.ok_count == 100

    def test_error_result(self):
        result = CavityFaultResult(
            cm_name="01", cavity_num=1, error="Connection timeout"
        )
        assert result.is_error is True
        assert result.error == "Connection timeout"

    def test_is_error_false_when_no_error(self):
        result = make_result()
        assert result.is_error is False

    def test_empty_fault_counts_all_zeros(self):
        result = CavityFaultResult(
            cm_name="01", cavity_num=1, fault_counts_by_tlc={}
        )
        assert result.alarm_count == 0
        assert result.warning_count == 0
        assert result.invalid_count == 0
        assert result.ok_count == 0

    def test_none_fault_counts_all_zeros(self):
        result = CavityFaultResult(cm_name="01", cavity_num=1)
        assert result.alarm_count == 0
        assert result.warning_count == 0

    def test_multiple_tlcs_sum_correctly(self):
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={
                "BCS": FaultCounter(5, 100, 1, 2),
                "SSA": FaultCounter(3, 50, 2, 4),
            },
        )
        assert result.alarm_count == 8
        assert result.warning_count == 6
        assert result.invalid_count == 3
        assert result.ok_count == 150

    def test_to_fault_counter(self):
        result = make_result(alarm=5, warning=2, invalid=1, ok=100)
        counter = result.to_fault_counter()
        assert isinstance(counter, FaultCounter)
        assert counter.alarm_count == 5
        assert counter.warning_count == 2
        assert counter.invalid_count == 1
        assert counter.ok_count == 100


# -- FaultDataFetcher tests --


class TestFaultDataFetcherSignals:
    def test_progress_emitted_for_each_cavity(self):
        machine = make_machine(num_cavities=3)
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())

        spy = Mock()
        fetcher.progress.connect(spy)
        fetcher.run()

        assert spy.call_count == 3
        spy.assert_any_call(1, 3)
        spy.assert_any_call(2, 3)
        spy.assert_any_call(3, 3)

    def test_cavity_result_emitted_for_each(self):
        machine = make_machine(num_cavities=3)
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())

        spy = Mock()
        fetcher.cavity_result.connect(spy)
        fetcher.run()

        assert spy.call_count == 3

    def test_finished_all_emitted_once(self):
        machine = make_machine(num_cavities=3)
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())

        spy = Mock()
        fetcher.finished_all.connect(spy)
        fetcher.run()

        spy.assert_called_once()
        results = spy.call_args[0][0]
        assert len(results) == 3

    def test_fetch_error_on_enumeration_failure(self):
        machine = Mock()
        machine.linacs = Mock(side_effect=RuntimeError("Bad machine"))

        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        spy = Mock()
        fetcher.fetch_error.connect(spy)
        fetcher.run()

        spy.assert_called_once()
        assert "Failed to enumerate" in spy.call_args[0][0]

    def test_fetch_error_on_empty_machine(self):
        machine = Mock()
        linac = Mock()
        linac.cryomodules = {}
        machine.linacs = [linac]

        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        spy = Mock()
        fetcher.fetch_error.connect(spy)
        fetcher.run()

        spy.assert_called_once()
        assert "No cavities found" in spy.call_args[0][0]


class TestFaultDataFetcherAbort:
    def test_is_abort_requested_initially_false(self):
        machine = make_machine()
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        assert fetcher.is_abort_requested is False

    def test_abort_sets_flag(self):
        machine = make_machine()
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        fetcher.abort()
        assert fetcher.is_abort_requested is True

    def test_abort_stops_iteration(self):
        machine = make_machine(num_cavities=5)
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())

        call_count = 0

        def abort_after_two(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                fetcher.abort()
            return {"BCS": FaultCounter(1, 10, 0, 0)}

        for cav in machine.linacs[0].cryomodules["01"].cavities.values():
            cav.get_fault_counts = abort_after_two

        result_spy = Mock()
        finished_spy = Mock()
        fetcher.cavity_result.connect(result_spy)
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        assert 1 <= result_spy.call_count < 5
        finished_spy.assert_called_once()


class TestFaultDataFetcherErrors:
    def test_single_cavity_exception_continues(self):
        machine = make_machine(num_cavities=3)
        cavities = machine.linacs[0].cryomodules["01"].cavities
        cavities[2].get_fault_counts = Mock(
            side_effect=RuntimeError("PV timeout")
        )

        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        finished_spy = Mock()
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        finished_spy.assert_called_once()
        results = finished_spy.call_args[0][0]
        assert len(results) == 3

        error_results = [r for r in results if r.is_error]
        ok_results = [r for r in results if not r.is_error]
        assert len(error_results) == 1
        assert len(ok_results) == 2
        assert "PV timeout" in error_results[0].error


class TestFaultDataFetcherFilter:
    def test_no_filter_fetches_all(self):
        machine = make_machine(num_cavities=3)
        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        finished_spy = Mock()
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        results = finished_spy.call_args[0][0]
        assert len(results) == 3

    def test_filter_limits_cavities(self):
        machine = make_machine(num_cavities=5)
        cavity_filter = {("01", 1), ("01", 3)}
        fetcher = FaultDataFetcher(
            machine,
            datetime.now(),
            datetime.now(),
            cavity_filter=cavity_filter,
        )
        finished_spy = Mock()
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        results = finished_spy.call_args[0][0]
        assert len(results) == 2
        result_keys = {(r.cm_name, r.cavity_num) for r in results}
        assert result_keys == {("01", 1), ("01", 3)}

    def test_filter_with_nonexistent_cavity(self):
        machine = make_machine(num_cavities=3)
        cavity_filter = {("01", 99)}
        fetcher = FaultDataFetcher(
            machine,
            datetime.now(),
            datetime.now(),
            cavity_filter=cavity_filter,
        )
        spy = Mock()
        fetcher.fetch_error.connect(spy)
        fetcher.run()

        spy.assert_called_once()
        assert "No cavities found" in spy.call_args[0][0]

    def test_progress_reflects_filtered_total(self):
        machine = make_machine(num_cavities=5)
        cavity_filter = {("01", 2), ("01", 4)}
        fetcher = FaultDataFetcher(
            machine,
            datetime.now(),
            datetime.now(),
            cavity_filter=cavity_filter,
        )
        progress_spy = Mock()
        fetcher.progress.connect(progress_spy)
        fetcher.run()

        assert progress_spy.call_count == 2
        progress_spy.assert_any_call(1, 2)
        progress_spy.assert_any_call(2, 2)


class TestFaultDataFetcherParallel:
    def test_parallel_fetch_all_results_collected(self):
        machine = make_machine(num_cavities=8)
        for cav in machine.linacs[0].cryomodules["01"].cavities.values():
            cav.get_fault_counts = Mock(
                return_value={"BCS": FaultCounter(1, 10, 0, 0)}
            )

        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        finished_spy = Mock()
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        finished_spy.assert_called_once()
        results = finished_spy.call_args[0][0]
        assert len(results) == 8

    def test_parallel_mixed_errors_and_successes(self):
        machine = make_machine(num_cavities=4)
        cavities = machine.linacs[0].cryomodules["01"].cavities
        cavities[1].get_fault_counts = Mock(
            return_value={"BCS": FaultCounter(1, 10, 0, 0)}
        )
        cavities[2].get_fault_counts = Mock(
            side_effect=RuntimeError("PV timeout")
        )
        cavities[3].get_fault_counts = Mock(
            return_value={"SSA": FaultCounter(2, 5, 0, 0)}
        )
        cavities[4].get_fault_counts = Mock(
            side_effect=RuntimeError("Connection refused")
        )

        fetcher = FaultDataFetcher(machine, datetime.now(), datetime.now())
        finished_spy = Mock()
        fetcher.finished_all.connect(finished_spy)
        fetcher.run()

        results = finished_spy.call_args[0][0]
        assert len(results) == 4
        error_results = [r for r in results if r.is_error]
        ok_results = [r for r in results if not r.is_error]
        assert len(error_results) == 2
        assert len(ok_results) == 2
