"""Poll tuning state PVs and persist current + versioned state."""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

from sc_linac_physics.applications.tuning.state.common import (
    DEFAULT_BASE_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_LOG_PATH,
    batched,
    build_state_logger,
    connect_db,
    now_utc_iso,
    resolve_poll_paths,
)
from sc_linac_physics.utils.epics import PVBatch
from sc_linac_physics.utils.sc_linac.linac_utils import (
    LINAC_TUPLES,
    TUNE_CONFIG_COLD_VALUE,
    TUNE_CONFIG_OTHER_VALUE,
    TUNE_CONFIG_PARKED_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
    build_cavity_pv,
    build_cavity_pv_base,
)

CAVITIES_PER_CM = 8
TUNE_CONFIG_FIELD = "TUNE_CONFIG"
DF_COLD_FIELD = "DF_COLD"

TUNE_CONFIG_LABELS = {
    TUNE_CONFIG_RESONANCE_VALUE: "On resonance",
    TUNE_CONFIG_COLD_VALUE: "Cold landing",
    TUNE_CONFIG_PARKED_VALUE: "Parked",
    TUNE_CONFIG_OTHER_VALUE: "Other",
}
LABEL_TO_TUNE_CODE = {
    label.lower(): code for code, label in TUNE_CONFIG_LABELS.items()
}

logger = logging.getLogger(__name__)


def configure_logging(log_path: Path, verbose: bool = False) -> logging.Logger:
    """Configure module logging with the shared package logger utility."""
    return build_state_logger(__name__, log_path=log_path, verbose=verbose)


def iter_cavity_ids():
    """Yield cavity IDs in ACCL naming format."""
    for linac_name, cms in LINAC_TUPLES[:4]:
        for cm in cms:
            for cavity in range(1, CAVITIES_PER_CM + 1):
                yield build_cavity_pv_base(linac_name, cm, cavity)


def pv_names(cavity_id: str) -> dict[str, str]:
    _, linac_name, cavity_slot = cavity_id.split(":", maxsplit=2)
    cryomodule_name = cavity_slot[:2]
    cavity_num = int(cavity_slot[2])
    return {
        "tune_config": build_cavity_pv(
            linac_name,
            cryomodule_name,
            cavity_num,
            TUNE_CONFIG_FIELD,
        ),
        "df_cold": build_cavity_pv(
            linac_name,
            cryomodule_name,
            cavity_num,
            DF_COLD_FIELD,
        ),
    }


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        create table if not exists cavity_state (
          cavity_id text primary key,
          tune_config_code integer,
          tune_config_label text,
          tune_config_time text,
          df_cold real,
          df_cold_time text,
          updated_at text
        );

        create table if not exists df_cold_version (
          id integer primary key autoincrement,
          cavity_id text not null,
          df_cold real not null,
          pv text not null,
          sample_time text not null,
          inserted_at text not null
        );

        create table if not exists tune_config_version (
          id integer primary key autoincrement,
          cavity_id text not null,
          tune_config_code integer not null,
          tune_config_label text not null,
          pv text not null,
          sample_time text not null,
          inserted_at text not null
        );

        create index if not exists idx_df_cold_version_cavity_time
          on df_cold_version (cavity_id, sample_time);

        create index if not exists idx_tune_config_version_cavity_time
          on tune_config_version (cavity_id, sample_time);
        """)
    conn.commit()


def caget_values(
    pvs: list[str],
    caget_timeout_sec: int,
    command_timeout_sec: int,
    batch_size: int,
    caget_command: str,
) -> dict[str, object | None]:
    """Bulk-read PVs in batches using the shared EPICS batch utility."""
    # Deprecated compatibility args retained for CLI/API stability.
    _ = command_timeout_sec, caget_command
    result: dict[str, object | None] = {}
    logger.info("Reading %s PVs in batches of %s", len(pvs), batch_size)

    total_batches = (len(pvs) + batch_size - 1) // batch_size if pvs else 0
    for batch_num, batch in enumerate(batched(pvs, batch_size), start=1):
        batch = list(batch)

        logger.info(
            "Processing batch %s/%s (%s PVs)",
            batch_num,
            total_batches,
            len(batch),
        )

        values = PVBatch.get_values(batch, timeout=float(caget_timeout_sec))
        if len(values) < len(batch):
            logger.warning(
                "Batch %s returned %s values for %s PVs; marking missing as disconnected",
                batch_num,
                len(values),
                len(batch),
            )

        for pv, value in zip(batch, values):
            result[pv] = _normalize_pv_value(value)

        if len(values) < len(batch):
            for pv in batch[len(values) :]:
                result[pv] = None

    connected = sum(1 for value in result.values() if value is not None)
    logger.info("Completed PV read: %s/%s connected", connected, len(result))
    return result


def _normalize_pv_value(value: object | None) -> object | None:
    """Normalize batch-read values into scalar Python types."""
    if value is None:
        return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return value


def upsert_state(
    conn: sqlite3.Connection,
    cavity_id: str,
    tune_code: int | None,
    tune_label: str,
    df_cold: float | None,
    timestamp_iso: str,
) -> None:
    conn.execute(
        """
        insert into cavity_state (
          cavity_id, tune_config_code, tune_config_label, tune_config_time,
          df_cold, df_cold_time, updated_at
        )
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict(cavity_id) do update set
          tune_config_code = excluded.tune_config_code,
          tune_config_label = excluded.tune_config_label,
          tune_config_time = excluded.tune_config_time,
          df_cold = excluded.df_cold,
          df_cold_time = excluded.df_cold_time,
          updated_at = excluded.updated_at;
        """,
        (
            cavity_id,
            tune_code,
            tune_label,
            timestamp_iso,
            df_cold,
            timestamp_iso,
            now_utc_iso(),
        ),
    )


def last_df_cold(conn: sqlite3.Connection, cavity_id: str) -> float | None:
    row = conn.execute(
        """
        select df_cold
        from df_cold_version
        where cavity_id = ?
        order by sample_time desc
        limit 1
        """,
        (cavity_id,),
    ).fetchone()
    return None if row is None else float(row[0])


def last_tune_config(conn: sqlite3.Connection, cavity_id: str) -> int | None:
    row = conn.execute(
        """
        select tune_config_code
        from tune_config_version
        where cavity_id = ?
        order by sample_time desc
        limit 1
        """,
        (cavity_id,),
    ).fetchone()
    return None if row is None else int(row[0])


def insert_df_cold_version(
    conn: sqlite3.Connection,
    cavity_id: str,
    pv: str,
    df_cold: float,
    timestamp_iso: str,
) -> None:
    conn.execute(
        """
        insert into df_cold_version
          (cavity_id, df_cold, pv, sample_time, inserted_at)
        values (?, ?, ?, ?, ?)
        """,
        (cavity_id, float(df_cold), pv, timestamp_iso, now_utc_iso()),
    )


def insert_tune_config_version(
    conn: sqlite3.Connection,
    cavity_id: str,
    pv: str,
    tune_code: int,
    tune_label: str,
    timestamp_iso: str,
) -> None:
    conn.execute(
        """
        insert into tune_config_version
          (
            cavity_id,
            tune_config_code,
            tune_config_label,
            pv,
            sample_time,
            inserted_at
          )
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            cavity_id,
            int(tune_code),
            tune_label,
            pv,
            timestamp_iso,
            now_utc_iso(),
        ),
    )


def parse_tune_config(raw: object | None) -> tuple[int | None, str]:
    if raw is None:
        return None, "Not connected"

    text = str(raw).strip()

    try:
        code = int(text)
        return code, TUNE_CONFIG_LABELS.get(code, f"UNKNOWN_{code}")
    except ValueError:
        pass

    key = text.lower()
    if key in LABEL_TO_TUNE_CODE:
        code = LABEL_TO_TUNE_CODE[key]
        return code, TUNE_CONFIG_LABELS[code]

    return None, text


def parse_float(raw: object | None) -> float | None:
    if raw is None:
        return None

    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll cavity tuning PVs and persist tune status state"
    )

    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"Base directory for db/json/log files (default: {DEFAULT_BASE_DIR})",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=f"Override sqlite db path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Override JSON snapshot path (default: <base-dir>/tune_status.json)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help=f"Override log path (default: {DEFAULT_LOG_PATH})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of PVs per caget call (default: 100)",
    )
    parser.add_argument(
        "--caget-timeout",
        type=int,
        default=5,
        help="caget per-PV timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=60,
        help="Deprecated compatibility option; batch reads use package EPICS utilities",
    )
    parser.add_argument(
        "--caget-command",
        default="caget",
        help="Deprecated compatibility option; batch reads use package EPICS utilities",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global logger
    args = parse_args(argv)

    db_path, json_path, log_path = resolve_poll_paths(
        base_dir=args.base_dir,
        db_path=args.db_path,
        json_path=args.json_path,
        log_path=args.log_path,
    )

    logger = configure_logging(log_path=log_path, verbose=args.verbose)
    logger.info("Starting tune status poll")

    args.base_dir.mkdir(parents=True, exist_ok=True)
    cavity_ids = list(iter_cavity_ids())
    logger.info("Polling %s cavities", len(cavity_ids))

    tune_pvs = [pv_names(cavity_id)["tune_config"] for cavity_id in cavity_ids]
    cold_pvs = [pv_names(cavity_id)["df_cold"] for cavity_id in cavity_ids]
    all_pvs = tune_pvs + cold_pvs
    timestamp_iso = now_utc_iso()

    logger.info("Reading %s PVs via %s", len(all_pvs), args.caget_command)
    pv_values = caget_values(
        pvs=all_pvs,
        caget_timeout_sec=args.caget_timeout,
        command_timeout_sec=args.command_timeout,
        batch_size=args.batch_size,
        caget_command=args.caget_command,
    )

    conn = connect_db(db_path)
    init_db(conn)

    snapshot: list[dict[str, str | int | float | None]] = []
    tune_changes = 0
    df_changes = 0

    for cavity_id in cavity_ids:
        names = pv_names(cavity_id)
        tune_raw = pv_values.get(names["tune_config"])
        df_raw = pv_values.get(names["df_cold"])

        tune_code, tune_label = parse_tune_config(tune_raw)
        df_cold = parse_float(df_raw)

        upsert_state(
            conn, cavity_id, tune_code, tune_label, df_cold, timestamp_iso
        )

        if tune_code is not None:
            last_tune = last_tune_config(conn, cavity_id)
            if last_tune is None or tune_code != last_tune:
                insert_tune_config_version(
                    conn,
                    cavity_id,
                    names["tune_config"],
                    tune_code,
                    tune_label,
                    timestamp_iso,
                )
                tune_changes += 1

        if df_cold is not None:
            last_df = last_df_cold(conn, cavity_id)
            if last_df is None or df_cold != last_df:
                insert_df_cold_version(
                    conn,
                    cavity_id,
                    names["df_cold"],
                    df_cold,
                    timestamp_iso,
                )
                df_changes += 1

        snapshot.append(
            {
                "cavity_id": cavity_id,
                "tune_config_code": tune_code,
                "tune_config_label": tune_label,
                "df_cold": df_cold,
                "time": timestamp_iso,
            }
        )

    conn.commit()
    conn.close()

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, sort_keys=True)

    logger.info(
        "Database updated: %s tune config changes, %s DF_COLD changes",
        tune_changes,
        df_changes,
    )
    logger.info("Poll completed successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("Poll failed with exception")
        sys.exit(1)
