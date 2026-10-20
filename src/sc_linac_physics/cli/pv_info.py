"""sc-pv-info: print what an EPICS record does, from its fields over CA.

Read-only: every PV here is read with PV.get, never put. The vocabulary
(record types, link fields, flags) is the one in docs/utils/epics_records.md.
"""

import argparse
import logging
import time
from typing import Dict, List, Optional, Sequence

from sc_linac_physics.utils.epics import PV, PVConnectionError, PVGetError
from sc_linac_physics.utils.sc_linac.linac_utils import (
    build_cavity_pv_prefix,
    get_linac_for_cryomodule,
)

# How long one round of reads waits for missing PVs (a wrong prefix, a
# field the record type lacks) before calling them "no response".
CONNECT_TIMEOUT_S = 1.0
# PV.batch_create waits on each PV in turn, so a missing PV costs its full
# connection_timeout. It gets this much; _connect then waits once, against
# one CONNECT_TIMEOUT_S deadline, for any PV still connecting.
BATCH_WAIT_S = 0.05

# Prefixes a cavity's PVs use in utils/sc_linac: the cavity itself,
# Piezo, StepperTuner and SSA (each built with cavity.pv_addr).
CAVITY_SUBPREFIXES = ("", "PZT:", "STEP:", "SSA:")

INPUT_TYPES = {"ai", "bi", "mbbi", "mbbiDirect", "longin", "int64in"}
INPUT_TYPES |= {"stringin", "lsi", "waveform", "aai", "subArray"}
OUTPUT_TYPES = {"ao", "bo", "mbbo", "mbboDirect", "longout", "int64out"}
OUTPUT_TYPES |= {"stringout", "lso"}
CALC_INPUTS = tuple(f"INP{letter}" for letter in "ABCDEFGHIJKL")
LINK_FIELDS = ("INP", "DOL", "OUT") + CALC_INPUTS + ("FLNK",)


def candidates(name: str, cm: str, cav: int) -> List[str]:
    """Full PV names to try for `name`.

    A name with three or more colons (ACCL:L1B:0210:PZT:PUSH_DFGAIN,
    QUAD:L0B:0185:CTRL) is used as is. Anything shorter is a suffix under
    the cavity's prefix, with or without PZT:/STEP:/SSA:.
    """
    if name.count(":") >= 3:
        return [name]
    linac = get_linac_for_cryomodule(cm)
    if linac is None:
        raise ValueError(f"No linac has cryomodule {cm!r}")
    prefix = build_cavity_pv_prefix(linac, cm, cav)
    return [prefix + sub + name for sub in CAVITY_SUBPREFIXES]


def _connect(names: Sequence[str]) -> List[PV]:
    pvs = PV.batch_create(list(names), connection_timeout=BATCH_WAIT_S)
    pvs = [pv for pv in pvs if pv is not None]
    deadline = time.monotonic() + CONNECT_TIMEOUT_S
    for pv in pvs:
        if not pv.connected:
            pv.wait_for_connection(max(0.0, deadline - time.monotonic()))
    return [pv for pv in pvs if pv.connected]


def _read(names: Sequence[str]) -> Dict[str, Optional[str]]:
    """{name: value as a string}, or None for a PV that didn't answer."""
    values = dict.fromkeys(names)
    for pv in _connect(names):
        try:
            values[pv.pvname] = pv.get(as_string=True)
        except (PVConnectionError, PVGetError):
            pass
    return values


def _fields_for(rtyp: str) -> List[str]:
    if rtyp in INPUT_TYPES:
        return ["INP", "FLNK"]
    if rtyp in OUTPUT_TYPES:
        return ["OMSL", "DOL", "OUT", "FLNK"]
    if rtyp == "calc":
        return ["CALC", *CALC_INPUTS, "FLNK"]
    if rtyp == "calcout":
        return ["CALC", *CALC_INPUTS, "OUT", "FLNK"]
    return ["OMSL", "CALC", *LINK_FIELDS]


def _link_kind(link: str) -> Optional[str]:
    """'hardware address' or 'constant' for a link that names no PV."""
    if link.startswith(("@", "#")):
        return "hardware address"
    try:
        float(link)
        return "constant"
    except ValueError:
        return "constant" if link.startswith(("{", "[", '"')) else None


# Flag meanings: EPICS Application Developer's Guide, "Database Links".
# The PP/NPP/CP/MS/NMS wording follows docs/utils/epics_records.md.
def _flag_words(flag: str, field: str, short: str) -> str:
    writes = field == "OUT"
    words = {
        "PP": (
            "writes it and makes it process"
            if writes
            else "makes it process, then reads it"
        ),
        "NPP": (
            "writes it without making it process"
            if writes
            else "reads it as it stands, without processing it"
        ),
        "CP": f"this record processes whenever {short} changes",
        "CPP": f"like CP: processes whenever {short} changes, if passive",
        "CA": "goes over Channel Access, even on the same IOC",
        "MS": "passes on its alarm severity",
        "NMS": "does not pass on its alarm severity",
        "MSS": "passes on its alarm severity and status",
        "MSI": "passes on its alarm severity only when INVALID",
    }.get(flag, "flag not explained here")
    return f"{flag}: {words}"


def _short(target: str, record: str) -> str:
    """Drop the device prefix the target shares with the record."""
    device = record.rsplit(":", 1)[0] + ":"
    return target[len(device) :] if target.startswith(device) else target


def _link_lines(field, link, record, targets) -> List[str]:
    kind = _link_kind(link)
    if kind:
        return [f"  {field:<5} {link}  ({kind}, not a PV)"]
    target, *flags = link.split()
    short = _short(target, record)
    lines = [f"  {field:<5} {target}"]
    if field == "FLNK":
        lines.append("          makes it process next, after this one")
    elif not {"PP", "NPP", "CP", "CPP"} & set(flags):
        lines.append("          no PP/NPP flag, so NPP (the default)")
    for flag in flags:
        lines.append("          " + _flag_words(flag, field, short))
    value = targets.get(target)
    if value is None:
        lines.append("          → no response")
    else:
        rtyp = targets.get(target + ".RTYP") or "no record fields"
        desc = targets.get(target + ".DESC") or ""
        lines.append(f'          → {rtyp} "{desc}" = {value}')
    return lines


def _summary(rtyp, fields, record) -> Optional[str]:
    def pv_target(field):
        link = fields.get(field) or ""
        return None if not link or _link_kind(link) else link.split()

    if rtyp in ("calc", "calcout"):
        return (
            f"Its value is CALC = {fields.get('CALC')} over the inputs above."
        )
    if rtyp in INPUT_TYPES:
        inp = pv_target("INP")
        if inp:
            return f"Its value comes from {_short(inp[0], record)}."
        kind = _link_kind(fields.get("INP") or "")
        return f"Its value comes from a {kind}." if kind else None
    out = pv_target("OUT")
    if rtyp not in OUTPUT_TYPES or not out:
        return None
    dest = _short(out[0], record)
    dol = pv_target("DOL")
    if fields.get("OMSL") == "closed_loop" and dol:
        how = "after making it process" if "PP" in dol else "as it stands"
        source = _short(dol[0], record)
        return f"Processing it copies {source} {how} into {dest}."
    return f"Processing it writes its own value into {dest}."


def _record_lines(pv: PV) -> List[str]:
    name = pv.pvname
    dbf = "DBF_" + str(pv.type).split("_")[-1].upper()
    head = _read([name, name + ".RTYP", name + ".DESC"])
    lines = [
        name,
        f"  connected · {pv.host} · {pv.access} · {dbf}",
    ]
    rtyp = head[name + ".RTYP"]
    if rtyp is None:
        lines.append("  no record fields served (.RTYP doesn't answer)")
    else:
        lines.append(f'  {rtyp} record: "{head[name + ".DESC"] or ""}"')
    lines.append(f"  value: {head[name]}")
    if dbf == "DBF_ENUM":
        pv.get_ctrlvars(timeout=CONNECT_TIMEOUT_S, warn=False)
        lines.append("  states:")
        for i, state in enumerate(pv.enum_strs or ()):
            lines.append(f"    [{i}] {state}")
    record = name.rsplit(":", 1)[-1]
    lines += [
        "",
        "  Channel Access can't show which records read this one. On the",
        f'  IOC shell, dbgrep "*{record}*" lists matching records and',
        "  dbpr <record> 1 prints each one's links.",
    ]
    if rtyp is not None:
        lines += _links_section(name, rtyp)
    return lines


def _links_section(name: str, rtyp: str) -> List[str]:
    wanted = _fields_for(rtyp)
    raw = _read([f"{name}.{f}" for f in wanted])
    fields = {f: raw[f"{name}.{f}"] for f in wanted}
    links = {f: v for f, v in fields.items() if f in LINK_FIELDS and v}
    # A FLNK only names a record to process; sc-sim serves an unset one as
    # "0", so a FLNK that names no PV is treated as unset.
    if _link_kind(links.get("FLNK", "")):
        del links["FLNK"]
    target_names = [v.split()[0] for v in links.values() if not _link_kind(v)]
    targets = _read(
        [t + suffix for t in target_names for suffix in ("", ".RTYP", ".DESC")]
    )

    lines = ["", "Links"]
    omsl = fields.get("OMSL")
    if omsl == "closed_loop":
        lines.append(
            "  OMSL  closed_loop: fetches from DOL every time it processes"
        )
    elif omsl:
        lines.append(
            f"  OMSL  {omsl}: ignores DOL and uses the value written to "
            "the record"
        )
    for field, link in links.items():
        lines += _link_lines(field, link, name, targets)
    if not links:
        lines.append("  none set")
    summary = _summary(rtyp, fields, name)
    if summary:
        lines += ["", summary]
    return lines


def describe(name: str, cm: str = "02", cav: int = 1) -> List[str]:
    """Lines describing the record `name` (full PV name or suffix)."""
    names = candidates(name, cm, cav)
    answered = _connect(names)
    if not answered:
        return [f"No response from {' or '.join(names)}"]
    if len(answered) > 1:
        lines = [f"{name} answers under more than one prefix:"]
        return lines + [f"  {pv.pvname}" for pv in answered]
    return _record_lines(answered[0])


def main():
    parser = argparse.ArgumentParser(
        description="Print what an EPICS record does. Reads only.",
    )
    parser.add_argument(
        "name",
        help="full PV name, or a suffix such as PUSH_DFGAIN under a cavity",
    )
    parser.add_argument("--cm", default="02", help="cryomodule (default 02)")
    parser.add_argument(
        "--cav",
        type=int,
        default=1,
        choices=range(1, 9),
        help="cavity number (default 1)",
    )
    args = parser.parse_args()
    # The epics logger warns on every PV that doesn't connect, and missing
    # PVs are expected here. The output already says "no response".
    logging.disable(logging.WARNING)
    print("\n".join(describe(args.name, args.cm, args.cav)))


if __name__ == "__main__":
    main()
