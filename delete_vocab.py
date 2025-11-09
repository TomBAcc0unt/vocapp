import sqlite3
conn = sqlite3.connect('../results.db')
cursor = conn.cursor()

# Delete all rows from the table
cursor.execute("DELETE FROM vocabulary")

# (Optional) reset the auto-increment counter if the table has an AUTOINCREMENT primary key
cursor.execute("DELETE FROM sqlite_sequence WHERE name='vocabulary'")

# Commit changes and close connection
conn.commit()
conn.close()

print("All entries deleted from 'vocabulary' table.")

