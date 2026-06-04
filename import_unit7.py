import sqlite3
conn = sqlite3.connect('../results.db')


conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("baseball", "bejsbal", "baseball.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("badminton", "bedminton", "badminton.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("gymnastics", "gymnastika", "gymnastics.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("hockey", "hokej", "hockey.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("basketball", "basket", "basketball.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("football", "futbal", "football.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("tennis", "tenis", "tennis.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("judo", "džudo", "judo.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("chess", "šach", "chess.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("table tennis", "ping pong", "table_tennis.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("volleyball", "volejbal", "volleyball.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("half", "polovica", "half.png"))
conn.execute("INSERT INTO vocabulary (english, slovak, image) VALUES (?, ?, ?)", ("quarters", "štvrtiny", "quarters.png"))

conn.commit()
conn.close()
