"""sc-pv-info: print what an EPICS record does, from its fields over CA.

Read-only: every PV here is read with PV.get, never put. The vocabulary
(record types, link fields, flags) is the one in docs/utils/epics_records.md.
"""

import argparse
import logging
import time
from typing import Dict, List, Optional, Sequence

from sc_linac_physics.utils.epics import PV, PVConnectionError, PVGetError
from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac import Machine

# How long one round of reads waits for missing PVs (a wrong prefix, a
# field the record type lacks) before calling them "no response".
CONNECT_TIMEOUT_S = 1.0
# PV.batch_create waits on each PV in turn, so a missing PV costs its full
# connection_timeout. It gets this much; _connect then waits once, against
# one CONNECT_TIMEOUT_S deadline, for any PV still connecting. A suffix
# makes ~60 candidates, so this keeps that round under a second.
BATCH_WAIT_S = 0.005

INPUT_TYPES = {"ai", "bi", "mbbi", "mbbiDirect", "longin", "int64in"}
INPUT_TYPES |= {"stringin", "lsi", "waveform", "aai", "subArray"}
OUTPUT_TYPES = {"ao", "bo", "mbbo", "mbboDirect", "longout", "int64out"}
OUTPUT_TYPES |= {"stringout", "lso"}
CALC_INPUTS = tuple(f"INP{letter}" for letter in "ABCDEFGHIJKL")
LINK_FIELDS = ("INP", "DOL", "OUT") + CALC_INPUTS + ("FLNK",)


def _model_objects(cm: str, cav: int) -> list:
    """The utils/sc_linac objects whose PVs a suffix can belong to.

    Decarads aren't tied to a cryomodule in the model, so both decarads
    and all their heads are included for every --cm.
    """
    try:
        cryomodule = Machine().cryomodules[cm]
    except KeyError:
        raise ValueError(f"No linac has cryomodule {cm!r}") from None
    cavity = cryomodule.cavities[cav]
    magnets = [getattr(cryomodule, m, None) for m in ("quad", "xcor", "ycor")]
    decarads = [Decarad(1), Decarad(2)]
    return [
        cryomodule.linac,
        cryomodule,
        cryomodule.rack_a,
        cryomodule.rack_b,
        cavity,
        cavity.piezo,
        cavity.stepper_tuner,
        cavity.ssa,
        *(m for m in magnets if m is not None),
        *decarads,
        *(head for d in decarads for head in d.heads.values()),
    ]


def _model_prefixes(cm: str, cav: int) -> set:
    """Every prefix the model builds for this CM and cavity.

    Taken from attributes named *prefix, *_pv and *_pvs. A full PV name
    gives each of its prefixes past the third colon, so CLL:CM01:2301:DS:LVL
    gives CLL:CM01:2301: and CLL:CM01:2301:DS:.
    """
    objects = _model_objects(cm, cav)
    names = []
    for obj in objects:
        for key, value in vars(obj).items():
            if key.lower().endswith(("prefix", "_pv", "_pvs")):
                names += value if isinstance(value, list) else [value]
    # CAS_ACCESS's prefix; Q0Cryomodule builds it (q0_cryomodule.py), not
    # utils/sc_linac. objects[1] is the cryomodule.
    names.append(f"CRYO:{objects[1].cryo_name}:0:")

    prefixes = set()
    for name in (n for n in names if isinstance(n, str)):
        if name.endswith(":"):
            prefixes.add(name)
        for i, char in enumerate(name):
            if char == ":" and name[: i + 1].count(":") >= 3:
                prefixes.add(name[: i + 1])
    return prefixes


def candidates(name: str, cm: str, cav: int) -> List[str]:
    """Full PV names to try for `name`.

    A name with three or more colons (ACCL:L1B:0210:PZT:PUSH_DFGAIN,
    QUAD:L0B:0185:CTRL) is used as is. Anything shorter is tried as typed,
    then under every prefix the model builds for this CM and cavity.
    """
    if name.count(":") >= 3:
        return [name]
    prefixes = sorted(_model_prefixes(cm, cav))
    return [name] + [prefix + name for prefix in prefixes]


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
    for pv in _connect(list(values)):
        try:
            values[pv.pvname] = pv.get(as_string=True)
        except (PVConnectionError, PVGetError):
            pass
    return values


def _record_of(name: str) -> str:
    """The record a PV name belongs to: PUSH_DFGAIN.PROC -> PUSH_DFGAIN."""
    return name.split(".", 1)[0]


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
# PP only processes a passive target, and a CA link doesn't apply it.
# CHECK: over a CA link (another IOC, or the CA flag), does the target
# process anyway when the field written is VAL?
def _flag_words(flag: str, field: str, short: str) -> str:
    writes = field == "OUT"
    words = {
        "PP": (
            "writes it, then makes it process if it is passive "
            "(not over a CA link)"
            if writes
            else "makes it process first if it is passive, then reads it "
            "(not over a CA link)"
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
        owner = _record_of(target)
        rtyp = targets.get(owner + ".RTYP") or "no record fields"
        desc = targets.get(owner + ".DESC") or ""
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
        how = (
            "after processing it if it is passive"
            if "PP" in dol
            else "as it stands"
        )
        source = _short(dol[0], record)
        return f"Processing it copies {source} {how} into {dest}."
    return f"Processing it writes its own value into {dest}."


def _record_lines(pv: PV) -> List[str]:
    # A field-qualified name (PUSH_DFGAIN.PROC) gives the value and cainfo
    # facts; the record's type, DESC and links come from PUSH_DFGAIN.
    name = pv.pvname
    owner = _record_of(name)
    dbf = "DBF_" + str(pv.type).split("_")[-1].upper()
    head = _read([name, owner + ".RTYP", owner + ".DESC"])
    lines = [
        name,
        f"  connected · {pv.host} · {pv.access} · {dbf}",
    ]
    rtyp = head[owner + ".RTYP"]
    if rtyp is None:
        lines.append("  no record fields served (.RTYP doesn't answer)")
    else:
        lines.append(f'  {rtyp} record: "{head[owner + ".DESC"] or ""}"')
    lines.append(f"  value: {head[name]}")
    if dbf == "DBF_ENUM":
        pv.get_ctrlvars(timeout=CONNECT_TIMEOUT_S, warn=False)
        lines.append("  states:")
        for i, state in enumerate(pv.enum_strs or ()):
            lines.append(f"    [{i}] {state}")
    record = owner.rsplit(":", 1)[-1]
    lines += [
        "",
        "  Channel Access can't show which records read this one. On the",
        f'  IOC shell, dbgrep "*{record}*" lists matching records and',
        "  dbpr <record> 1 prints each one's links.",
    ]
    if rtyp is not None:
        lines += _links_section(owner, rtyp)
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
        list(target_names)
        + [_record_of(t) + f for t in target_names for f in (".RTYP", ".DESC")]
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
        if len(names) == 1:
            return [f"No response from {name}"]
        return [
            f"No response from {name}, as typed or under any of the "
            f"{len(names) - 1} prefixes the model builds for CM{cm} "
            f"cavity {cav}"
        ]
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
