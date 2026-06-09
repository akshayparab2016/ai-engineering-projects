from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv

import sqlite3
import pandas as pd
import os
import uuid
from werkzeug.utils import secure_filename

# =========================================
# CONFIG
# =========================================

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ACTIVE_DB_FILE = "active_db.txt"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# =========================================
# ACTIVE DB
# =========================================

def set_active_db(path):
    with open(ACTIVE_DB_FILE, "w") as f:
        f.write(path)

def get_active_db():
    if not os.path.exists(ACTIVE_DB_FILE):
        return None

    path = open(ACTIVE_DB_FILE).read().strip()

    if not os.path.exists(path):
        return None

    return path

def get_conn():
    db = get_active_db()
    if not db:
        raise Exception("Upload a file first")

    return sqlite3.connect(db)

# =========================================
# FILE CONVERTERS → SQLITE
# =========================================

def create_sqlite_db(original_filename):
    base = os.path.splitext(original_filename)[0]
    db_path = os.path.join(UPLOAD_FOLDER, f"{base}")
    return db_path

# ---------- CSV ----------
def load_csv(file_path, conn, table_name):
    df = pd.read_csv(file_path)
    print("CSV rows:", len(df))
    df.to_sql(table_name, conn, if_exists="replace", index=False)

# ---------- EXCEL ----------
def load_excel(file_path, conn):
    xls = pd.ExcelFile(file_path)

    for sheet in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        print(f"{sheet} rows:", len(df))
        df.to_sql(sheet.replace(" ", "_"), conn, if_exists="replace", index=False)

# ---------- SQL DUMP ----------
def load_sql(file_path, conn):
    with open(file_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    conn.executescript(sql_script)

# =========================================
# UPLOAD HANDLER
# =========================================

@app.route("/upload-db", methods=["POST"])
def upload_db():
    try:
        file = request.files["file"]

        if not file:
            return jsonify({"success": False, "error": "No file"})

        filename = secure_filename(file.filename)
        ext = filename.split(".")[-1].lower()

        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(temp_path)

        # CREATE NEW SQLITE DB
        db_path = create_sqlite_db(filename)
        conn = sqlite3.connect(db_path)

        # =========================
        # FILE TYPE HANDLING
        # =========================

        if ext == "db":
            conn.close()
            set_active_db(temp_path)
            return jsonify({
                "success": True,
                "database": filename,
                "message": "DB loaded successfully"
            })

        elif ext == "csv":
            load_csv(temp_path, conn, "data")

        elif ext in ["xls", "xlsx"]:
            load_excel(temp_path, conn)

        elif ext == "sql":
            load_sql(temp_path, conn)

        else:
            return jsonify({
                "success": False,
                "error": "Unsupported format"
            })

        conn.commit()
        conn.close()

        set_active_db(db_path)

        return jsonify({
            "success": True,
            "database": os.path.basename(db_path),
            "message": f"{ext.upper()} file loaded successfully"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

# =========================================
# SCHEMA
# =========================================

def get_schema():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table'
    """)

    schema = "\n".join([r[0] for r in cur.fetchall() if r[0]])

    conn.close()
    return schema

def get_schema_details():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
    """)

    tables = cur.fetchall()
    result = {}

    for t in tables:
        name = t[0]

        cur.execute(f"PRAGMA table_info('{name}')")
        cols = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) FROM '{name}'")
        count = cur.fetchone()[0]

        result[name] = {
            "columns": cols,
            "rows": count
        }

    conn.close()
    return result

# =========================================
# AI SQL
# =========================================

def generate_sql(question):
    schema = get_schema()

    prompt = f"""
You are an expert SQLite assistant.
Return ONLY ONE valid SQLite SELECT query.
Schema:
{schema}

Rules:
- ONLY SELECT queries
- No explanation
- No markdown

Question:
{question}
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    sql = res.choices[0].message.content
    return sql.replace("```", "").strip()

def validate(sql):
    bad = ["insert","update","delete","drop","alter","create"]
    return sql.lower().startswith("select") and not any(b in sql.lower() for b in bad)

# =========================================
# ROUTES
# =========================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/schema")
def schema():
    return jsonify({
        "success": True,
        "schema": get_schema_details()
    })

@app.route("/database-info")
def db_info():
    db = get_active_db()
    return jsonify({
        "success": bool(db),
        "db": os.path.basename(db) if db else None
    })

@app.route("/ask", methods=["POST"])
def ask():
    try:
        q = request.json["question"]

        sql = generate_sql(q)

        if not validate(sql):
            raise Exception("Unsafe SQL")

        conn = get_conn()
        df = pd.read_sql_query(sql, conn)
        conn.close()

        return jsonify({
            "success": True,
            "sql": sql,
            "columns": df.columns.tolist(),
            "data": df.values.tolist(),
            "rows": len(df)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

# =========================================
def clear_active_db():
    if os.path.exists(ACTIVE_DB_FILE):
        open(ACTIVE_DB_FILE, "w").close()
# =========================================
@app.route("/deactivate-db", methods=["POST"])
def deactivate_db():
    try:
        db = get_active_db()

        if not db:
            return jsonify({
                "success": False,
                "message": "No active database to deactivate"
            })

        clear_active_db()

        return jsonify({
            "success": True,
            "message": "Database deactivated"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        })
# =========================================
if __name__ == "__main__":
    app.run(debug=True)