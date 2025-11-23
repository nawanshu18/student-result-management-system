# app.py - Student Result Management (complete, merged, ready-to-run)

import sqlite3
from datetime import datetime
import hashlib
import io
import os
import csv
import random
import smtplib
from email.message import EmailMessage
from typing import List, Dict

import streamlit as st
try:
    import pandas as pd
except Exception:
    st.error("This app requires pandas. Install with `pip install pandas`.")
    raise

# Optional libs (reportlab for PDF)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ---------------- Configuration ----------------
DB_PATH = "student_db.sqlite"
DEFAULT_ADMIN_EMAIL = "nawanshulahane2005@gmail.com"
OTP_TTL_SECONDS = 300  # 5 minutes

# ---------------- Utilities ----------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ---------------- Database helpers ----------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        roll TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        class TEXT NOT NULL,
        dob TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll TEXT NOT NULL,
        subject TEXT NOT NULL,
        exam_type TEXT NOT NULL,
        marks INTEGER NOT NULL,
        max_marks INTEGER DEFAULT 100,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (roll) REFERENCES students(roll) ON DELETE CASCADE
    );""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        email TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_security (
        username TEXT PRIMARY KEY,
        question TEXT,
        answer_hash TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );""")
    conn.commit()
    conn.close()

def upgrade_marks_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(marks);")
    cols = [c[1] for c in cur.fetchall()]
    if "max_marks" not in cols:
        cur.execute("ALTER TABLE marks ADD COLUMN max_marks INTEGER DEFAULT 100;")
        conn.commit()
    conn.close()

def upgrade_students_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(students);")
    cols = [c[1] for c in cur.fetchall()]
    if "dob" not in cols:
        cur.execute("ALTER TABLE students ADD COLUMN dob TEXT DEFAULT '';")
        conn.commit()
    conn.close()

def upgrade_admins_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(admins);")
    cols = [c[1] for c in cur.fetchall()]
    if "email" not in cols:
        cur.execute("ALTER TABLE admins ADD COLUMN email TEXT DEFAULT '';")
        conn.commit()
    conn.close()

def init_default_admin():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM admins;")
    if cur.fetchone()[0] == 0:
        default_pw = hash_password("admin123")
        cur.execute("INSERT INTO admins (username, password_hash, email) VALUES (?, ?, ?);",
                    ("admin", default_pw, DEFAULT_ADMIN_EMAIL))
        conn.commit()
    conn.close()

# ---------------- Admin helpers ----------------
def verify_admin(username: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM admins WHERE username = ?;", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return hash_password(password) == row[0]

def change_admin_password(username: str, new_password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE admins SET password_hash = ? WHERE username = ?;", (hash_password(new_password), username))
    conn.commit()
    conn.close()

def set_admin_email(username: str, email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE admins SET email = ? WHERE username = ?;", (email, username))
    conn.commit()
    conn.close()

def get_admin_email(username: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email FROM admins WHERE username = ?;", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

def set_security_question(username: str, question: str, answer: str):
    conn = get_conn()
    cur = conn.cursor()
    ah = hash_password(answer.strip().lower())
    cur.execute("INSERT OR REPLACE INTO admin_security (username, question, answer_hash) VALUES (?, ?, ?);", (username, question, ah))
    conn.commit()
    conn.close()

def get_security_question(username: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT question FROM admin_security WHERE username = ?;", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""

def verify_security_answer(username: str, answer: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT answer_hash FROM admin_security WHERE username = ?;", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return hash_password(answer.strip().lower()) == row[0]

# ---------------- Students / marks ----------------
def add_student(roll, name, cls, dob=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO students (roll, name, class, dob) VALUES (?, ?, ?, ?);", (str(roll), name, cls, dob))
    conn.commit()
    conn.close()

def delete_student(roll):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE roll = ?;", (str(roll),))
    conn.commit()
    conn.close()

def add_mark(roll, subject, exam_type, marks, max_marks=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO marks (roll, subject, exam_type, marks, max_marks) VALUES (?, ?, ?, ?, ?);",
                (str(roll), subject, exam_type, int(marks), int(max_marks)))
    conn.commit()
    conn.close()

def get_all_students():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM students ORDER BY roll;", conn)
    conn.close()
    return df

def get_all_marks():
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, roll, subject, exam_type, marks, COALESCE(max_marks,100) as max_marks, created_at FROM marks ORDER BY id;", conn)
    conn.close()
    return df

def update_mark(mark_id, marks):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE marks SET marks = ? WHERE id = ?;", (int(marks), int(mark_id)))
    conn.commit()
    conn.close()

def delete_mark(mark_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM marks WHERE id = ?;", (int(mark_id),))
    conn.commit()
    conn.close()

def get_student_result(roll):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.roll, s.name, s.class, m.subject, m.exam_type, m.marks, COALESCE(m.max_marks,100)
        FROM students s LEFT JOIN marks m ON s.roll = m.roll
        WHERE s.roll = ?;
    """, (str(roll),))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    student_info = {"roll": rows[0][0], "name": rows[0][1], "class": rows[0][2]}
    marks_rows = [ {"subject": r[3], "exam_type": r[4], "marks": r[5], "max_marks": r[6]} for r in rows if r[3] is not None ]
    total = sum(m['marks'] for m in marks_rows) if marks_rows else 0
    total_possible = sum(m['max_marks'] for m in marks_rows) if marks_rows else 0
    percentage = round((total / total_possible * 100), 2) if total_possible else 0
    return {"student": student_info, "marks": marks_rows, "total": total, "total_possible": total_possible, "count": len(marks_rows), "percentage": percentage}

def subject_averages():
    conn = get_conn()
    df = pd.read_sql_query("SELECT subject, AVG(marks * 100.0 / max_marks) as avg_marks, COUNT(*) as count FROM marks GROUP BY subject ORDER BY subject;", conn)
    conn.close()
    return df

# ---------------- Bulk insert helpers ----------------
def bulk_insert_students_from_df(df: pd.DataFrame):
    for _, row in df.iterrows():
        add_student(str(row['roll']), str(row['name']), str(row['class']), str(row.get('dob','')))

def bulk_insert_marks_from_df(df: pd.DataFrame):
    for _, row in df.iterrows():
        mm = int(row['max_marks']) if 'max_marks' in row and pd.notna(row['max_marks']) else 100
        add_mark(str(row['roll']), str(row['subject']), str(row['exam_type']), int(row['marks']), mm)

# ---------------- OTP helpers (email) ----------------
def _generate_otp(n=6):
    return "".join(str(random.randint(0,9)) for _ in range(n))

def send_otp_email(to_email: str, otp: str) -> bool:
    server = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASSWORD")
    if not (server and port and user and pwd and to_email):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = "Your admin OTP"
        msg["From"] = user
        msg["To"] = to_email
        msg.set_content(f"Your OTP for admin login is: {otp}\nThis OTP is valid for {OTP_TTL_SECONDS // 60} minutes.")
        with smtplib.SMTP_SSL(server, int(port)) as smtp:
            smtp.login(user, pwd)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("OTP email send failed:", e)
        return False

def start_otp_flow(username: str):
    otp = _generate_otp(6)
    key = f"otp_{username}"
    st.session_state[key] = {"otp": otp, "created_at": datetime.now()}
    email = get_admin_email(username)
    sent = False
    info = ""
    if email:
        sent = send_otp_email(email, otp)
        if sent:
            info = f"OTP sent to {email} (check spam)."
        else:
            info = "Failed to send email OTP (SMTP not configured or failed). OTP shown below for testing."
    else:
        info = "No email set for this admin. OTP shown below for testing."
    if not sent:
        info += f" OTP: {otp}"
    return sent, info

def verify_otp(username: str, otp_input: str) -> bool:
    key = f"otp_{username}"
    if key not in st.session_state:
        return False
    rec = st.session_state[key]
    otp = rec.get("otp")
    created = rec.get("created_at")
    if not otp or not created:
        return False
    if (datetime.now() - created).total_seconds() > OTP_TTL_SECONDS:
        del st.session_state[key]
        return False
    if str(otp_input).strip() == str(otp):
        del st.session_state[key]
        return True
    return False

# ---------------- Report generation ----------------
def make_student_html_report(result: dict) -> str:
    student = result['student']
    marks = result['marks']
    total = result['total']
    total_possible = result['total_possible']
    percentage = result['percentage']
    now = now_str()
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Report - {student['name']}</title>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 20px; }}
      .card {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 16px; border-radius:8px; max-width:900px; }}
      table {{ width:100%; border-collapse: collapse; margin-top: 12px; }}
      th, td {{ padding:8px; border-bottom:1px solid #ddd; text-align:left; }}
      .meta {{ color:#555; font-size:0.9rem; }}
    </style>
    </head>
    <body>
      <div class='card'>
        <h2>Student Result</h2>
        <p class='meta'>Generated: {now}</p>
        <h3>{student['name']} (Roll: {student['roll']}) - Class: {student['class']}</h3>
        <table>
          <thead><tr><th>Subject</th><th>Exam</th><th>Marks</th><th>Max Marks</th></tr></thead><tbody>
    """
    for m in marks:
        html += f"<tr><td>{m['subject']}</td><td>{m['exam_type']}</td><td>{m['marks']}</td><td>{m['max_marks']}</td></tr>"
    html += f"""
          </tbody>
        </table>
        <p><strong>Total:</strong> {total} / {total_possible} &nbsp;&nbsp; <strong>Percentage:</strong> {percentage}%</p>
      </div>
    </body>
    </html>
    """
    return html

def make_student_pdf_bytes(result: dict) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab not installed")
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    student = result['student']
    marks = result['marks']
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 750, f"Student Result - {student['name']}")
    c.setFont("Helvetica", 10)
    c.drawString(40, 735, f"Roll: {student['roll']}    Class: {student['class']}")
    y = 710
    c.drawString(40, y, "Subject")
    c.drawString(240, y, "Exam")
    c.drawString(380, y, "Marks")
    c.drawString(460, y, "Max")
    y -= 15
    for m in marks:
        c.drawString(40, y, str(m['subject']))
        c.drawString(240, y, str(m['exam_type']))
        c.drawString(380, y, str(m['marks']))
        c.drawString(460, y, str(m['max_marks']))
        y -= 15
        if y < 50:
            c.showPage()
            y = 750
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# ---------------- UI helpers / Theme / CSS ----------------
def set_page_style():
    dark = st.session_state.get("dark_mode", True)
    if dark:
        bg = "linear-gradient(135deg, #071021 0%, #0b2233 50%, #0f3850 100%)"
        card_bg = "rgba(255,255,255,0.03)"
        text = "#e6eef8"
        sub = "#9fb3d1"
        accent = "#8b5cf6"
        glow = "rgba(139,92,246,0.15)"
    else:
        bg = "linear-gradient(135deg, #f7fafc 0%, #eef2ff 50%, #ffffff 100%)"
        card_bg = "white"
        text = "#0b2946"
        sub = "#375a7f"
        accent = "#2563eb"
        glow = "rgba(37,99,235,0.08)"

    st.markdown(f"""
    <style>
    :root {{
      --bg: {bg};
      --card-bg: {card_bg};
      --text: {text};
      --sub: {sub};
      --accent: {accent};
      --glow: {glow};
    }}
    .stApp {{
        background: var(--bg);
        color: var(--text) !important;
        font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    }}
    .card {{
        background: var(--card-bg);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 10px 30px rgba(2,6,23,0.12), 0 0 40px var(--glow);
        color: var(--text) !important;
        transition: transform 280ms cubic-bezier(.2,.8,.2,1), box-shadow 280ms;
        animation: softFadeUp 460ms ease both;
    }}
    .card:hover {{ transform: translateY(-6px); box-shadow: 0 20px 40px rgba(2,6,23,0.16), 0 0 60px var(--glow); }}
    .stButton>button {{
        background: linear-gradient(90deg, var(--accent), #06b6d4);
        color: white;
        border-radius: 10px;
        padding: 8px 14px;
        border: none;
        box-shadow: 0 6px 18px rgba(0,0,0,0.12);
    }}
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
        backdrop-filter: blur(6px);
        border-right: 1px solid rgba(255,255,255,0.02);
    }}
    .small-meta {{ color: var(--sub) !important; font-size:0.92rem; }}
    @keyframes softFadeUp {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}
    </style>
    """, unsafe_allow_html=True)

# ---------------- App start ----------------
create_tables()
init_default_admin()
upgrade_marks_table()
upgrade_students_table()
upgrade_admins_table()

# session initialization
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "admin_username" not in st.session_state:
    st.session_state.admin_username = ""
if "student_logged_in" not in st.session_state:
    st.session_state.student_logged_in = False
if "student_roll" not in st.session_state:
    st.session_state.student_roll = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

# page config
st.set_page_config(page_title="Student Result Management - Pro", layout="centered", initial_sidebar_state="expanded")

# sidebar controls
with st.sidebar:
    st.title("Student Results — Pro")
    dm = st.checkbox("Dark mode", value=st.session_state.dark_mode, key="dm_toggle")
    st.session_state.dark_mode = bool(dm)
    st.markdown("---")
    st.markdown("**Quick Links**")
    st.markdown("- Home\n- Admin Login\n- Admin Panel\n- Student Login\n- Student Dashboard\n- Analytics\n- Help")
    st.markdown("---")
    st.write("Secure your admin account — change default password.")

# apply styling
set_page_style()

# Navigation
page = st.sidebar.selectbox("Go to", ["Home", "Admin Login", "Admin Panel", "Student Login", "Student Dashboard", "Analytics", "Help"])

# quick admin login in sidebar (small expander)
if not st.session_state.admin_logged_in:
    with st.sidebar.expander("Admin quick login", expanded=False):
        u = st.text_input("Username", key="quick_user")
        p = st.text_input("Password", type="password", key="quick_pw")
        if st.button("Login (quick)"):
            if verify_admin(u, p):
                st.session_state.admin_logged_in = True
                st.session_state.admin_username = u
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")

# ---------------- PAGES ----------------
if page == "Home":
    st.title("Student Result Management — Professional")
    st.markdown("<div class='card'><h2>Welcome</h2><p class='small-meta'>Use Admin Login to manage students and marks, or Student Login to check results. This app includes CSV import/export, responsive charts, downloadable reports, and polished UI animations.</p></div>", unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    try:
        total_students = len(get_all_students())
    except:
        total_students = "—"
    try:
        total_marks = len(get_all_marks())
    except:
        total_marks = "—"
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='card'><h3>Total Students</h3><p class='small-meta'>{total_students}</p></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><h3>Total Marks</h3><p class='small-meta'>{total_marks}</p></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><h3>Admin</h3><p class='small-meta'>{st.session_state.admin_username or 'Not logged in'}</p></div>", unsafe_allow_html=True)

# ---------------- Admin Login ----------------
elif page == "Admin Login":
    st.header("Admin Login")
    tabs = st.tabs(["Password", "OTP (Email)", "Security Question"])

    with tabs[0]:
        username = st.text_input("Username (password login)", key="pw_user")
        password = st.text_input("Password", type="password", key="pw_pass")
        if st.button("Login with password"):
            if verify_admin(username, password):
                st.success("Logged in")
                st.session_state.admin_logged_in = True
                st.session_state.admin_username = username
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tabs[1]:
        otp_user = st.text_input("Username (OTP login)", key="otp_user")
        col1, col2 = st.columns([2,1])
        if col1.button("Send OTP", key="send_otp_btn"):
            if not otp_user:
                st.error("Enter username first")
            else:
                sent, info = start_otp_flow(otp_user)
                st.info(info)
        otp_input = st.text_input("Enter OTP", key="otp_input")
        if st.button("Verify OTP", key="verify_otp_btn"):
            if verify_otp(otp_user, otp_input):
                st.success("OTP verified — logged in")
                st.session_state.admin_logged_in = True
                st.session_state.admin_username = otp_user
                st.rerun()
            else:
                st.error("Invalid or expired OTP")

    with tabs[2]:
        sq_user = st.text_input("Username (security question)", key="sq_user")
        if st.button("Get security question", key="get_sq_btn"):
            q = get_security_question(sq_user)
            if q:
                st.session_state[f"sq_question_{sq_user}"] = q
                st.success("Question loaded. Answer below.")
            else:
                st.error("No security question set for that username.")
        if f"sq_question_{sq_user}" in st.session_state:
            st.write("Question: ", st.session_state[f"sq_question_{sq_user}"])
            sq_answer = st.text_input("Your Answer", type="password", key="sq_answer")
            if st.button("Verify Security Answer", key="verify_sq_btn"):
                if verify_security_answer(sq_user, sq_answer):
                    st.success("Verified — logged in")
                    st.session_state.admin_logged_in = True
                    st.session_state.admin_username = sq_user
                    st.rerun()
                else:
                    st.error("Incorrect answer")

# ---------------- Admin Panel ----------------
elif page == "Admin Panel":
    if not st.session_state.admin_logged_in:
        st.warning("You must be logged in as admin to access this page. Use Admin Login in the sidebar.")
    else:
        st.header("Admin Panel")
        st.markdown(f"<div class='card'><h3>Welcome, {st.session_state.admin_username}</h3><p class='small-meta'>Use the controls below to manage students, marks, CSV import/export and settings.</p></div>", unsafe_allow_html=True)

        # Add / Update Student
        with st.expander("Add / Update Student", expanded=True):
            col1, col2, col3 = st.columns(3)
            roll = col1.text_input("Roll No", key="add_roll")
            name = col2.text_input("Name", key="add_name")
            cls = col3.text_input("Class", key="add_class")
            dob = col1.text_input("DOB (DD-MM-YYYY) — optional", key="add_dob")
            if st.button("Add / Update Student"):
                if roll and name and cls:
                    if dob.strip():
                        try:
                            datetime.strptime(dob.strip(), "%d-%m-%Y")
                        except Exception:
                            st.error("DOB must be in DD-MM-YYYY format (e.g., 15-08-2005)")
                            st.stop()
                    add_student(roll.strip(), name.strip(), cls.strip(), dob.strip())
                    st.success("Student added/updated")
                else:
                    st.error("All fields (except DOB) are required")

        # Add Mark
        with st.expander("Add Mark", expanded=False):
            c1, c2, c3, c4, c5 = st.columns(5)
            mroll = c1.text_input("Student Roll", key="m_roll")
            subject = c2.text_input("Subject", key="m_subject")
            exam_type = c3.text_input("Exam Type", key="m_exam")
            marks_val = c4.number_input("Marks", min_value=0, max_value=2000, step=1, key="m_marks")
            max_marks_val = c5.number_input("Max Marks", min_value=1, max_value=2000, step=1, key="m_max_marks", value=100)
            if st.button("Add Mark"):
                if mroll and subject and exam_type:
                    add_mark(mroll.strip(), subject.strip(), exam_type.strip(), int(marks_val), int(max_marks_val))
                    st.success("Mark added")
                else:
                    st.error("All fields are required")

        st.markdown("### 📘 All Students")
        df_students = get_all_students()
        st.dataframe(df_students)

        st.markdown("### 📝 All Marks")
        df_marks = get_all_marks()
        st.dataframe(df_marks)

        # Update / Delete mark
        st.markdown("### ✏️ Update / Delete Mark (by ID)")
        colA, colB = st.columns([1,1])
        mark_id = colA.number_input("Mark ID", min_value=1, step=1)
        new_mark = colB.number_input("New Mark", min_value=0, max_value=2000, step=1)
        c1, c2 = st.columns(2)
        if c1.button("Update Mark"):
            update_mark(mark_id, new_mark)
            st.success("Mark updated")
        if c2.button("Delete Mark"):
            delete_mark(mark_id)
            st.warning("Mark deleted")

        # Delete student
        st.markdown("---")
        st.markdown("### 🗑️ Delete Student (removes student + their marks)")
        del_roll = st.text_input("Enter Roll No to delete student", key="delete_student_roll")
        if st.button("Delete Student"):
            if del_roll.strip():
                delete_student(del_roll.strip())
                st.warning(f"Student {del_roll.strip()} deleted (including their marks).")
            else:
                st.error("Enter a valid roll no")

        st.markdown("---")
        st.markdown("### 📤 Bulk Upload (CSV)")
        st.markdown("**Students CSV:** roll,name,class,dob  \n**Marks CSV:** roll,subject,exam_type,marks,max_marks")
        uploaded = st.file_uploader("Upload CSV (students or marks)", type=["csv"])
        if uploaded:
            try:
                df_up = pd.read_csv(uploaded)
                st.write("Preview:")
                st.dataframe(df_up.head())
                if st.button("Import CSV"):
                    if {"roll","name","class"}.issubset(df_up.columns):
                        bulk_insert_students_from_df(df_up)
                        st.success("Students imported successfully")
                    elif {"roll","subject","exam_type","marks"}.issubset(df_up.columns):
                        bulk_insert_marks_from_df(df_up)
                        st.success("Marks imported successfully")
                    else:
                        st.error("CSV does not match required format.")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

        # Export CSV / Excel
        st.markdown("---")
        st.markdown("### 📥 Export Data")
        df_all_marks = get_all_marks()
        csv_bytes = df_all_marks.to_csv(index=False).encode('utf-8')
        st.download_button("Download all marks (CSV)", data=csv_bytes, file_name="all_marks.csv", mime="text/csv")
        try:
            import openpyxl
            excel_buf = io.BytesIO()
            df_all_marks.to_excel(excel_buf, index=False, engine="openpyxl")
            excel_buf.seek(0)
            st.download_button("Download all marks (Excel)", data=excel_buf, file_name="all_marks.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            st.info("Excel export not available — install openpyxl to enable.")

        # Admin settings
        st.markdown("---")
        st.markdown("### ⚙️ Admin Settings")
        cur_email = get_admin_email(st.session_state.admin_username)
        new_email = st.text_input("Set email (for OTP)", value=cur_email, key="admin_email")
        if st.button("Save Email"):
            set_admin_email(st.session_state.admin_username, new_email.strip())
            st.success("Email saved (used for OTP)")

        existing_q = get_security_question(st.session_state.admin_username)
        st.write("Security question:", existing_q if existing_q else "*Not set*")
        sq_q = st.text_input("New Security Question", key="set_sq_q")
        sq_a = st.text_input("Answer (will be stored hashed)", type="password", key="set_sq_a")
        if st.button("Save Security Question"):
            if sq_q.strip() and sq_a.strip():
                set_security_question(st.session_state.admin_username, sq_q.strip(), sq_a.strip())
                st.success("Security question saved")
            else:
                st.error("Both question and answer are required")

        st.markdown("Change admin password")
        old = st.text_input("Old password", type="password", key="oldpw")
        new = st.text_input("New password", type="password", key="newpw")
        if st.button("Change password"):
            user = st.session_state.admin_username
            if verify_admin(user, old):
                change_admin_password(user, new)
                st.success("Password changed")
            else:
                st.error("Old password incorrect")

        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.session_state.admin_username = ""
            st.rerun()

# ---------------- Student Login ----------------
elif page == "Student Login":
    st.header("Student Portal — Login")
    st.markdown("Login using **Roll Number + DOB (DD-MM-YYYY)**")
    col1, col2 = st.columns(2)
    sroll = col1.text_input("Roll Number", key="s_roll")
    sdob = col2.text_input("Date of Birth (DD-MM-YYYY)", key="s_dob", placeholder="15-08-2006")
    if st.button("Student Login"):
        if not sroll.strip() or not sdob.strip():
            st.error("Enter both Roll Number and DOB")
        else:
            try:
                datetime.strptime(sdob.strip(), "%d-%m-%Y")
            except:
                st.error("DOB must be DD-MM-YYYY")
                st.stop()
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT dob FROM students WHERE roll = ?", (sroll.strip(),))
            row = cur.fetchone()
            conn.close()
            if not row:
                st.error("Student not found")
            else:
                stored = (row[0] or "").strip()
                if stored == sdob.strip():
                    st.success("Login Successful")
                    st.session_state.student_logged_in = True
                    st.session_state.student_roll = sroll.strip()
                    st.rerun()
                else:
                    st.error("Incorrect DOB")

# ---------------- Student Dashboard ----------------
elif page == "Student Dashboard":
    if not st.session_state.student_logged_in:
        st.warning("Not logged in — go to Student Login")
    else:
        roll = st.session_state.student_roll
        res = get_student_result(roll)
        if not res:
            st.warning("No data available")
        else:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.subheader(f"{res['student']['name']} — Roll: {roll} — Class: {res['student']['class']}")

            if res["marks"]:
                df = pd.DataFrame([
                    {"Subject": m["subject"], "Exam": m["exam_type"], "Marks": m["marks"], "Max Marks": m["max_marks"]}
                    for m in res["marks"]
                ])
                st.table(df)
                try:
                    import altair as alt
                    df_chart = df.copy()
                    df_chart["Percent"] = df_chart["Marks"] * 100.0 / df_chart["Max Marks"]
                    chart = alt.Chart(df_chart).mark_bar().encode(
                        x="Subject:N",
                        y="Percent:Q",
                        tooltip=["Subject", "Marks", "Max Marks", "Percent"]
                    ).properties(width=700, height=350).interactive()
                    st.altair_chart(chart, use_container_width=True)
                except Exception:
                    st.info("Install altair for charts: pip install altair")
            else:
                st.info("No marks found")

            st.write(f"**Total:** {res['total']} / {res['total_possible']}")
            st.write(f"**Percentage:** {res['percentage']}%")

            html = make_student_html_report(res)
            st.download_button("Download Report (HTML)", data=html, file_name=f"report_{roll}.html", mime="text/html")
            if REPORTLAB_AVAILABLE:
                pdf_bytes = make_student_pdf_bytes(res)
                st.download_button("Download Report (PDF)", data=pdf_bytes, file_name=f"report_{roll}.pdf", mime="application/pdf")
            else:
                st.info("Install reportlab for PDF generation (pip install reportlab)")

            if st.button("Logout Student"):
                st.session_state.student_logged_in = False
                st.session_state.student_roll = ""
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Analytics ----------------
elif page == "Analytics":
    st.header("Analytics & Charts")
    df_avg = subject_averages()
    if not df_avg.empty:
        st.subheader("Subject-wise Averages (%)")
        st.dataframe(df_avg)
        try:
            import altair as alt
            chart = alt.Chart(df_avg).mark_bar().encode(
                x="subject:N",
                y="avg_marks:Q",
                tooltip=["subject", "avg_marks", "count"]
            ).properties(width=700, height=350)
            st.altair_chart(chart, use_container_width=True)
        except Exception:
            st.info("Install altair to enable charts")
        st.markdown("---")
        st.subheader("Marks distribution (boxplot)")
        df_marks = get_all_marks()
        if not df_marks.empty:
            try:
                import altair as alt
                chart2 = alt.Chart(df_marks).mark_boxplot().encode(
                    x="subject:N",
                    y="marks:Q"
                ).properties(width=700, height=350)
                st.altair_chart(chart2, use_container_width=True)
            except Exception:
                st.info("Install altair to enable charts")
    else:
        st.info("No marks available yet.")

# ---------------- Help ----------------
elif page == "Help":
    st.header("Help & User Guide")
    st.markdown("""
### 🔐 Admin Login:
- Login using **Password**, **Email OTP**, or **Security Question**
- Change password & set email for OTP (Admin Panel -> Admin Settings)
- Set your own security question

### 🧑‍🎓 Student Login:
- Students login using **Roll No + DOB**

### 📚 Admin Panel Tools:
- Add / update students  
- Add marks with max marks  
- Delete marks  
- **Delete student completely**  
- Import CSV for bulk upload  
- Export all marks to CSV/Excel

### 📊 Analytics:
- Subject-wise averages  
- Box plot distribution  
- Student dashboard: performance chart  

### 📄 Reports:
- Download HTML Report  
- Download PDF Report (requires `reportlab`)  

### 📦 Optional Installs:""")
    st.markdown("**CSV templates**")
    st.code("students.csv -> roll,name,class,dob\n101,Aman,10A,15-08-2007\n102,Neha,10A,30-08-2007", language="text")
    st.code("marks.csv -> roll,subject,exam_type,marks,max_marks\n101,Math,Unit Test,72,80\n101,Physics,Midterm,42,50", language="text")

# ---------------- END OF FILE ---------------- 