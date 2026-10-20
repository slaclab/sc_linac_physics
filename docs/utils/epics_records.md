# Reading an IOC record

How to find out what a PV does from a terminal, without IOC expertise.
Every command here only reads.

## Records and fields

A PV name like `ACCL:L1B:0210:PZT:PUSH_DFGAIN` is a *record* on an IOC.
A record has settings called *fields*, read as `PV.FIELD`. A plain `caget`
reads `.VAL`, the record's value.

```bash
caget ACCL:L1B:0210:PZT:PUSH_DFGAIN.RTYP ACCL:L1B:0210:PZT:PUSH_DFGAIN.DESC
```

`RTYP` is the record type and `DESC` a one-line description. Some `DESC`s are
generic ("A detune gain"), so the link fields below usually say more.

For an enum PV, `caget` shows the current state's string. This lists every
state with its number, which is what code compares against:

```bash
caget -d DBR_CTRL_ENUM ACCL:L1B:0210:PZT:RFTESTSTAT
```

## Processing

A record does its job only when it *processes*: it runs once, reading its
input, updating its value, and writing its output. Writing `1` to `.PROC`
makes it process. It stores nothing; `PUSH_DFGAIN.PROC = 1` means "run
`PUSH_DFGAIN` once".

## Record types you will meet

| Type | Holds |
|---|---|
| `ai` / `ao` | A number. An `ai` (analog input) is filled in by something else, such as a device, a script or a link. An `ao` (analog output) sends its number somewhere. |
| `bi` / `bo` | A two-state value (off/on). |
| `mbbi` / `mbbo` | An enum of up to 16 named states. |
| `calc` | A formula over inputs `INPA` … `INPL`. |

## Link fields

Links are fields that name another record. They are where a record's value
comes from and where it goes.

| Field | On | Meaning |
|---|---|---|
| `INP` | input records (`ai`, `bi`, …) | where the value is read from |
| `DOL` | output records (`ao`, `bo`, …) | where the value is fetched from, if `OMSL` says so |
| `OMSL` | output records | `closed_loop`: fetch from `DOL` every time it processes. `supervisory`: ignore `DOL` and use the value written to the record. |
| `OUT` | output records | where the value is written |
| `INPA` … `INPL` | `calc` | the formula's inputs |
| `FLNK` | any | a record to process next, after this one |

Each link carries flags after the PV name:

- `PP` (process passive) makes the other record process too, but only if
  that record's `SCAN` is `Passive`; a periodic or event-driven record is
  left to its own schedule. On an input link the source processes before
  the value is read. On an output link the destination processes after the
  write, so the value takes effect. This holds for links between records on
  the same IOC; a link to another IOC goes over Channel Access, with its own
  rules. `NPP` reads or writes without processing the other record.
- `CP` (on an input) makes this record process whenever the source changes.
- `MS` passes the source's alarm severity on; `NMS` doesn't.

## Example: the piezo detune gain push

The piezo with RF phase writes `PUSH_DFGAIN.PROC` and then
`SAVE_DFGAIN.PROC`. Their links, as `ACCL:L1B:0210:PZT` served them on
2026-10-20:

```bash
caget ACCL:L1B:0210:PZT:PUSH_DFGAIN.DOL ACCL:L1B:0210:PZT:PUSH_DFGAIN.OMSL ACCL:L1B:0210:PZT:PUSH_DFGAIN.OUT
```

| Record | `OMSL` | `DOL` | `OUT` | So processing it… |
|---|---|---|---|---|
| `PUSH_DFGAIN` (`ao`) | `closed_loop` | `DFGAIN_NEW NPP` | `DFGAIN PP` | copies `DFGAIN_NEW` as it stands into `DFGAIN`, the gain in use |
| `SAVE_DFGAIN` (`ao`) | `closed_loop` | `DFGAIN NPP` | `DFGAIN_SAVE PP` | copies whatever `DFGAIN` holds into `DFGAIN_SAVE` |

Two things follow. The push sends whatever `DFGAIN_NEW` holds at the moment
PUSH processes; it doesn't compute a new gain. The links don't promise that
this is the value the operator reviewed: if `DFGAIN_NEW` changes in between,
PUSH copies the new one. Code that pushes a reviewed value has to re-read
`DFGAIN_NEW` just before pushing and refuse if it changed. And SAVE has to
run after PUSH has finished, or it saves the old gain.

## Links point one way

A record names its own sources and destinations, never the records that read
from it. So `caget` can't tell you who uses `DFGAIN_SAVE`. Two ways to find
out:

- Check the likely reader's own links. For example, if `DFGAIN.DOL` names
  `DFGAIN_SAVE`, the live gain can be reloaded from the saved one.
- On the IOC's shell, `dbgrep "*DFGAIN*"` lists matching records, and
  `dbpr <record> 1` prints each one's fields, links included. Ask the IOC's
  owner if you don't have shell access.

Values restored at IOC boot by autosave don't show up in links at all. They
are listed in the IOC's autosave request files, which the IOC's owner knows.

## What this means for code

`PV.put(value)` waits for the IOC to confirm the record processed
(`wait=True`), and never sends twice
<span class="cite">`epics/core.py::PV.put “Only None is retried.”`</span>.

That is right for a record like `PUSH_DFGAIN`, whose processing is one copy.
It is wrong for a record that starts a long script, such as `RFTESTSTRT` or
`PROBECALSTRT`. There the put may not be confirmed until the script ends.
The caller waits up to `put_timeout`, 30 s by default
<span class="cite">`epics/config.py::PVConfig “put_timeout: float = 30.0”`</span>,
and then `PV.put` raises `PVPutError`. The script may still be running when
that happens: the start reached the IOC, so don't send it again. Those
starts use `wait=False`
<span class="cite">`cavity.py::Cavity.start_characterization “put(1, wait=False)”`</span>,
and the code then polls the script's status PV
<span class="cite">`cavity.py::Cavity.wait_for_characterization`</span>.
