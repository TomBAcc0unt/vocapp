from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os, random, sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'secret123')

DB = 'results.db'
RUN_SIZE = 10


# --- Initialize DB ---
def init_db():
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()

        cur.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT NOT NULL,
                slovak TEXT NOT NULL,
                image TEXT NOT NULL
            )
        ''')

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

        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user TEXT PRIMARY KEY,
                breadcrumbs INTEGER DEFAULT 0,
                cheese INTEGER DEFAULT 0,
                happiness INTEGER DEFAULT 50,
                fullness_bread INTEGER DEFAULT 50,
                fullness_cheese INTEGER DEFAULT 50
            )
        ''')
    print("Database initialized or verified.")


# --- Migration for old schemas ---
def migrate_db():
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in cur.fetchall()}

        added = []
        if 'fullness_bread' not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN fullness_bread INTEGER DEFAULT 50")
            added.append('fullness_bread')
        if 'fullness_cheese' not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN fullness_cheese INTEGER DEFAULT 50")
            added.append('fullness_cheese')

        if added:
            print("Added columns:", ', '.join(added))
        else:
            print("No migration needed.")


init_db()
migrate_db()


def get_db():
    return sqlite3.connect(DB)


# --- Login ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        if not username:
            return render_template('login.html', error='Please enter a name')
        session['user'] = username

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user FROM users WHERE user=?", (username,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (user, breadcrumbs, cheese, happiness, fullness_bread, fullness_cheese)
                    VALUES (?, 0, 0, 50, 50, 50)
                """, (username,))
                conn.commit()

        return redirect(url_for('quiz'))

    return render_template('login.html')


# --- Vocabulary Quiz (breadcrumbs) ---
@app.route('/quiz')
def quiz():
    if 'user' not in session:
        return redirect('/')

    user = session['user']

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(run_id) FROM results WHERE user=?", (user,))
        last_run = cur.fetchone()[0]
        run_id = 1 if last_run is None else last_run + 1

        cur.execute("SELECT id, english, slovak, image FROM vocabulary ORDER BY RANDOM() LIMIT ?", (RUN_SIZE,))
        words = cur.fetchall()

        cur.execute("SELECT breadcrumbs, cheese FROM users WHERE user=?", (user,))
        row = cur.fetchone()
        breadcrumbs, cheese = row if row else (0, 0)

    session['current_run'] = {'run_id': run_id, 'words': words}
    return render_template('quiz.html', words=words, run_id=run_id, breadcrumbs=breadcrumbs, cheese=cheese)


@app.route('/check', methods=['POST'])
def check():
    data = request.json
    guess = data.get('guess', '').strip().lower()
    index = int(data.get('index', 0))
    run_info = session.get('current_run')
    if not run_info:
        return jsonify({'error': 'Run info missing'}), 400

    run_id = run_info['run_id']
    words = run_info['words']
    if index < 0 or index >= len(words):
        return jsonify({'error': 'Index out of range'}), 400

    word_id, english, slovak, image = words[index]
    correct = 1 if english.lower() == guess else 0

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO results (user, run_id, word_id, correct, user_guess) VALUES (?, ?, ?, ?, ?)",
            (session['user'], run_id, word_id, correct, guess)
        )
        if correct:
            cur.execute("UPDATE users SET breadcrumbs = breadcrumbs + 1 WHERE user=?", (session['user'],))
        conn.commit()
        cur.execute("SELECT breadcrumbs, cheese FROM users WHERE user=?", (session['user'],))
        breadcrumbs, cheese = cur.fetchone() or (0, 0)

    return jsonify({'correct': bool(correct), 'correct_answer': english, 'breadcrumbs': breadcrumbs, 'cheese': cheese})


# --- Math Quiz (cheese) ---
@app.route('/cheese')
def cheese_quiz():
    if 'user' not in session:
        return redirect('/')

    user = session['user']

    problems = []
    for i in range(RUN_SIZE):
        a = random.randint(0, 10)
        b = random.randint(4, 10)
        question = f"{a} * {b}"
        answer = a * b
        problems.append({'question': question, 'answer': answer})

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT breadcrumbs, cheese FROM users WHERE user=?", (user,))
        breadcrumbs, cheese = cur.fetchone() or (0, 0)

    session['cheese_run'] = {'problems': [p['answer'] for p in problems]}
    return render_template('cheese.html', problems=[p['question'] for p in problems],
                           breadcrumbs=breadcrumbs, cheese=cheese)


@app.route('/check_cheese', methods=['POST'])
def check_cheese():
    data = request.json
    try:
        guess = int(data.get('guess'))
    except Exception:
        return jsonify({'error': 'Invalid guess; must be a number'}), 400
    index = int(data.get('index', 0))
    run_info = session.get('cheese_run')
    if not run_info:
        return jsonify({'error': 'No cheese run found'}), 400

    problems = run_info.get('problems', [])
    if index < 0 or index >= len(problems):
        return jsonify({'error': 'Index out of range'}), 400

    correct_answer = problems[index]
    correct = 1 if guess == correct_answer else 0

    with get_db() as conn:
        cur = conn.cursor()
        if correct:
            cur.execute("UPDATE users SET cheese = cheese + 1 WHERE user=?", (session['user'],))
        conn.commit()
        cur.execute("SELECT breadcrumbs, cheese FROM users WHERE user=?", (session['user'],))
        breadcrumbs, cheese = cur.fetchone() or (0, 0)

    return jsonify({'correct': bool(correct), 'correct_answer': correct_answer,
                    'breadcrumbs': breadcrumbs, 'cheese': cheese})


# --- History page ---
@app.route('/history')
def history():
    user = session.get('user')
    if not user:
        return redirect('/')

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT run_id, SUM(correct) as score
            FROM results
            WHERE user=?
            GROUP BY run_id
            ORDER BY run_id DESC
            LIMIT 10
        """, (user,))
        runs = cur.fetchall()

        run_details = []
        for run_id, score in runs:
            cur.execute("""
                SELECT v.english, v.slovak, v.image, r.user_guess, r.correct
                FROM results r
                JOIN vocabulary v ON v.id = r.word_id
                WHERE r.user=? AND r.run_id=?
                ORDER BY r.id ASC
            """, (user, run_id))
            entries = cur.fetchall()
            run_details.append({'run_id': run_id, 'score': score, 'entries': entries})

        cur.execute("SELECT breadcrumbs, cheese, happiness, fullness_bread, fullness_cheese FROM users WHERE user=?", (user,))
        row = cur.fetchone()
        breadcrumbs, cheese, happiness, fullness_bread, fullness_cheese = row if row else (0, 0, 50, 50, 50)

    return render_template('history.html', runs=run_details,
                           breadcrumbs=breadcrumbs, cheese=cheese,
                           happiness=happiness,
                           fullness_bread=fullness_bread, fullness_cheese=fullness_cheese)


# --- Pet page ---
@app.route('/pet')
def pet_page():
    if 'user' not in session:
        return redirect('/')

    user = session['user']

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT breadcrumbs, cheese, happiness, fullness_bread, fullness_cheese FROM users WHERE user=?", (user,))
        row = cur.fetchone()
        if row:
            breadcrumbs, cheese, happiness, fullness_bread, fullness_cheese = row
        else:
            breadcrumbs = cheese = 0
            happiness = fullness_bread = fullness_cheese = 50

    return render_template('pet.html',
                           breadcrumbs=breadcrumbs,
                           cheese=cheese,
                           happiness=happiness,
                           fullness_bread=fullness_bread,
                           fullness_cheese=fullness_cheese)


# --- Pet actions ---
@app.route('/pet_action', methods=['POST'])
def pet_action():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    data = request.json
    action = data.get('action')
    user = session['user']

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT breadcrumbs, cheese, fullness_bread, fullness_cheese, happiness FROM users WHERE user=?", (user,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'User not found'}), 404

        breadcrumbs, cheese, fullness_bread, fullness_cheese, happiness = row

        if action == 'feed_bread':
            if breadcrumbs <= 0:
                return jsonify({'error': 'No breadcrumbs to feed'}), 400
            breadcrumbs -= 1
            fullness_bread = min(100, fullness_bread + 10)
        elif action == 'feed_cheese':
            if cheese <= 0:
                return jsonify({'error': 'No cheese to feed'}), 400
            cheese -= 1
            fullness_cheese = min(100, fullness_cheese + 10)
        elif action == 'pet':
            happiness = min(100, happiness + 10)
        else:
            return jsonify({'error': 'Unknown action'}), 400

        cur.execute("""
            UPDATE users
            SET breadcrumbs=?, cheese=?, fullness_bread=?, fullness_cheese=?, happiness=?
            WHERE user=?
        """, (breadcrumbs, cheese, fullness_bread, fullness_cheese, happiness, user))
        conn.commit()

        return jsonify({
            'breadcrumbs': breadcrumbs,
            'cheese': cheese,
            'fullness_bread': fullness_bread,
            'fullness_cheese': fullness_cheese,
            'happiness': happiness
        })


# --- Run server ---
if __name__ == '__main__':
    app.run(debug=True)
