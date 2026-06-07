"""
Export the full MySQL database to a .sql file (CREATE TABLE + INSERT data).

Run from mock_test/backend:

  python scripts/export_database_sql.py
  python scripts/export_database_sql.py -o dumps/backup.sql
  python scripts/export_database_sql.py --method python
  python scripts/export_database_sql.py --tables users,package

Uses DB settings from app/core/config.py and backend/.env (DB_* overrides if set).

Requires: pymysql (already in requirements.txt). Optional: mysqldump on PATH (faster, recommended).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

# Allow: python scripts/export_database_sql.py from backend/
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import get_settings  # noqa: E402

try:
    import pymysql
except ImportError as exc:
    raise SystemExit("Install pymysql: pip install pymysql") from exc


def _apply_db_env_overrides(settings: Any) -> None:
    """Optional overrides via backend/.env: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME."""
    settings.db_host = os.getenv("DB_HOST", settings.db_host)
    settings.db_port = int(os.getenv("DB_PORT", str(settings.db_port)))
    settings.db_user = os.getenv("DB_USER", settings.db_user)
    settings.db_password = os.getenv("DB_PASSWORD", settings.db_password)
    settings.db_name = os.getenv("DB_NAME", settings.db_name)


def _find_mysqldump() -> str | None:
    explicit = os.getenv("MYSQLDUMP_PATH", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    found = shutil.which("mysqldump")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
        r"C:\xampp\mysql\bin\mysqldump.exe",
        r"C:\wamp64\bin\mysql\mysql8.0.31\bin\mysqldump.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def _default_output_path(db_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _BACKEND / "dumps"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{db_name}_{stamp}.sql"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, datetime):
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, (dict, list)):
        import json

        raw = json.dumps(value, ensure_ascii=False, default=str)
    else:
        raw = str(value)
    escaped = (
        raw.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\0", "")
    )
    return f"'{escaped}'"


def _connect(settings: Any) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
    )


def _list_tables(conn: pymysql.connections.Connection, only: set[str] | None) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        names = [row[0] for row in cur.fetchall()]
    if only:
        missing = only - set(names)
        if missing:
            raise SystemExit(f"Unknown table(s): {', '.join(sorted(missing))}")
        names = [t for t in names if t in only]
    return names


def export_via_mysqldump(
    settings: Any,
    output: Path,
    *,
    tables: list[str] | None,
    schema_only: bool,
    data_only: bool,
) -> None:
    mysqldump = _find_mysqldump()
    if not mysqldump:
        raise RuntimeError("mysqldump not found. Install MySQL client tools or use --method python")

    cmd: list[str] = [
        mysqldump,
        f"-h{settings.db_host}",
        f"-P{settings.db_port}",
        f"-u{settings.db_user}",
        f"-p{settings.db_password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        "--hex-blob",
        "--default-character-set=utf8mb4",
        "--set-gtid-purged=OFF",
        "--add-drop-table",
        "--complete-insert",
    ]
    if schema_only:
        cmd.append("--no-data")
    if data_only:
        cmd.append("--no-create-info")

    cmd.append(settings.db_name)
    if tables:
        cmd.extend(tables)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as out:
        header = (
            f"-- MySQL dump via mysqldump\n"
            f"-- Host: {settings.db_host}  Database: {settings.db_name}\n"
            f"-- Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
        )
        out.write(header)
        out.flush()
        proc = subprocess.run(
            cmd,
            stdout=out,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    if proc.returncode != 0:
        output.unlink(missing_ok=True)
        raise RuntimeError(proc.stderr.strip() or f"mysqldump exited with code {proc.returncode}")
    print(f"Wrote {output} ({output.stat().st_size:,} bytes) via mysqldump")


def export_via_python(
    settings: Any,
    output: Path,
    *,
    tables: list[str] | None,
    schema_only: bool,
    data_only: bool,
    batch_rows: int,
) -> None:
    only = set(tables) if tables else None
    conn = _connect(settings)
    try:
        table_names = _list_tables(conn, only)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="\n") as out:
            out.write(
                f"-- Python SQL export\n"
                f"-- Host: {settings.db_host}  Database: {settings.db_name}\n"
                f"-- Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
                "SET NAMES utf8mb4;\n"
                "SET FOREIGN_KEY_CHECKS=0;\n"
                "SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n\n"
            )

            for name in table_names:
                print(f"  {name} ...")
                with conn.cursor() as cur:
                    if not data_only:
                        cur.execute(f"SHOW CREATE TABLE `{name}`")
                        row = cur.fetchone()
                        create_sql = row[1] if row else ""
                        out.write(f"\n--\n-- Table structure for `{name}`\n--\n\n")
                        out.write(f"DROP TABLE IF EXISTS `{name}`;\n")
                        out.write(create_sql + ";\n\n")

                    if schema_only:
                        continue

                    cur.execute(f"SELECT * FROM `{name}`")
                    columns = [d[0] for d in cur.description] if cur.description else []
                    if not columns:
                        continue

                    col_list = ", ".join(f"`{c}`" for c in columns)
                    batch: list[str] = []
                    row_count = 0

                    while True:
                        rows = cur.fetchmany(batch_rows)
                        if not rows:
                            break
                        for row in rows:
                            values = ", ".join(_sql_literal(v) for v in row)
                            batch.append(f"({values})")
                            row_count += 1
                            if len(batch) >= batch_rows:
                                out.write(
                                    f"INSERT INTO `{name}` ({col_list}) VALUES\n"
                                    + ",\n".join(batch)
                                    + ";\n"
                                )
                                batch.clear()

                    if batch:
                        out.write(
                            f"INSERT INTO `{name}` ({col_list}) VALUES\n"
                            + ",\n".join(batch)
                            + ";\n"
                        )
                    if row_count:
                        out.write(f"\n-- {row_count} row(s) for `{name}`\n")

            out.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

        print(f"Wrote {output} ({output.stat().st_size:,} bytes) via Python ({len(table_names)} tables)")
    finally:
        conn.close()


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export MySQL DB to .sql (CREATE + INSERT).")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .sql file (default: backend/dumps/<db>_<timestamp>.sql)",
    )
    parser.add_argument(
        "--method",
        choices=("auto", "mysqldump", "python"),
        default="auto",
        help="auto: mysqldump if available, else Python (default: auto)",
    )
    parser.add_argument(
        "--tables",
        help="Comma-separated table names only (default: all tables)",
    )
    parser.add_argument("--schema-only", action="store_true", help="CREATE only, no INSERTs")
    parser.add_argument("--data-only", action="store_true", help="INSERT only, no CREATE")
    parser.add_argument(
        "--batch-rows",
        type=int,
        default=200,
        help="Rows per INSERT statement in Python mode (default: 200)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.schema_only and args.data_only:
        parser.error("Use only one of --schema-only or --data-only")

    settings = get_settings()
    _apply_db_env_overrides(settings)
    output = args.output or _default_output_path(settings.db_name)
    tables = [t.strip() for t in args.tables.split(",") if t.strip()] if args.tables else None

    print(
        f"Exporting `{settings.db_name}` from {settings.db_host}:{settings.db_port} "
        f"-> {output}"
    )

    method = args.method
    if method == "auto":
        method = "mysqldump" if _find_mysqldump() else "python"
        print(f"Using method: {method}")

    try:
        if method == "mysqldump":
            export_via_mysqldump(
                settings,
                output,
                tables=tables,
                schema_only=args.schema_only,
                data_only=args.data_only,
            )
        else:
            export_via_python(
                settings,
                output,
                tables=tables,
                schema_only=args.schema_only,
                data_only=args.data_only,
                batch_rows=max(1, args.batch_rows),
            )
    except RuntimeError as exc:
        if method == "mysqldump" and args.method == "auto":
            print(f"mysqldump failed ({exc}); falling back to Python ...")
            export_via_python(
                settings,
                output,
                tables=tables,
                schema_only=args.schema_only,
                data_only=args.data_only,
                batch_rows=max(1, args.batch_rows),
            )
        else:
            raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
