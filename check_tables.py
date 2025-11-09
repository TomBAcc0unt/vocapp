import sqlite3

DB = "../results.db"

def list_tables_and_data(db_path):
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()

        # Get list of all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cur.fetchall()]

        if not tables:
            print("No tables found in the database.")
            return

        for table in tables:
            print(f"\n--- Table: {table} ---")

            # Get column names
            cur.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cur.fetchall()]
            print("Columns:", ", ".join(columns))

            # Fetch all data
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            if rows:
                for row in rows:
                    print(row)
            else:
                print("(No data)")

if __name__ == "__main__":
    list_tables_and_data(DB)

