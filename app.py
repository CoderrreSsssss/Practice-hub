import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
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
                  screenshot_path TEXT,
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
st.set_page_config(page_title="Payment Portal", layout="centered")
st.markdown("""
    <style>
    .stButton button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .timer-box { background: #fff5f5; color: #e53e3e; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #feb2b2; margin-bottom: 20px; }
    .bank-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION HELPERS ---
def navigate_to(step):
    st.session_state.step = step
    st.rerun()

# --- MAIN APP LOGIC ---
menu = ["User Panel", "Admin Panel"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "User Panel":
    tabs = st.tabs(["Make Payment", "Check All Status"])

    with tabs[0]:
        # --- STEP 1: SELECT METHOD ---
        if st.session_state.step == "Selection":
            st.header("Select Payment Method")
            if st.button("📱 UPI ID"):
                st.session_state.pay_method = "UPI"
                navigate_to("Amount")
            if st.button("📸 Scan QR Code"):
                st.session_state.pay_method = "QR"
                navigate_to("Amount")
            if st.button("🏦 Bank Transfer"):
                st.session_state.pay_method = "Bank"
                navigate_to("Amount")

        # --- STEP 2: ENTER AMOUNT ---
        elif st.session_state.step == "Amount":
            st.header("Enter Amount")
            amt = st.number_input("Amount (₹)", min_value=1.0, step=1.0)
            if st.button("Proceed"):
                st.session_state.amount = amt
                st.session_state.start_time = datetime.now()
                navigate_to("Payment")
            if st.button("Back"): navigate_to("Selection")

        # --- STEP 3: PAYMENT PAGE ---
        elif st.session_state.step == "Payment":
            # Timer Calculation
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
                        else: st.info("QR Code Image Missing")
                    elif st.session_state.pay_method == "UPI":
                        st.info("UPI ID: shreeshyam101@ptyes")
                    else:
                        st.markdown("<div class='bank-card'>Federal Bank<br>A/C: 24950100015849<br>IFSC: FDRL0002495</div>", unsafe_allow_html=True)

                with col2:
                    u_name = st.text_input("Name")
                    u_utr = st.text_input("UTR (Must be 14 digits)", max_chars=14)
                    u_file = st.file_uploader("Screenshot", type=['jpg','png'])
                    
                    if st.button("Submit Payment"):
                        if len(u_utr) != 14:
                            st.error("❌ UTR must be exactly 14 digits.")
                        elif not u_name or not u_file:
                            st.error("❌ Fill all fields.")
                        else:
                            # Save entry
                            c = conn.cursor()
                            c.execute("INSERT INTO transactions (timestamp, name, amount, method, txid, status, reason) VALUES (?,?,?,?,?,?,?)",
                                      (datetime.now().strftime("%Y-%m-%d %H:%M"), u_name, st.session_state.amount, st.session_state.pay_method, u_utr, "Pending", ""))
                            conn.commit()
                            navigate_to("Success")

        # --- STEP 4: SUCCESS ---
        elif st.session_state.step == "Success":
            st.success("### ✅ Transaction Recorded!")
            st.write("Our team is verifying your payment. Check 'All Status' tab for updates.")
            if st.button("Back to Home"): navigate_to("Selection")

    with tabs[1]:
        st.header("Previous Transactions")
        history = pd.read_sql_query("SELECT timestamp, amount, txid, status, reason FROM transactions ORDER BY id DESC", conn)
        if not history.empty:
            st.table(history)
        else:
            st.info("No transactions found.")

elif choice == "Admin Panel":
    st.header("Admin Login")
    if not st.session_state.admin_logged_in:
        with st.form("admin_login"):
            password = st.text_input("Enter Admin Password", type="password")
            if st.form_submit_button("Submit Password"):
                if password == "ShuB#2026!Fed_Admin_9x":
                    st.session_state.admin_logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect Password")
    else:
        if st.sidebar.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
        st.subheader("Verification Requests")
        reqs = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending'", conn)
        
        if not reqs.empty:
            for i, r in reqs.iterrows():
                with st.expander(f"Request from {r['name']} - ₹{r['amount']}"):
                    st.write(f"**UTR:** {r['txid']}")
                    st.write(f"**Method:** {r['method']}")
                    st.write(f"**Time:** {r['timestamp']}")
                    
                    reason = st.text_input("Decline Reason (Optional)", key=f"res_{r['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Approve", key=f"app_{r['id']}"):
                        conn.execute("UPDATE transactions SET status='Approved' WHERE id=?", (r['id'],))
                        conn.commit()
                        st.rerun()
                    if c2.button("❌ Decline", key=f"dec_{r['id']}"):
                        conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (reason, r['id']))
                        conn.commit()
                        st.rerun()
        else:
            st.success("No pending requests.")
