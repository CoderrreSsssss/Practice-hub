import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import urllib.parse

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
    # Drops old table to prevent the "OperationalError" and creates fresh one
    c.execute("DROP TABLE IF EXISTS transactions")
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  name TEXT,
                  amount REAL,
                  method TEXT,
                  txid TEXT,
                  status TEXT,
                  reason TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- SESSION STATE ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pay_method' not in st.session_state:
    st.session_state.pay_method = None
if 'amount' not in st.session_state:
    st.session_state.amount = 0.0
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.now()

# --- STYLING ---
st.set_page_config(page_title="Payment Portal", layout="centered")
st.markdown("""
    <style>
    .timer-box {
        background: #fff5f5; color: #e53e3e; padding: 10px;
        border-radius: 8px; text-align: center; font-weight: bold;
        border: 1px solid #feb2b2; margin-bottom: 20px;
    }
    .bank-card {
        background: white; padding: 15px; border-radius: 10px;
        border: 1px solid #ddd; margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCTIONS ---
def reset_flow():
    st.session_state.step = 1
    st.session_state.start_time = datetime.now()

def generate_upi_qr(amount):
    # This creates a link that auto-fills the amount in GPay/PhonePe
    payee_vpa = "shreeshyam101@ptyes"
    payee_name = "Shubham Sharma"
    params = {
        "pa": payee_vpa,
        "pn": payee_name,
        "am": str(amount),
        "cu": "INR"
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"upi://pay?{encoded_params}"

# --- APP LOGIC ---
page = st.sidebar.radio("Navigation", ["User Payment", "Check Status", "Admin Panel"])

if page == "User Payment":
    # STEP 1: CHOOSE METHOD
    if st.session_state.step == 1:
        st.title("Select Payment Method")
        if st.button("📱 UPI ID (GPay/PhonePe/Paytm)"):
            st.session_state.pay_method = "UPI"
            st.session_state.step = 2
        if st.button("📸 Scan QR Code (Auto-Amount)"):
            st.session_state.pay_method = "QR"
            st.session_state.step = 2
        if st.button("🏦 Bank Transfer (IMPS/NEFT)"):
            st.session_state.pay_method = "Bank"
            st.session_state.step = 2

    # STEP 2: ENTER AMOUNT
    elif st.session_state.step == 2:
        st.title("Enter Amount")
        st.session_state.amount = st.number_input("Enter Amount to Pay (₹)", min_value=1.0, step=1.0)
        if st.button("Proceed to Pay"):
            if st.session_state.amount > 0:
                st.session_state.start_time = datetime.now()
                st.session_state.step = 3
        if st.button("← Back"): st.session_state.step = 1

    # STEP 3: PAYMENT PAGE
    elif st.session_state.step == 3:
        # Timer
        elapsed = datetime.now() - st.session_state.start_time
        rem = timedelta(minutes=10) - elapsed
        if rem.total_seconds() <= 0:
            st.error("Session expired!")
            if st.button("Restart"): reset_flow()
            st.stop()
        
        mins, secs = divmod(int(rem.total_seconds()), 60)
        st.markdown(f'<div class="timer-box">⏱️ Time Remaining: {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)
        
        st.title("Complete Payment")
        st.info(f"Paying: ₹{st.session_state.amount}")

        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.pay_method == "QR":
                st.write("Scan this QR with any app:")
                # Using the QR image you uploaded
                if os.path.exists("qr_code.png"):
                    st.image("qr_code.png", caption=f"Pay ₹{st.session_state.amount}")
                else:
                    st.warning("QR image 'qr_code.png' not found in folder.")
            
            elif st.session_state.pay_method == "UPI":
                st.markdown(f"**UPI ID:** `shreeshyam101@ptyes`")
                st.caption("Copy this ID and pay the exact amount.")
            
            elif st.session_state.pay_method == "Bank":
                st.markdown("""
                <div class="bank-card">
                    <strong>Federal Bank</strong><br>
                    A/C: 24950100015849<br>
                    IFSC: FDRL0002495<br>
                    Name: Shubham Sharma
                </div>
                """, unsafe_allow_html=True)

        with col2:
            with st.form("proof"):
                u_name = st.text_input("Your Full Name")
                u_utr = st.text_input("UTR / Transaction ID")
                u_file = st.file_uploader("Upload Screenshot", type=['jpg','png','jpeg'])
                if st.form_submit_button("Submit Transaction Proof"):
                    if u_name and u_utr:
                        c = conn.cursor()
                        c.execute("INSERT INTO transactions (timestamp, name, amount, method, txid, status, reason) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.now().strftime("%Y-%m-%d %H:%M"), u_name, st.session_state.amount, st.session_state.pay_method, u_utr, "Pending", ""))
                        conn.commit()
                        st.session_state.step = 4
                        st.rerun()

    # STEP 4: SUCCESS
    elif st.session_state.step == 4:
        st.success("### ✅ Transaction Saved!")
        st.balloons()
        st.write("Your transaction has been recorded. Kindly check the status using your UTR number.")
        if st.button("Done"): reset_flow()

elif page == "Check Status":
    st.title("🔍 Check Payment Status")
    tid = st.text_input("Enter your UTR Number")
    if tid:
        res = pd.read_sql_query("SELECT status, reason FROM transactions WHERE txid=?", conn, params=(tid,))
        if not res.empty:
            s = res['status'][0]
            st.subheader(f"Status: {s}")
            if s == "Declined": st.error(f"Reason: {res['reason'][0]}")
        else: st.warning("No record found.")

elif page == "Admin Panel":
    # Using the Strong Password
    pw = st.sidebar.text_input("Admin Password", type="password")
    if pw == "ShuB#2026!Fed_Admin_9x":
        st.title("Admin Panel")
        df = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        st.dataframe(df)
        for i, r in df.iterrows():
            with st.expander(f"Review: {r['name']} (₹{r['amount']})"):
                reason = st.text_input("Decline Reason", key=f"r{i}")
                if st.button("Approve ✅", key=f"a{i}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
                if st.button("Decline ❌", key=f"d{i}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id']))
                    conn.commit()
                    st.rerun()
