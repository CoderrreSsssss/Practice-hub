import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

# --- DATABASE SELF-HEAL LOGIC ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
    
    # Create table with all required columns
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
                  status TEXT,
                  reason TEXT)''')
    
    # Check if 'username' column exists (to handle upgrades from old versions)
    c.execute("PRAGMA table_info(transactions)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'username' not in columns:
        # If database is old, drop and recreate fresh to avoid errors
        c.execute("DROP TABLE transactions")
        c.execute('''CREATE TABLE transactions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT,
                      username TEXT,
                      sitename TEXT,
                      amount REAL,
                      method TEXT,
                      txid TEXT UNIQUE,
                      bonus_opted TEXT,
                      rolling TEXT,
                      status TEXT,
                      reason TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- SESSION STATE ---
if 'step' not in st.session_state:
    st.session_state.step = "Selection"
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

# --- STYLING ---
st.set_page_config(page_title="Secure Deposit", layout="centered")
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 10px; height: 3.2em; font-weight: bold; }
    .timer-box { background: #fff5f5; color: #e53e3e; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #feb2b2; margin-bottom: 20px; }
    .info-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #004a99; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- NAVIGATION ---
choice = st.sidebar.selectbox("Panel Select", ["User Panel", "Admin Panel"])

if choice == "User Panel":
    tabs = st.tabs(["New Deposit", "Transaction History"])

    with tabs[0]:
        if st.session_state.step == "Selection":
            st.header("Select Payment Method")
            if st.button("📱 UPI ID"):
                st.session_state.pay_method = "UPI"; navigate_to("Amount")
            if st.button("📸 Scan QR Code"):
                st.session_state.pay_method = "QR"; navigate_to("Amount")
            if st.button("🏦 Bank Transfer"):
                st.session_state.pay_method = "Bank"; navigate_to("Amount")

        elif st.session_state.step == "Amount":
            st.header("Deposit Details")
            u_name = st.text_input("Username")
            s_name = st.text_input("Site Name")
            amt = st.number_input("Amount (₹)", min_value=100.0, step=100.0)
            bonus = st.checkbox("Get 5% Bonus (3x Rolling Required)")
            
            if st.button("Proceed"):
                if u_name and s_name and amt >= 100:
                    st.session_state.username = u_name
                    st.session_state.sitename = s_name
                    st.session_state.amount = amt
                    st.session_state.bonus = "Yes" if bonus else "No"
                    st.session_state.rolling = "3x Rolling" if bonus else "1x Rolling"
                    st.session_state.start_time = datetime.now()
                    navigate_to("Payment")
                else: st.error("Please fill all details.")

        elif st.session_state.step == "Payment":
            elapsed = datetime.now() - st.session_state.start_time
            rem = timedelta(minutes=10) - elapsed
            if rem.total_seconds() <= 0:
                st.error("Session Expired"); st.button("Restart", on_click=lambda: navigate_to("Selection"))
            else:
                mins, secs = divmod(int(rem.total_seconds()), 60)
                st.markdown(f'<div class="timer-box">⏳ Time Left: {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.session_state.pay_method == "QR":
                        if os.path.exists("qr_code.png"): st.image("qr_code.png")
                        else: st.warning("QR Not Available")
                    elif st.session_state.pay_method == "UPI":
                        st.info("UPI: shreeshyam101@ptyes")
                    else:
                        st.markdown("<div class='info-card'>Federal Bank<br>Acc: 24950100015849<br>IFSC: FDRL0002495</div>", unsafe_allow_html=True)

                with col2:
                    u_utr = st.text_input("UTR (Exactly 14 Digits)", max_chars=14)
                    u_file = st.file_uploader("Screenshot", type=['jpg','png','jpeg'])
                    if st.button("Submit Proof"):
                        if len(u_utr) != 14: st.error("UTR must be 14 digits.")
                        elif not u_file: st.error("Upload screenshot.")
                        else:
                            try:
                                c = conn.cursor()
                                c.execute("INSERT INTO transactions (timestamp, username, sitename, amount, method, txid, bonus_opted, rolling, status, reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                          (datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state.username, st.session_state.sitename, st.session_state.amount, st.session_state.pay_method, u_utr, st.session_state.bonus, st.session_state.rolling, "Pending", ""))
                                conn.commit(); navigate_to("Success")
                            except sqlite3.IntegrityError:
                                st.error("❌ ERROR: This UTR has already been used.")

        elif st.session_state.step == "Success":
            st.success("✅ Transaction Submitted!"); st.button("New Deposit", on_click=lambda: navigate_to("Selection"))

    with tabs[1]:
        st.header("History")
        history = pd.read_sql_query("SELECT timestamp, username, amount, status, rolling, reason FROM transactions ORDER BY id DESC", conn)
        st.dataframe(history, use_container_width=True)

elif choice == "Admin Panel":
    if not st.session_state.admin_logged_in:
        with st.form("admin_login"):
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Enter Panel"):
                if pw == "ShuB#2026!Fed_Admin_9x":
                    st.session_state.admin_logged_in = True; st.rerun()
                else: st.error("Access Denied")
    else:
        if st.sidebar.button("Logout"): st.session_state.admin_logged_in = False; st.rerun()
        pending = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        for i, r in pending.iterrows():
            with st.expander(f"User: {r['username']} (₹{r['amount']})"):
                st.write(f"UTR: {r['txid']} | Site: {r['sitename']}")
                st.write(f"Requirement: {r['rolling']}")
                reason = st.text_input("Decline Reason", key=f"r_{r['id']}")
                if st.button("Approve", key=f"a_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                if st.button("Decline", key=f"d_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id'])); conn.commit(); st.rerun()
