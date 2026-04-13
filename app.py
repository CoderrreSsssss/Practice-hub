import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
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
                  txid TEXT,
                  status TEXT,
                  reason TEXT,
                  approved_amount REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- STYLING ---
st.set_page_config(page_title="Payment Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    .bank-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-top: 5px solid #004a99;
    }
    .status-pending { color: #f39c12; font-weight: bold; }
    .status-approved { color: #27ae60; font-weight: bold; }
    .status-declined { color: #c0392b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Make Payment", "Check Status", "Admin Panel"])

# --- PAGE 1: USER PAYMENT ---
if page == "Make Payment":
    st.title("💳 Secure Checkout")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 🏦 Payment Details")
        st.markdown(f"""
        <div class="bank-card">
            <h4 style="color:#004a99; margin-top:0;">Federal Bank</h4>
            <p><strong>Account Holder:</strong> Shubham Sharma</p>
            <p><strong>Account Number:</strong> 24950100015849</p>
            <p><strong>IFSC Code:</strong> FDRL0002495</p>
            <hr>
            <p><strong>UPI ID:</strong> <span style="background:#e8f0fe; padding:2px 5px;">shreeshyam101@ptyes</span></p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.subheader("Scan QR Code")
        # Ensure your image file is named exactly 'qr_code.png' in GitHub
        if os.path.exists("qr_code.png"):
            st.image("qr_code.png", width=300)
        else:
            st.info("Scan using the UPI ID provided on the left.")

    st.divider()

    st.subheader("Submit Payment Proof")
    with st.form("user_form", clear_on_submit=True):
        name = st.text_input("Your Full Name")
        amount = st.number_input("Amount Paid", min_value=1.0)
        txid = st.text_input("Transaction ID / UTR Number")
        uploaded_file = st.file_uploader("Upload Screenshot", type=['jpg','png','jpeg'])
        
        if st.form_submit_button("Submit Transaction"):
            if name and txid:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c = conn.cursor()
                c.execute("INSERT INTO transactions (timestamp, name, amount, txid, status, reason, approved_amount) VALUES (?,?,?,?,?,?,?)",
                          (now, name, amount, txid, "Pending", "", 0.0))
                conn.commit()
                st.success("✅ Transaction submitted successfully! Please check status later.")
            else:
                st.error("Please fill in all details.")

# --- PAGE 2: USER STATUS CHECK ---
elif page == "Check Status":
    st.title("🔍 Check Your Payment Status")
    search_txid = st.text_input("Enter your Transaction ID / UTR")
    
    if search_txid:
        query = pd.read_sql_query("SELECT status, reason, approved_amount FROM transactions WHERE txid=?", conn, params=(search_txid,))
        if not query.empty:
            status = query['status'][0]
            st.markdown(f"Current Status: <span class='status-{status.lower()}'>{status}</span>", unsafe_allow_html=True)
            if status == "Approved":
                st.balloons()
                st.info(f"Verified Amount: ₹{query['approved_amount'][0]}")
            elif status == "Declined":
                st.error(f"Reason: {query['reason'][0]}")
        else:
            st.warning("No record found for this Transaction ID.")

# --- PAGE 3: ADMIN PANEL ---
elif page == "Admin Panel":
    st.title("⚙️ Admin Control Panel")
    
    pw = st.sidebar.text_input("Admin Password", type="password")
    if pw == "admin123":
        data = pd.read_sql_query("SELECT * FROM transactions WHERE status='Pending' ORDER BY id DESC", conn)
        
        if not data.empty:
            for index, row in data.iterrows():
                with st.expander(f"Pending: {row['name']} (₹{row['amount']})"):
                    st.write(f"**UTR:** {row['txid']} | **Time:** {row['timestamp']}")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        app_amt = st.number_input("Confirm Amount", value=row['amount'], key=f"amt_{row['id']}")
                    with col_b:
                        dec_reason = st.text_input("Decline Reason", key=f"rec_{row['id']}")
                    
                    btn_col1, btn_col2 = st.columns(2)
                    if btn_col1.button(f"Approve ✅", key=f"app_{row['id']}"):
                        conn.execute("UPDATE transactions SET status='Approved', approved_amount=? WHERE id=?", (app_amt, row['id']))
                        conn.commit()
                        st.rerun()
                    
                    if btn_col2.button(f"Decline ❌", key=f"dec_{row['id']}"):
                        conn.execute("UPDATE transactions SET status='Declined', reason=? WHERE id=?", (dec_reason, row['id']))
                        conn.commit()
                        st.rerun()
        else:
            st.success("No pending transactions.")
            
        st.divider()
        st.subheader("All Records")
        history = pd.read_sql_query("SELECT * FROM transactions", conn)
        st.dataframe(history, use_container_width=True)
    else:
        st.info("Please enter the admin password in the sidebar to continue.")
