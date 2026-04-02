from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os, random, sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'secret123')

DB = 'results.db'
RUN_SIZE = 10
IMAGE_FOLDER = 'static/images'


# --- Initialize DB ---
def init_db():
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


# --- Migration: split last_fed into 3 new columns ---
def migrate_db():
    print("No migration needed")

init_db()
migrate_db()

# --- Helper: DB connection ---
def get_db():
    return sqlite3.connect(DB)

# --- update resources ---
@app.context_processor
def inject_user_resources():
    """Automatically provide breadcrumb and cheese counters to all templates."""
    if 'user' not in session:
        return {}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT breadcrumbs_inventory, cheese_inventory, happiness
            FROM users
            WHERE user = ?
        """, (session['user'],))
        row = cur.fetchone()
        if row:
            breadcrumbs_inventory, cheese_inventory, happiness = row
        else:
            breadcrumbs_inventory, cheese_inventory, happiness = 0, 0, 50

    return {
        'breadcrumbs': breadcrumbs_inventory,
        'cheese': cheese_inventory,
        'happiness': happiness
    }

# --- Hunger decay system ---
def apply_hunger_decay(username):
    """Deduct 1 per hour from each reward since last fed."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT breadcrumbs_fullness, cheese_fullness, happiness,
                   breadcrumbs_last_fed, cheese_last_fed, happiness_last_fed
            FROM users WHERE user=?
        """, (username,))
        row = cur.fetchone()
        if not row:
            return

        breadcrumbs, cheese, happiness, lb_ts, lc_ts, lh_ts = row

        def parse_ts(ts):
            if not ts:
                return None
            try:
                return datetime.fromisoformat(ts)
            except:
                try:
                    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except:
                    return None

        now = datetime.utcnow()

        def decay(value, ts_str):
            ts = parse_ts(ts_str)
            if not ts:
                return value, now.isoformat()
            hours = int((now - ts).total_seconds() // 5400)
            if hours <= 0:
                return value, ts_str
            new_val = max(0, (value or 0) - hours)
            new_ts = (ts + timedelta(hours=hours)).isoformat()
            return new_val, new_ts

        breadcrumbs, lb_ts = decay(breadcrumbs, lb_ts)
        cheese, lc_ts = decay(cheese, lc_ts)
        happiness, lh_ts = decay(happiness, lh_ts)

        cur.execute("""
            UPDATE users
            SET breadcrumbs_fullness=?, cheese_fullness=?, happiness=?,
                breadcrumbs_last_fed=?, cheese_last_fed=?, happiness_last_fed=?
            WHERE user=?
        """, (breadcrumbs, cheese, happiness, lb_ts, lc_ts, lh_ts, username))
        conn.commit()

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
                    INSERT INTO users (user, breadcrumbs_inventory, breadcrumbs_fullness, cheese_inventory, cheese_fullness, happiness)
                    VALUES (?, 0, 50, 0, 50, 50)
                """, (username,))
                conn.commit()

        return redirect(url_for('quiz'))

    return render_template('login.html')


# --- Vocabulary quiz ---
@app.route('/quiz')
def quiz():
    if 'user' not in session:
        return redirect('/')

    user = session['user']
    apply_hunger_decay(user)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(run_id) FROM results WHERE user=?", (user,))
        last_run = cur.fetchone()[0]
        run_id = 1 if last_run is None else last_run + 1

        cur.execute("SELECT id, english, slovak, image FROM vocabulary ORDER BY RANDOM() LIMIT ?", (RUN_SIZE,))
        words = cur.fetchall()

        # Determine if each word was wrong in the *last* attempt only
        words_with_bonus = []
        for w in words:
            word_id = w[0]
            cur.execute("""
                SELECT correct
                FROM results
                WHERE user=? AND word_id=?
                ORDER BY run_id DESC, id DESC
                LIMIT 1
            """, (user, word_id))
            last_result = cur.fetchone()
            was_last_wrong = (last_result is not None and last_result[0] == 0)
            words_with_bonus.append((w[0], w[1], w[2], w[3], was_last_wrong))

    session['current_run'] = {'run_id': run_id, 'words': words_with_bonus}
    return render_template('quiz.html', words=words_with_bonus, run_id=run_id)

# --- Check vocab answer ---
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

    word_id, english, slovak, image, bonus = words[index]
    correct = 1 if english.lower() == guess else 0

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO results (user, run_id, word_id, correct, user_guess) VALUES (?, ?, ?, ?, ?)",
            (session['user'], run_id, word_id, correct, guess)
        )

        if correct:
            reward = 3 if bonus else 1
            cur.execute("UPDATE users SET breadcrumbs_inventory = breadcrumbs_inventory + ? WHERE user=?", (reward, session['user']))
        conn.commit()
        cur.execute("SELECT breadcrumbs_inventory, cheese_inventory FROM users WHERE user=?", (session['user'],))
        breadcrumbs_inventory, cheese_inventory = cur.fetchone() or (0, 0)

    return jsonify({'correct': bool(correct), 'correct_answer': english, 'breadcrumbs': breadcrumbs_inventory, 'cheese': cheese_inventory})


# --- Math (cheese) quiz ---
@app.route('/cheese')
def cheese_quiz():
    if 'user' not in session:
        return redirect('/')

    user = session['user']
    apply_hunger_decay(user)

    problems = []
    for i in range(RUN_SIZE):
        a = random.randint(0, 10)
        b = random.randint(4, 10)
        question = f"{a} * {b}"
        answer = a * b
        problems.append({'question': question, 'answer': answer})

    session['cheese_run'] = {'problems': [p['answer'] for p in problems]}
    return render_template('cheese.html', problems=[p['question'] for p in problems])

# --- Check cheese answer ---
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
            cur.execute("UPDATE users SET cheese_inventory = cheese_inventory + 1 WHERE user=?", (session['user'],))
        conn.commit()
        cur.execute("SELECT breadcrumbs_inventory, cheese_inventory FROM users WHERE user=?", (session['user'],))
        breadcrumbs_inventory, cheese_inventory = cur.fetchone() or (0, 0)

    return jsonify({'correct': bool(correct), 'correct_answer': correct_answer, 'breadcrumbs': breadcrumbs_inventory, 'cheese': cheese_inventory})

# --- Competition Mode ---
@app.route('/competition', methods=['GET', 'POST'])
def competition():
    if 'user' not in session:
        return redirect('/')

    user1 = session['user']

    if request.method == 'POST':
        user2 = request.form['player2'].strip()
        if not user2:
            return redirect(url_for('competition'))
        session['player2'] = user2
    else:
        user2 = session.get('player2')

    with get_db() as conn:
        cur = conn.cursor()

        # ✅ Ensure player2 exists in DB (same as login)
        if user2:
            cur.execute("SELECT user FROM users WHERE user=?", (user2,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (user, breadcrumbs_inventory, breadcrumbs_fullness, cheese_inventory, cheese_fullness, happiness)
                    VALUES (?, 0, 50, 0, 50, 50)
                """, (user2,))
                conn.commit()

        # Apply hunger decay
        apply_hunger_decay(user1)
        if user2:
            apply_hunger_decay(user2)

        # Get run_id
        cur.execute("SELECT MAX(run_id) FROM results WHERE user=?", (user1,))
        last_run = cur.fetchone()[0]
        run_id = 1 if last_run is None else last_run + 1

        # Get words
        cur.execute(
            "SELECT id, english, slovak, image FROM vocabulary ORDER BY RANDOM() LIMIT ?",
            (RUN_SIZE,)
        )
        words = cur.fetchall()

    # Assign turns
    words_with_turns = []
    for w in words:
        starter = random.choice([user1, user2 if user2 else user1])
        words_with_turns.append((*w, starter))

    # Initialize session
    session['competition'] = {
        'run_id': run_id,
        'words': words_with_turns,
        'user1': user1,
        'user2': user2,
        'breadcrumbs': {
            user1: 0,
            user2: 0 if user2 else 0
        }
    }

    return render_template(
        'competition.html',
        words=words_with_turns,
        run_id=run_id,
        user1=user1,
        user2=user2 if user2 else "Player 2",
        breadcrumbs=0,
        breadcrumbs_user1=0,
        breadcrumbs_user2=0
    )

# --- Check competition answer ---
@app.route('/check_competition', methods=['POST'])
def check_competition():
    if 'competition' not in session:
        return jsonify({"error": "Competition not started"}), 400

    data = request.get_json()
    run_id = int(data.get('run_id', 0))
    index = int(data.get('index', 0))
    guess = data.get('guess', '').strip().lower()
    player = data.get('player')

    comp = session['competition']
    words = comp['words']
    user1 = comp['user1']
    user2 = comp['user2']

    if index < 0 or index >= len(words):
        return jsonify({"error": "Index out of range"}), 400

    word_id, english, slovak, image, starter = words[index]
    correct = english.lower() == guess

    with get_db() as conn:
        cur = conn.cursor()

        # ✅ Ensure player exists (extra safety)
        cur.execute("SELECT user FROM users WHERE user=?", (player,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO users (user, breadcrumbs_inventory, breadcrumbs_fullness, cheese_inventory, cheese_fullness, happiness)
                VALUES (?, 0, 50, 0, 50, 50)
            """, (player,))

        # Save result
        cur.execute(
            "INSERT INTO results (user, run_id, word_id, correct, user_guess) VALUES (?, ?, ?, ?, ?)",
            (player, run_id, word_id, int(correct), guess)
        )

        # Update breadcrumbs ONLY for answering player
        if correct:
            cur.execute(
                "UPDATE users SET breadcrumbs_inventory = breadcrumbs_inventory + 1 WHERE user=?",
                (player,)
            )

        conn.commit()

        # Fetch player1
        cur.execute(
            "SELECT breadcrumbs_inventory, cheese_inventory FROM users WHERE user=?",
            (user1,)
        )
        row1 = cur.fetchone()
        user1_b, user1_c = row1 if row1 else (0, 0)

        # Fetch player2
        cur.execute(
            "SELECT breadcrumbs_inventory FROM users WHERE user=?",
            (user2,)
        )
        row2 = cur.fetchone()
        user2_b = row2[0] if row2 else 0

    # Update session
    comp['breadcrumbs'][user1] = user1_b
    comp['breadcrumbs'][user2] = user2_b
    session['competition'] = comp

    return jsonify({
        "correct": correct,
        "correct_answer": english,

        # Player boxes
        "breadcrumbs_user1": user1_b,
        "breadcrumbs_user2": user2_b,

        # Header (ONLY player1)
        "breadcrumbs": user1_b,
        "cheese": user1_c
    })


# --- History page ---
@app.route('/history')
def history():
    user = session.get('user')
    if not user:
        return redirect('/')

    apply_hunger_decay(user)

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

    return render_template('history.html', runs=run_details)


# --- Pet page ---
@app.route('/pet')
def pet_page():
    if 'user' not in session:
        return redirect('/')

    user = session['user']
    apply_hunger_decay(user)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT breadcrumbs_fullness, cheese_fullness, happiness,
                   breadcrumbs_last_fed, cheese_last_fed, happiness_last_fed
            FROM users WHERE user=?
        """, (user,))
        row = cur.fetchone()
        if row:
            breadcrumbs_fullness, cheese_fullness, happiness, lb_ts, lc_ts, lh_ts = row
        else:
            breadcrumbs_fullness = cheese_fullness = happiness = 50            
            lb_ts = lc_ts = lh_ts = datetime.utcnow().isoformat()

    return render_template(
        'pet.html',
        breadcrumbs_fullness=breadcrumbs_fullness,        
        cheese_fullness=cheese_fullness,
        happiness=happiness,
        last_breadcrumb_fed=lb_ts,
        last_cheese_fed=lc_ts,
        last_happiness_fed=lh_ts
    )


@app.route('/pet_action', methods=['POST'])
def pet_action():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    data = request.json
    action = data.get('action')
    user = session['user']

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT breadcrumbs_inventory, breadcrumbs_fullness,
                   cheese_inventory, cheese_fullness, happiness
            FROM users WHERE user=?
        """, (user,))
        breadcrumbs_inventory, breadcrumbs_fullness, cheese_inventory, cheese_fullness, happiness = cur.fetchone() or (0, 50, 0, 50, 50)

        now = datetime.utcnow().isoformat()

        if action == 'pet':
            happiness = min(100, (happiness or 0) + 1)
            cur.execute("UPDATE users SET happiness=?, happiness_last_fed=? WHERE user=?", (happiness, now, user))

        elif action == 'feed_bread':
            if breadcrumbs_inventory <= 0:
                return jsonify({'error': 'No breadcrumbs to feed'}), 400
            breadcrumbs_inventory -= 1
            breadcrumbs_fullness = min(100, (breadcrumbs_fullness or 0) + 1)
            cur.execute("""
                UPDATE users SET breadcrumbs_inventory=?, breadcrumbs_fullness=?, breadcrumbs_last_fed=?
                WHERE user=?
            """, (breadcrumbs_inventory, breadcrumbs_fullness, now, user))

        elif action == 'feed_cheese':
            if cheese_inventory <= 0:
                return jsonify({'error': 'No cheese to feed'}), 400
            cheese_inventory -= 1
            cheese_fullness = min(100, (cheese_fullness or 0) + 1)
            cur.execute("""
                UPDATE users SET cheese_inventory=?, cheese_fullness=?, cheese_last_fed=?
                WHERE user=?
            """, (cheese_inventory, cheese_fullness, now, user))
        else:
            return jsonify({'error': 'Unknown action'}), 400

        conn.commit()

        # Re-fetch latest values after update
        cur.execute("""
            SELECT breadcrumbs_inventory, breadcrumbs_fullness,
                   cheese_inventory, cheese_fullness, happiness
            FROM users WHERE user=?
        """, (user,))
        breadcrumbs_inventory, breadcrumbs_fullness, cheese_inventory, cheese_fullness, happiness = cur.fetchone()

    # Return live values for JS to update bars/counters
    return jsonify({
        'breadcrumbs': breadcrumbs_inventory,
        'cheese': cheese_inventory,
        'happiness': happiness,
        'breadcrumbs_fullness': breadcrumbs_fullness,
        'cheese_fullness': cheese_fullness
    })

@app.route('/perfect_run_reward', methods=['POST'])
def perfect_run_reward():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    user = session['user']
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET breadcrumbs_inventory = breadcrumbs_inventory + 5 WHERE user=?", (user,))
        conn.commit()
        cur.execute("SELECT breadcrumbs_inventory FROM users WHERE user=?", (user,))
        breadcrumbs_inventory = cur.fetchone()[0]

    return jsonify({'breadcrumbs': breadcrumbs_inventory})


# --- Start Flask server ---
if __name__ == '__main__':
    app.run(debug=True)
