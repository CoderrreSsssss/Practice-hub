import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import os

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
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

# --- SESSION STATE MANAGEMENT ---
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'pay_method' not in st.session_state:
    st.session_state.pay_method = None
if 'amount' not in st.session_state:
    st.session_state.amount = 0.0
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.now()

# --- STYLING ---
st.set_page_config(page_title="Secure Pay", layout="centered")

st.markdown("""
    <style>
    .step-tracker { color: #666; font-size: 14px; text-align: center; margin-bottom: 20px; }
    .pay-card {
        background: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: 1px solid #e1e4e8;
        cursor: pointer; transition: 0.3s; margin-bottom: 10px;
    }
    .timer-box {
        background: #fff5f5; color: #e53e3e; padding: 10px;
        border-radius: 8px; text-align: center; font-weight: bold;
        border: 1px solid #feb2b2; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- UTILS ---
def next_step(): st.session_state.step += 1
def reset_flow(): 
    st.session_state.step = 1
    st.session_state.start_time = datetime.now()

# --- TIMER LOGIC ---
def show_timer():
    elapsed = datetime.now() - st.session_state.start_time
    remaining = timedelta(minutes=10) - elapsed
    if remaining.total_seconds() > 0:
        mins, secs = divmod(int(remaining.total_seconds()), 60)
        st.markdown(f'<div class="timer-box">⏱️ Payment expires in: {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)
    else:
        st.error("Session Expired. Please restart.")
        if st.button("Restart"): reset_flow()
        st.stop()

# --- APP NAVIGATION ---
page = st.sidebar.radio("Navigation", ["User Payment", "Check Status", "Admin Panel"])

if page == "User Payment":
    # STEP 1: SELECT METHOD
    if st.session_state.step == 1:
        st.title("Select Payment Method")
        st.write("Choose how you would like to pay:")
        
        if st.button("📱 UPI ID / GPay / PhonePe"):
            st.session_state.pay_method = "UPI"
            next_step()
        if st.button("📸 Scan QR Code"):
            st.session_state.pay_method = "QR"
            next_step()
        if st.button("🏦 Bank Transfer (IMPS/NEFT)"):
            st.session_state.pay_method = "Bank"
            next_step()

    # STEP 2: ENTER AMOUNT
    elif st.session_state.step == 2:
        st.title("Enter Amount")
        st.session_state.amount = st.number_input("How much are you paying?", min_value=1.0, step=1.0)
        if st.button("Continue to Payment"):
            if st.session_state.amount > 0:
                st.session_state.start_time = datetime.now() # Start timer here
                next_step()

    # STEP 3: ACTUAL PAYMENT & UPLOAD
    elif st.session_state.step == 3:
        show_timer()
        st.title("Complete Payment")
        st.info(f"Method: {st.session_state.pay_method} | Amount: ₹{st.session_state.amount}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.pay_method == "UPI":
                st.code("shreeshyam101@ptyes", language="text")
                st.caption("Copy and paste this UPI ID in your payment app.")
            elif st.session_state.pay_method == "QR":
                if os.path.exists("qr_code.png"): st.image("qr_code.png")
                else: st.warning("QR Code Image Missing")
            elif st.session_state.pay_method == "Bank":
                st.markdown("""**Federal Bank** Acc: 24950100015849  
                IFSC: FDRL0002495  
                Name: Shubham Sharma""")

        with col2:
            with st.form("proof_form"):
                u_name = st.text_input("Your Name")
                u_utr = st.text_input("UTR / Transaction ID")
                u_file = st.file_uploader("Screenshot", type=['jpg','png'])
                if st.form_submit_button("Submit Payment"):
                    if u_name and u_utr:
                        c = conn.cursor()
                        c.execute("INSERT INTO transactions (timestamp, name, amount, method, txid, status, reason) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.now().strftime("%Y-%m-%d %H:%M"), u_name, st.session_state.amount, st.session_state.pay_method, u_utr, "Pending", ""))
                        conn.commit()
                        next_step()
                    else:
                        st.error("Fill all fields")

    # STEP 4: SUCCESS PAGE
    elif st.session_state.step == 4:
        st.balloons()
        st.success("### 🎉 Transaction Saved!")
        st.write("Your payment is being verified by our team. This usually takes 5-30 minutes.")
        st.info("Kindly check your status using your Transaction ID in the 'Check Status' tab.")
        if st.button("Make Another Payment"): reset_flow()

elif page == "Check Status":
    st.title("🔍 Check Status")
    tid = st.text_input("Enter UTR Number")
    if tid:
        res = pd.read_sql_query("SELECT status, reason FROM transactions WHERE txid=?", conn, params=(tid,))
        if not res.empty:
            st.subheader(f"Status: {res['status'][0]}")
            if res['reason'][0]: st.error(f"Note: {res['reason'][0]}")
        else: st.warning("Not found.")

elif page == "Admin Panel":
    pw = st.sidebar.text_input("Password", type="password")
    if pw == "admin123":
        st.title("Admin Dashboard")
        df = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        st.write("Pending Tasks:", df)
        # Admin approval logic (same as previous code)
        for i, r in df.iterrows():
            with st.expander(f"Review {r['name']}"):
                reason = st.text_input("Decline Reason", key=f"re{i}")
                c1, c2 = st.columns(2)
                if c1.button("Approve", key=f"ap{i}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
                if c2.button("Decline", key=f"de{i}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id']))
                    conn.commit()
                    st.rerun()
