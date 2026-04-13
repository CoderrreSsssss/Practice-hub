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
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
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

# --- HELPER FUNCTIONS ---
def get_upi_qr(amt):
    upi_link = f"upi://pay?pa=shreeshyam101@ptyes&pn=Shubham%20Sharma&am={amt}&cu=INR"
    img = qrcode.make(upi_link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def create_report(details):
    report = f"""
    --- TRANSACTION REPORT ---
    Date: {details['timestamp']}
    UTR Number: {details['txid']}
    Amount: ₹{details['amount']}
    Payment Method: {details['method']}
    Bonus Opted: {details['bonus']}
    Requirement: {details['rolling']}
    Status: Pending Verification
    ---------------------------
    """
    return report

# --- SESSION STATE ---
if 'step' not in st.session_state: st.session_state.step = "Selection"
if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False

# --- STYLING ---
st.set_page_config(page_title="Payment Portal", layout="centered")
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; height: 3.5em; }
    .timer-box { background: #fff5f5; color: #e53e3e; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #feb2b2; margin-bottom: 15px;}
    .report-box { background: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px dashed #666; margin-top: 10px;}
    </style>
""", unsafe_allow_html=True)

def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- NAVIGATION ---
choice = st.sidebar.selectbox("Navigation", ["User Panel", "Admin Panel"])

if choice == "User Panel":
    if st.session_state.step == "Selection":
        st.header("Select Payment Method")
        if st.button("📱 UPI ID"): st.session_state.pay_method = "UPI"; navigate_to("Amount")
        if st.button("📸 Scan QR Code"): st.session_state.pay_method = "QR"; navigate_to("Amount")
        if st.button("🏦 Bank IMPS"): st.session_state.pay_method = "Bank"; navigate_to("Amount")

    elif st.session_state.step == "Amount":
        st.header("Deposit Details")
        amt = st.number_input("Amount (Min ₹500)", min_value=500.0, step=100.0)
        bonus = st.checkbox("Apply 5% Bonus (3x Rolling)")
        if st.button("Confirm Amount"):
            st.session_state.amount = amt
            st.session_state.bonus = "Yes" if bonus else "No"
            st.session_state.rolling = "3x Rolling" if bonus else "1x Rolling"
            st.session_state.start_time = datetime.now()
            navigate_to("Payment")

    elif st.session_state.step == "Payment":
        rem = timedelta(minutes=10) - (datetime.now() - st.session_state.start_time)
        if rem.total_seconds() <= 0:
            st.error("Session Expired"); st.button("Restart", on_click=lambda: navigate_to("Selection"))
        else:
            st.markdown(f'<div class="timer-box">⏳ Time Left: {int(rem.total_seconds()//60):02d}:{int(rem.total_seconds()%60):02d}</div>', unsafe_allow_html=True)
            st.subheader(f"Deposit: ₹{st.session_state.amount}")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.session_state.pay_method == "QR":
                    st.image(get_upi_qr(st.session_state.amount), caption="Scan to Pay")
                elif st.session_state.pay_method == "UPI":
                    st.info("UPI ID: shreeshyam101@ptyes")
                else:
                    st.markdown("**Federal Bank**<br>Acc: 24950100015849<br>IFSC: FDRL0002495", unsafe_allow_html=True)

            with c2:
                u_utr = st.text_input("14-Digit UTR Number", max_chars=14)
                u_file = st.file_uploader("Upload Screenshot", type=['jpg','png','jpeg'])
                if st.button("Submit Payment"):
                    if len(u_utr) != 14: st.error("UTR must be 14 digits.")
                    elif not u_file: st.error("Upload proof.")
                    else:
                        try:
                            path = f"screenshots/{u_utr}.png"
                            with open(path, "wb") as f: f.write(u_file.getbuffer())
                            st.session_state.current_utr = u_utr
                            st.session_state.ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                            c = conn.cursor()
                            c.execute("INSERT INTO transactions (timestamp, amount, method, txid, bonus_opted, rolling, ss_path, status, reason) VALUES (?,?,?,?,?,?,?,?,?)",
                                      (st.session_state.ts, st.session_state.amount, st.session_state.pay_method, u_utr, st.session_state.bonus, st.session_state.rolling, path, "Pending", ""))
                            conn.commit(); navigate_to("Success")
                        except sqlite3.IntegrityError: st.error("❌ Duplicate UTR.")

    elif st.session_state.step == "Success":
        st.success("✅ Submission Successful!")
        
        # Report Details
        details = {
            "timestamp": st.session_state.ts,
            "txid": st.session_state.current_utr,
            "amount": st.session_state.amount,
            "method": st.session_state.pay_method,
            "bonus": st.session_state.bonus,
            "rolling": st.session_state.rolling
        }
        report_text = create_report(details)
        
        st.markdown("### 📥 Download Your Report")
        st.download_button(label="Download Transaction Report", data=report_text, file_name=f"Report_{st.session_state.current_utr}.txt", mime="text/plain")
        
        st.markdown("""
        <div class="report-box">
        <strong>Steps to follow:</strong><br>
        1. Click the 'Download' button above.<br>
        2. Click the 'Send to WhatsApp' button below.<br>
        3. Attach the downloaded report file to the chat.
        </div>
        """, unsafe_allow_html=True)
        
        # WhatsApp Redirect
        wa_msg = f"Hello, I have made a deposit of ₹{st.session_state.amount}. My UTR is {st.session_state.current_utr}. Please verify my payment."
        encoded_msg = urllib.parse.quote(wa_msg)
        wa_url = f"https://wa.me/919294823595?text={encoded_msg}"
        
        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:15px; border-radius:8px; font-weight:bold; cursor:pointer;">📲 Send to WhatsApp</button></a>', unsafe_allow_html=True)
        
        if st.button("Make Another Deposit"): navigate_to("Selection")

elif choice == "Admin Panel":
    if not st.session_state.admin_logged_in:
        with st.form("admin"):
            pw = st.text_input("Admin Password", type="password")
            if st.form_submit_button("Enter"):
                if pw == "ShuB#2026!Fed_Admin_9x": st.session_state.admin_logged_in = True; st.rerun()
                else: st.error("Wrong Password")
    else:
        if st.sidebar.button("Logout"): st.session_state.admin_logged_in = False; st.rerun()
        pending = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        for i, r in pending.iterrows():
            with st.expander(f"UTR: {r['txid']} (₹{r['amount']})"):
                if os.path.exists(r['ss_path']): st.image(r['ss_path'], width=300)
                st.write(f"Bonus: {r['bonus_opted']} | Rolling: {r['rolling']}")
                reason = st.text_input("Decline Reason", key=f"r_{r['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Approve ✅", key=f"a_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
                if c2.button("Decline ❌", key=f"d_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id'])); conn.commit(); st.rerun()
