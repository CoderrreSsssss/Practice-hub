import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import qrcode
from PIL import Image
from io import BytesIO

# --- DIRECTORY SETUP ---
if not os.path.exists("screenshots"):
    os.makedirs("screenshots")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  username TEXT,
                  sitename TEXT,
                  amount REAL,
                  method TEXT,
                  txid TEXT UNIQUE,
                  bonus_opted TEXT,
                  rolling TEXT,
                  ss_path TEXT,
                  status TEXT,
                  reason TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- HELPER: GENERATE QR ---
def get_upi_qr(amt):
    upi_link = f"upi://pay?pa=shreeshyam101@ptyes&pn=Shubham%20Sharma&am={amt}&cu=INR"
    img = qrcode.make(upi_link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- SESSION STATE ---
if 'step' not in st.session_state: st.session_state.step = "Selection"
if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False

# --- STYLING ---
st.set_page_config(page_title="Professional Deposit Portal", layout="centered")
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.5em; }
    .timer-box { background: #fff5f5; color: #e53e3e; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #feb2b2; }
    .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border: 1px solid #eee; }
    </style>
""", unsafe_allow_html=True)

def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- NAVIGATION ---
choice = st.sidebar.selectbox("Navigation", ["User Panel", "Admin Panel"])

if choice == "User Panel":
    t1, t2 = st.tabs(["New Deposit", "My History"])

    with t1:
        if st.session_state.step == "Selection":
            st.header("Select Payment Method")
            if st.button("📱 UPI ID (Direct)"): st.session_state.pay_method = "UPI"; navigate_to("Amount")
            if st.button("📸 Scan QR Code"): st.session_state.pay_method = "QR"; navigate_to("Amount")
            if st.button("🏦 Bank IMPS"): st.session_state.pay_method = "Bank"; navigate_to("Amount")

        elif st.session_state.step == "Amount":
            st.header("Deposit Details")
            u_name = st.text_input("Username")
            s_name = st.text_input("Site Name")
            amt = st.number_input("Amount (Min ₹500)", min_value=500.0, step=100.0)
            bonus = st.checkbox("Apply 5% Bonus (3x Rolling)")
            if st.button("Confirm Amount"):
                if u_name and s_name:
                    st.session_state.username, st.session_state.sitename = u_name, s_name
                    st.session_state.amount = amt
                    st.session_state.bonus = "Yes" if bonus else "No"
                    st.session_state.rolling = "3x Rolling" if bonus else "1x Rolling"
                    st.session_state.start_time = datetime.now()
                    navigate_to("Payment")
                else: st.error("Fill all details.")

        elif st.session_state.step == "Payment":
            rem = timedelta(minutes=10) - (datetime.now() - st.session_state.start_time)
            if rem.total_seconds() <= 0:
                st.error("Session Expired"); st.button("Restart", on_click=lambda: navigate_to("Selection"))
            else:
                st.markdown(f'<div class="timer-box">⏳ Time Remaining: {int(rem.total_seconds()//60):02d}:{int(rem.total_seconds()%60):02d}</div>', unsafe_allow_html=True)
                st.subheader(f"Deposit Amount: ₹{st.session_state.amount}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.session_state.pay_method == "QR":
                        st.image(get_upi_qr(st.session_state.amount), caption="Scan to Pay")
                    elif st.session_state.pay_method == "UPI":
                        st.info("UPI: shreeshyam101@ptyes")
                    else:
                        st.markdown("**Federal Bank**<br>Acc: 24950100015849<br>IFSC: FDRL0002495", unsafe_allow_html=True)

                with col2:
                    u_utr = st.text_input("14-Digit UTR", max_chars=14)
                    u_file = st.file_uploader("Upload Screenshot", type=['jpg','png','jpeg'])
                    if st.button("Submit Payment Proof"):
                        if len(u_utr) != 14: st.error("UTR must be 14 digits.")
                        elif not u_file: st.error("Screenshot required.")
                        else:
                            try:
                                # Save SS
                                path = f"screenshots/{u_utr}.png"
                                with open(path, "wb") as f: f.write(u_file.getbuffer())
                                # DB Entry
                                c = conn.cursor()
                                c.execute("INSERT INTO transactions (timestamp, username, sitename, amount, method, txid, bonus_opted, rolling, ss_path, status, reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                          (datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.username, st.session_state.sitename, st.session_state.amount, st.session_state.pay_method, u_utr, st.session_state.bonus, st.session_state.rolling, path, "Pending", ""))
                                conn.commit(); navigate_to("Success")
                            except sqlite3.IntegrityError: st.error("❌ Duplicate UTR detected.")

        elif st.session_state.step == "Success":
            st.success("✅ Payment Submitted Successfully!"); st.button("New Deposit", on_click=lambda: navigate_to("Selection"))

    with t2:
        st.header("My Log")
        st.dataframe(pd.read_sql_query("SELECT timestamp, amount, status, rolling, reason FROM transactions ORDER BY id DESC", conn), use_container_width=True)

elif choice == "Admin Panel":
    if not st.session_state.admin_logged_in:
        with st.form("admin_login"):
            pw = st.text_input("Admin Password", type="password")
            if st.form_submit_button("Access Panel"):
                if pw == "ShuB#2026!Fed_Admin_9x": st.session_state.admin_logged_in = True; st.rerun()
                else: st.error("Wrong Password")
    else:
        if st.sidebar.button("Logout"): st.session_state.admin_logged_in = False; st.rerun()
        
        # --- PENDING REQUESTS ---
        st.subheader("🔔 Verification Queue")
        pending = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        for i, r in pending.iterrows():
            with st.expander(f"USER: {r['username']} (₹{r['amount']})"):
                st.write(f"**UTR:** `{r['txid']}` | **Site:** {r['sitename']}")
                if os.path.exists(r['ss_path']): st.image(r['ss_path'], caption="User Proof", width=300)
                reason = st.text_input("Reason", key=f"r_{r['id']}")
                c1, c2 = st.columns(2)
                if c1.button("✅ Approve", key=f"a_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                if c2.button("❌ Decline", key=f"d_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id'])); conn.commit(); st.rerun()

        st.divider()
        # --- HISTORY SECTION ---
        st.subheader("📜 Complete History (Approved/Declined)")
        history_df = pd.read_sql_query("SELECT timestamp, username, amount, txid, status, reason FROM transactions WHERE status != 'Pending' ORDER BY id DESC", conn)
        st.dataframe(history_df, use_container_width=True)
