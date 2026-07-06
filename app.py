from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import pickle
import base64
from io import BytesIO

try:
    import numpy as np
    import face_recognition
    from PIL import Image

    CV_AVAILABLE = True
    CV_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    np = None
    face_recognition = None
    Image = None
    CV_AVAILABLE = False
    CV_IMPORT_ERROR = exc

app = Flask(__name__)
app.secret_key = os.getenv("FACEVOTE_SECRET_KEY", "dev-secret-key")
DB = 'database.db'

# ======================= DB INIT =======================

def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        voter_id TEXT UNIQUE NOT NULL,
                        aadhaar TEXT UNIQUE NOT NULL,
                        encoding BLOB NOT NULL,
                        has_voted INTEGER DEFAULT 0
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS candidates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        votes INTEGER DEFAULT 0
                    )''')
        # Add default candidates if empty
        c.execute("SELECT COUNT(*) FROM candidates")
        if c.fetchone()[0] == 0:
            c.executemany("INSERT INTO candidates (name) VALUES (?)",
                          [('Alice',), ('Bob',), ('Charlie',)])
            conn.commit()

# ======================= UTILS =======================

def decode_image(base64_data):
    if not CV_AVAILABLE or Image is None or np is None:
        raise RuntimeError("Face recognition dependencies are not installed.")
    image_data = base64.b64decode(base64_data.split(',')[1])
    image = Image.open(BytesIO(image_data)).convert('RGB')
    return np.array(image)

# ======================= ROUTES =======================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not CV_AVAILABLE:
            flash(f"Face recognition dependencies are unavailable: {CV_IMPORT_ERROR}", "warning")
            return redirect(url_for('register'))

        name = request.form['name']
        voter_id = request.form['voter_id']
        aadhaar = request.form['aadhaar']
        image_data = request.form['image_data']

        if not image_data:
            flash("No image captured.", "warning")
            return redirect(url_for('register'))

        rgb = decode_image(image_data)
        encodings = face_recognition.face_encodings(rgb)

        if not encodings:
            flash("No face detected. Try again.", "danger")
            return redirect(url_for('register'))

        encoding = encodings[0]

        # Check for duplicate face
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("SELECT encoding FROM users")
            for row in c.fetchall():
                existing = pickle.loads(row[0])
                match = face_recognition.compare_faces([existing], encoding, tolerance=0.5)
                if match[0]:
                    flash("Face already registered with another voter.", "danger")
                    return redirect(url_for('register'))

        try:
            with sqlite3.connect(DB) as conn:
                conn.execute('''INSERT INTO users (name, voter_id, aadhaar, encoding)
                                VALUES (?, ?, ?, ?)''',
                             (name, voter_id, aadhaar, pickle.dumps(encoding)))
                conn.commit()
                flash("Registered successfully! Please log in to vote.", "success")
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Voter ID or Aadhaar already exists.", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not CV_AVAILABLE:
            flash(f"Face recognition dependencies are unavailable: {CV_IMPORT_ERROR}", "warning")
            return redirect(url_for('login'))

        voter_id = request.form['voter_id']
        image_data = request.form['image_data']

        if not image_data:
            flash("No image provided for verification.", "danger")
            return redirect(url_for('login'))

        rgb = decode_image(image_data)
        encodings = face_recognition.face_encodings(rgb)

        if not encodings:
            flash("No face detected. Try again.", "warning")
            return redirect(url_for('login'))

        user = None
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("SELECT id, name, encoding, has_voted FROM users WHERE voter_id=?", (voter_id,))
            row = c.fetchone()
            if row:
                user = {
                    "id": row[0],
                    "name": row[1],
                    "encoding": pickle.loads(row[2]),
                    "has_voted": row[3]
                }

        if not user:
            flash("Voter ID not found.", "danger")
            return redirect(url_for('login'))

        match = face_recognition.compare_faces([user['encoding']], encodings[0])[0]

        if match:
            if user["has_voted"]:
                flash("You have already voted.", "warning")
                return redirect(url_for('login'))
            session['user_id'] = user['id']
            return redirect(url_for('vote'))
        else:
            flash("Face mismatch. Try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    with sqlite3.connect(DB) as conn:
        c = conn.cursor()

        # Ensure NOTA exists
        c.execute("SELECT id FROM candidates WHERE name='NOTA'")
        if not c.fetchone():
            c.execute("INSERT INTO candidates (name) VALUES ('NOTA')")
            conn.commit()

        # Check if user already voted
        c.execute("SELECT has_voted FROM users WHERE id=?", (user_id,))
        if c.fetchone()[0]:
            flash("Already voted.", "warning")
            return redirect(url_for('login'))

        if request.method == 'POST':
            selected = request.form['candidate']
            c.execute("UPDATE users SET has_voted=1 WHERE id=?", (user_id,))

            if selected == "NOTA":
                c.execute("UPDATE candidates SET votes = votes + 1 WHERE name='NOTA'")
            else:
                c.execute("UPDATE candidates SET votes = votes + 1 WHERE id=?", (selected,))
            conn.commit()
            flash("Vote recorded successfully!", "success")
            return redirect(url_for('success'))

        c.execute("SELECT id, name FROM candidates")
        candidates = c.fetchall()

    return render_template('vote.html', candidates=candidates)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/results')
def results():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        c.execute("SELECT name, votes FROM candidates ORDER BY votes DESC")
        results = c.fetchall()
    return render_template('results.html', results=results)

# ======================= MAIN =======================

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
