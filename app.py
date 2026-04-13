import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import qrcode
from io import BytesIO
import urllib.parse

# --- DIRECTORY SETUP ---
if not os.path.exists("screenshots"):
    os.makedirs("screenshots")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
    # Transactions Table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT, amount REAL, method TEXT, txid TEXT UNIQUE,
                  bonus_opted TEXT, rolling TEXT, ss_path TEXT, status TEXT, reason TEXT)''')
    
    # Settings Table for Dynamic Updates
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Default Details (Only inserts if table is empty)
    defaults = [
        ('upi_id', 'shreeshyam101@ptyes'),
        ('bank_name', 'Federal Bank'),
        ('bank_acc', '24950100015849'),
        ('bank_ifsc', 'FDRL0002495')
    ]
    for key, val in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    
    conn.commit()
    return conn

conn = init_db()

# --- DATA HELPERS ---
def get_setting(key):
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    return res[0] if res else ""

def update_setting(key, value):
    c = conn.cursor()
    c.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    conn.commit()

def get_upi_qr(amt):
    upi = get_setting('upi_id')
    upi_link = f"upi://pay?pa={upi}&pn=Admin&am={amt}&cu=INR"
    img = qrcode.make(upi_link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- SESSION STATE ---
if 'step' not in st.session_state: st.session_state.step = "Selection"
if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False

# --- STYLING ---
st.set_page_config(page_title="Payment Portal", layout="centered")
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.5em; }
    .timer-box { background: #fff5f5; color: #e53e3e; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #feb2b2; margin-bottom: 15px;}
    .admin-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- NAVIGATION ---
choice = st.sidebar.selectbox("Navigation", ["User Panel", "Admin Panel"])

if choice == "User Panel":
    t1, t2 = st.tabs(["New Deposit", "Transaction History"])

    with t1:
        if st.session_state.step == "Selection":
            st.header("Select Payment Method")
            if st.button("📱 UPI ID"): st.session_state.pay_method = "UPI"; navigate_to("Amount")
            if st.button("📸 Scan QR Code"): st.session_state.pay_method = "QR"; navigate_to("Amount")
            if st.button("🏦 Bank IMPS"): st.session_state.pay_method = "Bank"; navigate_to("Amount")

        elif st.session_state.step == "Amount":
            st.header("Deposit Details")
            amt = st.number_input("Amount (Min ₹500)", min_value=500.0, step=100.0)
            bonus = st.checkbox("Apply 5% Bonus (3x Rolling)")
            if st.button("Confirm"):
                st.session_state.amount, st.session_state.bonus = amt, ("Yes" if bonus else "No")
                st.session_state.rolling = "3x Rolling" if bonus else "1x Rolling"
                st.session_state.start_time = datetime.now()
                navigate_to("Payment")

        elif st.session_state.step == "Payment":
            rem = timedelta(minutes=10) - (datetime.now() - st.session_state.start_time)
            if rem.total_seconds() <= 0:
                st.error("Session Expired"); st.button("Restart", on_click=lambda: navigate_to("Selection"))
            else:
                st.markdown(f'<div class="timer-box">⏳ Time Left: {int(rem.total_seconds()//60):02d}:{int(rem.total_seconds()%60):02d}</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.session_state.pay_method == "QR":
                        st.image(get_upi_qr(st.session_state.amount), caption=f"Scan to Pay ₹{st.session_state.amount}")
                    elif st.session_state.pay_method == "UPI":
                        st.info(f"UPI ID: {get_setting('upi_id')}")
                    else:
                        st.markdown(f"**{get_setting('bank_name')}**<br>Acc: {get_setting('bank_acc')}<br>IFSC: {get_setting('bank_ifsc')}", unsafe_allow_html=True)
                with c2:
                    u_utr = st.text_input("14-Digit UTR", max_chars=14)
                    u_file = st.file_uploader("Screenshot", type=['jpg','png','jpeg'])
                    if st.button("Submit Payment"):
                        if len(u_utr) != 14: st.error("UTR must be 14 digits.")
                        elif not u_file: st.error("Proof required.")
                        else:
                            try:
                                path = f"screenshots/{u_utr}.png"
                                with open(path, "wb") as f: f.write(u_file.getbuffer())
                                st.session_state.cur_utr, st.session_state.ts = u_utr, datetime.now().strftime("%Y-%m-%d %H:%M")
                                conn.execute("INSERT INTO transactions (timestamp, amount, method, txid, bonus_opted, rolling, ss_path, status, reason) VALUES (?,?,?,?,?,?,?,?,?)",
                                          (st.session_state.ts, st.session_state.amount, st.session_state.pay_method, u_utr, st.session_state.bonus, st.session_state.rolling, path, "Pending", ""))
                                conn.commit(); navigate_to("Success")
                            except sqlite3.IntegrityError: st.error("❌ Duplicate UTR.")

        elif st.session_state.step == "Success":
            st.success("✅ Submission Successful!")
            wa_msg = f"*DEPOSIT REPORT*\n*Amount:* ₹{st.session_state.amount}\n*UTR:* {st.session_state.cur_utr}\n\n_Verify my screenshot attached._"
            wa_url = f"https://wa.me/919294823595?text={urllib.parse.quote(wa_msg)}"
            st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:15px; border-radius:8px; font-weight:bold; cursor:pointer; width:100%;">📲 Send to WhatsApp</button></a>', unsafe_allow_html=True)
            if st.button("New Deposit"): navigate_to("Selection")

    with t2:
        st.header("Global History")
        st.table(pd.read_sql_query("SELECT timestamp, amount, txid, status, reason FROM transactions ORDER BY id DESC", conn))

elif choice == "Admin Panel":
    if not st.session_state.admin_logged_in:
        with st.form("admin"):
            pw = st.text_input("Admin Password", type="password")
            if st.form_submit_button("Enter"):
                if pw == "ShuB#2026!Fed_Admin_9x": st.session_state.admin_logged_in = True; st.rerun()
                else: st.error("Denied")
    else:
        if st.sidebar.button("Logout"): st.session_state.admin_logged_in = False; st.rerun()
        
        adm_tabs = st.tabs(["Verify Payments", "⚙️ Update Bank/UPI Details"])
        
        with adm_tabs[0]:
            pending = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
            for i, r in pending.iterrows():
                with st.expander(f"UTR: {r['txid']} (₹{r['amount']})"):
                    if os.path.exists(r['ss_path']): st.image(r['ss_path'], width=300)
                    reason = st.text_input("Reason", key=f"r_{r['id']}")
                    if st.button("Approve ✅", key=f"a_{r['id']}"):
                        conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                    if st.button("Decline ❌", key=f"d_{r['id']}"):
                        conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id'])); conn.commit(); st.rerun()

        with adm_tabs[1]:
            st.subheader("Edit Active Payment Details")
            new_upi = st.text_input("Current UPI ID", value=get_setting('upi_id'))
            new_bank = st.text_input("Bank Name", value=get_setting('bank_name'))
            new_acc = st.text_input("Account Number", value=get_setting('bank_acc'))
            new_ifsc = st.text_input("IFSC Code", value=get_setting('bank_ifsc'))
            
            if st.button("💾 Save All Changes"):
                update_setting('upi_id', new_upi)
                update_setting('bank_name', new_bank)
                update_setting('bank_acc', new_acc)
                update_setting('bank_ifsc', new_ifsc)
                st.success("Details Updated! The User Panel is now using these new details.")
                    
