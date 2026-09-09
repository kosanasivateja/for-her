from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "for-her-secret-key"

socketio = SocketIO(app)


def init_db():
    connection = sqlite3.connect("forher.db")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personal_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        personal_id = request.form["personal_id"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        connection = sqlite3.connect("forher.db")

        try:
            connection.execute(
                "INSERT INTO users (personal_id, password) VALUES (?, ?)",
                (personal_id, password_hash)
            )

            connection.commit()
            message = "Account created successfully!"

        except sqlite3.IntegrityError:
            message = "This Personal ID already exists."

        connection.close()

        return render_template(
            "signup.html",
            message=message
        )

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        personal_id = request.form["personal_id"]
        password = request.form["password"]

        connection = sqlite3.connect("forher.db")

        user = connection.execute(
            "SELECT password FROM users WHERE personal_id = ?",
            (personal_id,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user[0], password):

            session["personal_id"] = personal_id

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            message="Invalid Personal ID or Password."
        )

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "personal_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        personal_id=session["personal_id"],
        search_result=None,
        searched_id=None
    )


@app.route("/search")
def search():

    if "personal_id" not in session:
        return redirect(url_for("login"))

    search_id = request.args.get(
        "personal_id",
        ""
    ).strip()

    connection = sqlite3.connect("forher.db")

    user = connection.execute(
        "SELECT personal_id FROM users WHERE personal_id = ?",
        (search_id,)
    ).fetchone()

    connection.close()

    return render_template(
        "dashboard.html",
        personal_id=session["personal_id"],
        search_result=user,
        searched_id=search_id
    )


@app.route("/chat/<other_user>")
def chat(other_user):

    if "personal_id" not in session:
        return redirect(url_for("login"))

    current_user = session["personal_id"]

    connection = sqlite3.connect("forher.db")

    messages = connection.execute(
        """
        SELECT sender, receiver, message
        FROM messages
        WHERE
            (sender = ? AND receiver = ?)
            OR
            (sender = ? AND receiver = ?)
        ORDER BY id ASC
        """,
        (
            current_user,
            other_user,
            other_user,
            current_user
        )
    ).fetchall()

    connection.close()

    return render_template(
        "chat.html",
        other_user=other_user,
        messages=messages
    )


# ==========================
# JOIN CHAT
# ==========================

@socketio.on("join_chat")
def handle_join(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")

    if not current_user or not other_user:
        return

    room = "_".join(
        sorted([current_user, other_user])
    )

    join_room(room)


# ==========================
# SEND MESSAGE
# ==========================

@socketio.on("send_message")
def handle_message(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")
    message = data.get("message", "").strip()

    if not current_user or not other_user or not message:
        return

    connection = sqlite3.connect("forher.db")

    connection.execute(
        """
        INSERT INTO messages
        (sender, receiver, message)
        VALUES (?, ?, ?)
        """,
        (
            current_user,
            other_user,
            message
        )
    )

    connection.commit()
    connection.close()

    room = "_".join(
        sorted([current_user, other_user])
    )

    emit(
        "receive_message",
        {
            "sender": current_user,
            "message": message
        },
        to=room
    )


# ==========================
# CALL OFFER
# ==========================

@socketio.on("call_offer")
def handle_call_offer(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")

    if not current_user or not other_user:
        return

    room = "_".join(
        sorted([current_user, other_user])
    )

    emit(
        "call_offer",
        {
            "sender": current_user,
            "offer": data.get("offer")
        },
        to=room,
        include_self=False
    )


# ==========================
# CALL ANSWER
# ==========================

@socketio.on("call_answer")
def handle_call_answer(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")

    if not current_user or not other_user:
        return

    room = "_".join(
        sorted([current_user, other_user])
    )

    emit(
        "call_answer",
        {
            "sender": current_user,
            "answer": data.get("answer")
        },
        to=room,
        include_self=False
    )


# ==========================
# ICE CANDIDATE
# ==========================

@socketio.on("ice_candidate")
def handle_ice_candidate(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")

    if not current_user or not other_user:
        return

    room = "_".join(
        sorted([current_user, other_user])
    )

    emit(
        "ice_candidate",
        {
            "sender": current_user,
            "candidate": data.get("candidate")
        },
        to=room,
        include_self=False
    )


# ==========================
# END CALL
# ==========================

@socketio.on("end_call")
def handle_end_call(data):

    current_user = session.get("personal_id")
    other_user = data.get("other_user")

    if not current_user or not other_user:
        return

    room = "_".join(
        sorted([current_user, other_user])
    )

    emit(
        "end_call",
        {
            "sender": current_user
        },
        to=room,
        include_self=False
    )


# ==========================
# START SERVER
# ==========================

# Initialize database when the application starts
init_db()


if __name__ == "__main__":

    socketio.run(
        app,
        debug=True
    )