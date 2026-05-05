"""SQLite query execution tool. Local-first, zero-dep database access.

Usage: python sql.py <db_path> <query>
SELECT queries return results as text table. Write queries report rows affected.
DB is auto-created if it doesn't exist. All data stays on-disk.
"""

import os
import sqlite3
import sys

MAX_ROWS = 500
MAX_COL_WIDTH = 120


def main() -> None:
    if len(sys.argv) < 3:
        print("[SQL ERROR] Usage: sql.py <db_path> <query>")
        return

    db_path = sys.argv[1]
    query = " ".join(sys.argv[2:])

    if not query.strip():
        print("[SQL ERROR] Empty query.")
        return

    # Safety: refuse to operate on files > 4GB (FAT32 limit)
    if os.path.isfile(db_path) and os.path.getsize(db_path) > 4 * 1024**3:
        print("[SQL ERROR] Database exceeds 4 GB FAT32 limit.")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query)

        upper = query.strip().upper()
        if upper.startswith("SELECT") or upper.startswith("PRAGMA") or upper.startswith("EXPLAIN"):
            rows = cursor.fetchmany(MAX_ROWS + 1)
            if not rows:
                print("[SQL] Query returned 0 rows.")
                conn.close()
                return

            columns = [desc[0] for desc in cursor.description]
            truncated = len(rows) > MAX_ROWS
            if truncated:
                rows = rows[:MAX_ROWS]

            # Simple text table
            col_widths = [len(c) for c in columns]
            for row in rows:
                for i, val in enumerate(row):
                    col_widths[i] = min(MAX_COL_WIDTH, max(col_widths[i], len(str(val))))

            header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(columns))
            sep = "-+-".join("-" * w for w in col_widths)
            print(header)
            print(sep)
            for row in rows:
                line = " | ".join(
                    str(v).ljust(col_widths[i])[:MAX_COL_WIDTH]
                    for i, v in enumerate(row)
                )
                print(line)

            if truncated:
                print(f"... [TRUNCATED at {MAX_ROWS} rows]")
            else:
                print(f"\n[SQL] {len(rows)} row(s) returned.")
        else:
            conn.commit()
            print(f"[SQL OK] {cursor.rowcount} row(s) affected.")

        conn.close()

    except sqlite3.Error as e:
        print(f"[SQL ERROR] {e}")
    except Exception as e:
        print(f"[SQL ERROR] Unexpected: {e}")


if __name__ == "__main__":
    main()
