# -*- coding: utf-8 -*-
"""
طبقة قاعدة البيانات لتطبيق مستقل | Mustaqil
SQLite محلية (ملف mustaqil.db بجانب هذا الملف). تُنشأ الجداول تلقائياً،
وتُزرع بيانات mustaqil_dataset_v2.xlsx فيها عند أول تشغيل فقط.

على استضافة مجانية بقرص مؤقّت (كـ Streamlit Community Cloud) تُعاد زراعة
البيانات الأساسية من ملف الإكسل المرفق مع كل نشر جديد، أمّا الأهداف
والفواتير التي يُنشئها المستخدم فتبقى طوال عمر الجلسة الحيّة وتُفقد فقط
عند إعادة نشر التطبيق، هذا حدّ معروف لقواعد بيانات الملف الواحد على
الاستضافة المجانية، وواضح للفريق كخطوة تالية (Postgres مُدار، مثلاً Supabase).
"""
import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mustaqil.db")
XLSX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mustaqil_dataset_v2.xlsx")

SCHEMA = """
CREATE TABLE IF NOT EXISTS monthly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Freelancer_ID INTEGER NOT NULL,
    Name TEXT NOT NULL,
    Specialty TEXT NOT NULL,
    Year INTEGER NOT NULL,
    Month INTEGER NOT NULL,
    Income REAL, Fixed_Expenses REAL, Variable_Expenses REAL, Total_Expenses REAL,
    Savings REAL, Emergency_Fund REAL, Bank_Balance REAL,
    Number_of_Projects INTEGER, Payment_Delay_Days INTEGER, Loan_Amount REAL,
    Dry_Month_Label TEXT, Next_Month_Income REAL
);

CREATE TABLE IF NOT EXISTS projects_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Project_ID INTEGER NOT NULL,
    Freelancer_ID INTEGER NOT NULL,
    Specialty TEXT NOT NULL,
    Client_Type TEXT NOT NULL,
    Project_Duration_Days INTEGER, Estimated_Hours REAL, Complexity REAL,
    Hourly_Rate REAL, Project_Value REAL, Payment_Delay_Days INTEGER,
    Late_Payment INTEGER, Defaulted INTEGER, Suggested_Price REAL
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Freelancer_ID INTEGER NOT NULL,
    name TEXT NOT NULL,
    target REAL NOT NULL,
    share REAL NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS forest_meta (
    Freelancer_ID INTEGER PRIMARY KEY,
    months_simulated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Freelancer_ID INTEGER NOT NULL,
    invoice_number TEXT NOT NULL,
    client_name TEXT NOT NULL,
    description TEXT,
    amount_excl_vat REAL NOT NULL,
    vat_amount REAL NOT NULL,
    total_incl_vat REAL NOT NULL,
    vat_number TEXT,
    issued_at TEXT NOT NULL,
    qr_payload_b64 TEXT
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """ينشئ الجداول إن لم تكن موجودة، ويزرع بيانات الإكسل مرّة واحدة فقط."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM monthly_data").fetchone()[0]
    if count == 0:
        _seed_from_excel(conn)
    conn.close()


def _seed_from_excel(conn):
    if not os.path.exists(XLSX_PATH):
        return
    monthly = pd.read_excel(XLSX_PATH, sheet_name="Monthly_Data")
    projects = pd.read_excel(XLSX_PATH, sheet_name="Projects_Data")
    monthly.to_sql("monthly_data", conn, if_exists="append", index=False)
    projects.to_sql("projects_data", conn, if_exists="append", index=False)
    conn.commit()


def load_monthly() -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM monthly_data", conn)
    conn.close()
    return df.drop(columns=["id"], errors="ignore")


def load_projects() -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM projects_data", conn)
    conn.close()
    return df.drop(columns=["id"], errors="ignore")


# ═══════════════════════════════════════════════════════════════
#  الأهداف، أشجار الأهداف (تبويب 8)
# ═══════════════════════════════════════════════════════════════
def load_goals(fid: int):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, target, share, balance FROM goals "
        "WHERE Freelancer_ID=? ORDER BY sort_order", conn, params=(fid,))
    conn.close()
    return df.to_dict("records")


def save_goals(fid: int, goals: list):
    """يستبدل كل أهداف الفريلانسر بالقائمة الجديدة، أبسط من مزامنة صف بصف."""
    conn = get_connection()
    conn.execute("DELETE FROM goals WHERE Freelancer_ID=?", (fid,))
    for i, g in enumerate(goals):
        conn.execute(
            "INSERT INTO goals (Freelancer_ID,name,target,share,balance,sort_order) "
            "VALUES (?,?,?,?,?,?)",
            (fid, g["name"], g["target"], g["share"], g.get("balance", 0), i))
    conn.commit()
    conn.close()


def seed_default_goals(fid: int, defaults: list):
    """يزرع أهدافاً افتراضية أوّل مرّة فقط لهذا الفريلانسر."""
    conn = get_connection()
    exists = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE Freelancer_ID=?", (fid,)).fetchone()[0] > 0
    conn.close()
    if not exists:
        save_goals(fid, defaults)


def get_months_simulated(fid: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT months_simulated FROM forest_meta WHERE Freelancer_ID=?", (fid,)).fetchone()
    conn.close()
    return row[0] if row else 0


def set_months_simulated(fid: int, months: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO forest_meta (Freelancer_ID, months_simulated) VALUES (?,?) "
        "ON CONFLICT(Freelancer_ID) DO UPDATE SET months_simulated=excluded.months_simulated",
        (fid, months))
    conn.commit()
    conn.close()


def reset_forest(fid: int):
    conn = get_connection()
    conn.execute("DELETE FROM goals WHERE Freelancer_ID=?", (fid,))
    conn.execute("DELETE FROM forest_meta WHERE Freelancer_ID=?", (fid,))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
#  الفواتير الإلكترونية (تبويب الفاتورة)
# ═══════════════════════════════════════════════════════════════
def save_invoice(fid, invoice_number, client_name, description,
                  amount_excl_vat, vat_amount, total_incl_vat, vat_number,
                  issued_at, qr_payload_b64):
    conn = get_connection()
    conn.execute("""INSERT INTO invoices
        (Freelancer_ID, invoice_number, client_name, description, amount_excl_vat,
         vat_amount, total_incl_vat, vat_number, issued_at, qr_payload_b64)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (fid, invoice_number, client_name, description, amount_excl_vat,
         vat_amount, total_incl_vat, vat_number, issued_at, qr_payload_b64))
    conn.commit()
    conn.close()


def load_invoices(fid: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT invoice_number, client_name, description, amount_excl_vat, vat_amount, "
        "total_incl_vat, issued_at FROM invoices WHERE Freelancer_ID=? ORDER BY id DESC",
        conn, params=(fid,))
    conn.close()
    return df


def next_invoice_number(fid: int) -> str:
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM invoices WHERE Freelancer_ID=?", (fid,)).fetchone()[0] + 1
    conn.close()
    return f"INV-{fid}-{n:04d}"
