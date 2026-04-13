import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('payments.db', check_same_thread=False)
    c = conn.cursor()
    # Updated table schema to include Site Name, Username, Bonus, and Rolling
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
    conn.commit()
    return conn

conn = init_db()

# --- SESSION STATE ---
if 'step' not in st.session_state:
    st.session_state.step = "Selection"
if 'pay_method' not in st.session_state:
    st.session_state.pay_method = None
if 'amount' not in st.session_state:
    st.session_state.amount = 0.0
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

# --- NAVIGATION HELPERS ---
def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- MAIN APP ---
menu = ["User Panel", "Admin Panel"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "User Panel":
    tabs = st.tabs(["New Deposit", "My History"])

    with tabs[0]:
        # --- STEP 1: METHOD ---
        if st.session_state.step == "Selection":
            st.header("Select Payment Method")
            if st.button("📱 UPI / GPay / PhonePe"):
                st.session_state.pay_method = "UPI"; navigate_to("Amount")
            if st.button("📸 Scan QR Code"):
                st.session_state.pay_method = "QR"; navigate_to("Amount")
            if st.button("🏦 Bank Transfer (IMPS)"):
                st.session_state.pay_method = "Bank"; navigate_to("Amount")

        # --- STEP 2: DETAILS ---
        elif st.session_state.step == "Amount":
            st.header("Deposit Details")
            u_name = st.text_input("Username")
            s_name = st.text_input("Site Name")
            amt = st.number_input("Amount (₹)", min_value=100.0, step=100.0)
            
            st.markdown("### 🎁 Bonus Offer")
            bonus = st.checkbox("Get 5% Bonus (3x Rolling Required)")
            rolling_info = "3x Rolling" if bonus else "1x Rolling (Compulsory)"
            st.caption(f"Requirement: {rolling_info}")

            if st.button("Continue"):
                if u_name and s_name and amt >= 100:
                    st.session_state.username = u_name
                    st.session_state.sitename = s_name
                    st.session_state.amount = amt
                    st.session_state.bonus = "Yes" if bonus else "No"
                    st.session_state.rolling = rolling_info
                    st.session_state.start_time = datetime.now()
                    navigate_to("Payment")
                else:
                    st.warning("Please enter all details. Minimum deposit is ₹100.")
            if st.button("Back"): navigate_to("Selection")

        # --- STEP 3: PAYMENT & UTR ---
        elif st.session_state.step == "Payment":
            elapsed = datetime.now() - st.session_state.start_time
            rem = timedelta(minutes=10) - elapsed
            if rem.total_seconds() <= 0:
                st.error("Time Expired!")
                if st.button("Restart"): navigate_to("Selection")
            else:
                mins, secs = divmod(int(rem.total_seconds()), 60)
                st.markdown(f'<div class="timer-box">⏳ Time Left: {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)
                
                st.subheader(f"Paying: ₹{st.session_state.amount}")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.session_state.pay_method == "QR":
                        if os.path.exists("qr_code.png"): st.image("qr_code.png")
                        else: st.info("QR Code Image Not Found")
                    elif st.session_state.pay_method == "UPI":
                        st.info("UPI ID: shreeshyam101@ptyes")
                    else:
                        st.markdown("<div class='info-card'>Federal Bank<br>A/C: 24950100015849<br>IFSC: FDRL0002495</div>", unsafe_allow_html=True)

                with col2:
                    u_utr = st.text_input("UTR (14 Digits)", max_chars=14)
                    u_file = st.file_uploader("Upload Screenshot", type=['jpg','png','jpeg'])
                    
                    if st.button("Submit Deposit"):
                        if len(u_utr) != 14:
                            st.error("❌ UTR must be exactly 14 digits.")
                        else:
                            try:
                                c = conn.cursor()
                                c.execute("""INSERT INTO transactions 
                                          (timestamp, username, sitename, amount, method, txid, bonus_opted, rolling, status, reason) 
                                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                          (datetime.now().strftime("%Y-%m-%d %H:%M"), 
                                           st.session_state.username, st.session_state.sitename, 
                                           st.session_state.amount, st.session_state.pay_method, 
                                           u_utr, st.session_state.bonus, st.session_state.rolling, "Pending", ""))
                                conn.commit()
                                navigate_to("Success")
                            except sqlite3.IntegrityError:
                                st.error("❌ ERROR: This UTR is already used or duplicated. Please check your transaction.")

        elif st.session_state.step == "Success":
            st.success("### ✅ Submitted Successfully!")
            st.write("Our team is checking your transaction. Please wait 5-10 minutes.")
            if st.button("New Deposit"): navigate_to("Selection")

    with tabs[1]:
        st.header("Transaction Log")
        history = pd.read_sql_query("SELECT timestamp, username, amount, status, rolling, reason FROM transactions ORDER BY id DESC", conn)
        st.table(history)

elif choice == "Admin Panel":
    if not st.session_state.admin_logged_in:
        with st.form("login"):
            password = st.text_input("Admin Password", type="password")
            if st.form_submit_button("Enter Panel"):
                if password == "ShuB#2026!Fed_Admin_9x":
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else: st.error("Invalid Access")
    else:
        if st.sidebar.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
        st.subheader("Verification Queue")
        pending = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        
        for i, r in pending.iterrows():
            with st.expander(f"User: {r['username']} | ₹{r['amount']} | Site: {r['sitename']}"):
                st.write(f"**UTR:** `{r['txid']}`")
                st.write(f"**Bonus Opted:** {r['bonus_opted']} | **Requirement:** {r['rolling']}")
                
                reason = st.text_input("Decline Reason", key=f"r_{r['id']}")
                c1, c2 = st.columns(2)
                if c1.button("✅ Approve", key=f"a_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],))
                    conn.commit(); st.rerun()
                if c2.button("❌ Decline", key=f"d_{r['id']}"):
                    conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id']))
                    conn.commit(); st.rerun()
