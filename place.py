import sqlite3
conn = sqlite3.connect('../results.db')
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES ('place','miesto','place.png')")
conn.commit()
conn.close()
