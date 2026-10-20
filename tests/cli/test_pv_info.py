from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics.cli import pv_info

P = "ACCL:L1B:0210:PZT:"

# PUSH_DFGAIN / SAVE_DFGAIN links as ACCL:L1B:0210:PZT served them on
# 2026-10-20 (docs/utils/epics_records.md). DESCs and values are made up.
PUSH_DFGAIN = {
    P + "PUSH_DFGAIN": "0",
    P + "PUSH_DFGAIN.RTYP": "ao",
    P + "PUSH_DFGAIN.DESC": "Push new DF gain",
    P + "PUSH_DFGAIN.DOL": P + "DFGAIN_NEW NPP NMS",
    P + "PUSH_DFGAIN.OMSL": "closed_loop",
    P + "PUSH_DFGAIN.OUT": P + "DFGAIN PP NMS",
    P + "PUSH_DFGAIN.FLNK": "",
    P + "DFGAIN_NEW": "0.85",
    P + "DFGAIN_NEW.RTYP": "ao",
    P + "DFGAIN_NEW.DESC": "A detune gain",
    P + "DFGAIN": "0.8",
    P + "DFGAIN.RTYP": "ao",
    P + "DFGAIN.DESC": "A detune gain",
}


class FakePV:
    def __init__(self, name, served, enum_strs=None):
        self.pvname = name
        self.connected = name in served
        self._value = served.get(name)
        self.host = "cpu-l1b-rf02:5068"
        self.access = "read-only"
        self.type = "time_enum" if enum_strs else "time_double"
        self.enum_strs = None
        self._enum_strs = enum_strs
        self.put = MagicMock()

    def wait_for_connection(self, timeout=None):
        return self.connected

    def get(self, as_string=False, **kwargs):
        return self._value

    def get_ctrlvars(self, **kwargs):
        self.enum_strs = self._enum_strs


@pytest.fixture
def serve():
    """Patch PV so batch_create serves the given {name: string} dict."""
    created = []

    def _serve(served, enums=None):
        enums = enums or {}

        def batch_create(names, **kwargs):
            pvs = [FakePV(n, served, enums.get(n)) for n in names]
            created.extend(pvs)
            return pvs

        fake = MagicMock()
        fake.batch_create.side_effect = batch_create
        patcher = patch.object(pv_info, "PV", fake)
        patcher.start()
        return created

    yield _serve
    patch.stopall()
    for pv in created:
        pv.put.assert_not_called()


def describe(name, **kwargs):
    return "\n".join(pv_info.describe(name, **kwargs))


class TestResolve:
    def test_full_name_used_as_is(self, serve):
        serve({})
        assert pv_info.candidates("QUAD:L0B:0185:CTRL", "02", 1) == [
            "QUAD:L0B:0185:CTRL"
        ]

    def test_suffix_gets_every_cavity_prefix(self):
        names = pv_info.candidates("PUSH_DFGAIN", "02", 1)
        assert {
            "ACCL:L1B:0210:PUSH_DFGAIN",
            "ACCL:L1B:0210:PZT:PUSH_DFGAIN",
            "ACCL:L1B:0210:STEP:PUSH_DFGAIN",
            "ACCL:L1B:0210:SSA:PUSH_DFGAIN",
        } <= set(names)

    def test_name_as_typed_is_tried_first(self):
        assert pv_info.candidates("CTE:CM01", "01", 1)[0] == "CTE:CM01"

    def test_linac_comes_from_cryomodule(self):
        assert "ACCL:L1B:H180:ADES" in pv_info.candidates("ADES", "H1", 8)
        assert "ACCL:L3B:3530:ADES" in pv_info.candidates("ADES", "35", 3)

    @pytest.mark.parametrize(
        "suffix, cm, full",
        [
            ("DS:LVL", "01", "CLL:CM01:2301:DS:LVL"),
            ("PVJT:SP_RQST", "01", "CLIC:CM01:3001:PVJT:SP_RQST"),
            ("PVJT:SP_RQST", "H1", "CLIC:HL01:3001:PVJT:SP_RQST"),
            ("EHCV:MANPOS_RQST", "01", "CPIC:CM01:0000:EHCV:MANPOS_RQST"),
            ("CAS_ACCESS", "01", "CRYO:CM01:0:CAS_ACCESS"),
            ("AACTMEANSUM", "01", "ACCL:L0B:0100:AACTMEANSUM"),
            ("COMBO_P", "02", "VGXX:L1B:0214:COMBO_P"),
            ("CTRL", "02", "QUAD:L1B:0285:CTRL"),
        ],
    )
    def test_suffix_under_model_prefixes(self, suffix, cm, full):
        assert full in pv_info.candidates(suffix, cm, 1)

    def test_every_decarad_head_is_a_candidate(self):
        names = pv_info.candidates("GAMMAAVE", "02", 1)
        assert "RADM:SYS0:100:01:GAMMAAVE" in names
        assert "RADM:SYS0:200:10:GAMMAAVE" in names

    def test_unknown_cryomodule(self):
        with pytest.raises(ValueError, match="99"):
            pv_info.candidates("ADES", "99", 1)

    def test_suffix_resolves_to_the_one_that_answers(self, serve):
        serve(PUSH_DFGAIN)
        out = describe("PUSH_DFGAIN")
        assert out.startswith(P + "PUSH_DFGAIN\n")

    def test_several_answer_lists_them(self, serve):
        serve({"ACCL:L1B:0210:X": "1", P + "X": "2"})
        out = describe("X")
        assert "answers under more than one prefix" in out
        assert "ACCL:L1B:0210:X" in out and P + "X" in out
        assert "Links" not in out

    def test_none_answer(self, serve):
        serve({})
        out = describe("NOPE")
        assert out.startswith("No response from NOPE, as typed or under any")
        assert "CM02 cavity 1" in out


class TestRecord:
    def test_header_has_cainfo_facts(self, serve):
        serve(PUSH_DFGAIN)
        out = describe(P + "PUSH_DFGAIN")
        assert "cpu-l1b-rf02:5068" in out
        assert "read-only" in out
        assert "DBF_DOUBLE" in out
        assert 'ao record: "Push new DF gain"' in out
        assert "value: 0" in out

    def test_reverse_link_warning_comes_before_links(self, serve):
        serve(PUSH_DFGAIN)
        out = describe(P + "PUSH_DFGAIN")
        assert 'dbgrep "*PUSH_DFGAIN*"' in out
        assert "dbpr" in out
        assert out.index("dbgrep") < out.index("Links")

    def test_enum_states_listed_with_numbers(self, serve):
        name = P + "RFTESTSTAT"
        serve(
            {name: "Pass", name + ".RTYP": "mbbi", name + ".DESC": ""},
            enums={name: ("Pass", "Warning", "Fail")},
        )
        out = describe(name)
        assert "DBF_ENUM" in out
        assert "[0] Pass" in out and "[2] Fail" in out

    def test_no_response(self, serve):
        serve({})
        assert "No response" in describe(P + "NOPE")

    def test_no_record_fields(self, serve):
        """sc-sim serves most PVs without a record behind them."""
        serve({P + "DFGAIN_NEW": "0.85"})
        out = describe(P + "DFGAIN_NEW")
        assert "no record fields" in out
        assert "Links" not in out


class TestLinks:
    def test_push_dfgain(self, serve):
        serve(PUSH_DFGAIN)
        out = describe(P + "PUSH_DFGAIN")
        assert "OMSL  closed_loop" in out
        assert "DOL   " + P + "DFGAIN_NEW" in out
        assert "NPP: reads it as it stands" in out
        assert "NMS: does not pass on its alarm severity" in out
        assert "OUT   " + P + "DFGAIN" in out
        assert "PP: writes it and makes it process" in out
        assert "FLNK" not in out
        assert "Processing it copies DFGAIN_NEW as it stands into DFGAIN." in (
            out
        )

    def test_targets_read_one_hop(self, serve):
        serve(PUSH_DFGAIN)
        out = describe(P + "PUSH_DFGAIN")
        assert '→ ao "A detune gain" = 0.85' in out
        assert '→ ao "A detune gain" = 0.8' in out

    def test_target_no_response(self, serve):
        served = dict(PUSH_DFGAIN)
        del served[P + "DFGAIN"]
        serve(served)
        assert "→ no response" in describe(P + "PUSH_DFGAIN")

    def test_supervisory(self, serve):
        served = dict(PUSH_DFGAIN, **{P + "PUSH_DFGAIN.OMSL": "supervisory"})
        serve(served)
        out = describe(P + "PUSH_DFGAIN")
        assert "supervisory: ignores DOL" in out
        assert "Processing it writes its own value into DFGAIN." in out

    def test_only_type_fields_asked_for(self, serve):
        created = serve(PUSH_DFGAIN)
        describe(P + "PUSH_DFGAIN")
        asked = {pv.pvname for pv in created}
        assert P + "PUSH_DFGAIN.INP" not in asked
        assert P + "PUSH_DFGAIN.INPA" not in asked

    def test_unknown_type_asks_every_field(self, serve):
        name = P + "THING"
        created = serve({name: "1", name + ".RTYP": "weird"})
        describe(name)
        asked = {pv.pvname for pv in created}
        assert {name + ".INP", name + ".DOL", name + ".INPL"} <= asked

    def test_input_record_with_cp(self, serve):
        name = P + "AMP"
        serve(
            {
                name: "3",
                name + ".RTYP": "ai",
                name + ".DESC": "",
                name + ".INP": P + "RAW CP MS",
                name + ".FLNK": P + "NEXT",
            }
        )
        out = describe(name)
        assert "CP: this record processes whenever RAW changes" in out
        assert "MS: passes on its alarm severity" in out
        assert "FLNK  " + P + "NEXT" in out
        assert "Its value comes from RAW." in out

    def test_calc(self, serve):
        name = P + "SUM"
        serve(
            {
                name: "5",
                name + ".RTYP": "calc",
                name + ".DESC": "",
                name + ".CALC": "A+B",
                name + ".INPA": P + "A NPP",
                name + ".INPB": P + "B NPP",
                name + ".INPC": "",
            }
        )
        out = describe(name)
        assert "INPA  " + P + "A" in out
        assert "INPC" not in out
        assert "Its value is CALC = A+B over the inputs above." in out

    @pytest.mark.parametrize(
        "link, label",
        [("@asyn(PORT,0)", "hardware address"), ("0.5", "constant")],
    )
    def test_non_pv_links(self, serve, link, label):
        name = P + "IN"
        serve(
            {
                name: "1",
                name + ".RTYP": "ai",
                name + ".DESC": "",
                name + ".INP": link,
            }
        )
        out = describe(name)
        assert f"INP   {link}  ({label}, not a PV)" in out


def test_sim_style_zero_flnk_is_unset(serve):
    """sc-sim's ai records serve INP and FLNK as "0"."""
    name = "ACCL:L1B:0200:NRP:STATSUMY"
    serve(
        {
            name: "0",
            name + ".RTYP": "ai",
            name + ".DESC": "",
            name + ".INP": "0",
            name + ".FLNK": "0",
        }
    )
    out = describe(name)
    assert "INP   0  (constant, not a PV)" in out
    assert "FLNK" not in out


def test_main_prints(serve, capsys):
    serve(PUSH_DFGAIN)
    with patch("sys.argv", ["sc-pv-info", "PUSH_DFGAIN", "--cm", "02"]):
        pv_info.main()
    assert "copies DFGAIN_NEW" in capsys.readouterr().out
