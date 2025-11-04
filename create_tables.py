import sqlite3
import os

# Path to your SQLite database
DB = "results.db"

def init_db():
    """Initialize the database with tables and default columns."""
    # Ensure the database file exists (will be created automatically)
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        # Vocabulary table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT NOT NULL,
                slovak TEXT NOT NULL,
                image TEXT NOT NULL
            )
        ''')

        # Results table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                run_id INTEGER,
                word_id INTEGER,
                correct INTEGER,
                user_guess TEXT,
                FOREIGN KEY(word_id) REFERENCES vocabulary(id)
            )
        ''')

        # Users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user TEXT PRIMARY KEY,
                breadcrumbs_inventory INTEGER DEFAULT 0,
                breadcrumbs_fullness INTEGER DEFAULT 50,
                breadcrumbs_last_fed TEXT DEFAULT (datetime('now')),                
                cheese_inventory INTEGER DEFAULT 0,
                cheese_fullness INTEGER DEFAULT 50,
                cheese_last_fed TEXT DEFAULT (datetime('now')),                                
                happiness INTEGER DEFAULT 50,
                happiness_last_fed TEXT DEFAULT (datetime('now'))
            )
        ''')

    print("Database initialized or verified.")

if __name__ == "__main__":
    # Check if DB already exists
    if not os.path.exists(DB):
        print(f"Database file '{DB}' not found. It will be created.")
    else:
        print(f"Database file '{DB}' already exists. Tables will be verified/created if missing.")

    init_db()

