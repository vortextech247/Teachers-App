import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, date
import json
import random
import string

# --- إعدادات الصفحة ---
st.set_page_config(page_title="EduMaster Pro", layout="wide", page_icon="🎓")

MASTER_SHEET_NAME = "Teachers_Master_DB"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# --- الاتصال بقاعدة البيانات ---
@st.cache_resource
def get_client():
    try:
        # الكود ده بيدور على مفتاح اسمه gcp_json في الـ Secrets
        if "gcp_json" not in st.secrets:
            st.error("❌ مفتاح 'gcp_json' غير موجود في Secrets.")
            st.stop()
            
        json_str = st.secrets["gcp_json"]
        info = json.loads(json_str)
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بجوجل: {e}")
        return None

client = get_client()

if not client: st.stop()

# --- دوال المساعدة ---
def get_master_db():
    try:
        return client.open(MASTER_SHEET_NAME)
    except Exception as e:
        # محاولة استخراج الايميل لمساعدة المستخدم
        try:
            email = json.loads(st.secrets["gcp_json"])["client_email"]
            st.error(f"❌ مش لاقي الشيت '{MASTER_SHEET_NAME}'.\n⚠️ تأكد إنك عملت Share للشيت مع الإيميل ده:\n**{email}**")
        except:
            st.error(f"❌ مش لاقي الشيت '{MASTER_SHEET_NAME}'. تأكد من الاسم والمشاركة.")
        st.stop()

# --- واجهة التطبيق ---
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# (1) شاشة الدخول
if not st.session_state.logged_in_user:
    st.title("🎓 نظام إدارة المدرسين")
    tab1, tab2, tab3 = st.tabs(["دخول", "تسجيل جديد", "إدارة"])
    
    with tab1:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("دخول"):
                try:
                    sh = get_master_db().worksheet("Users")
                    users = sh.get_all_records()
                    found = False
                    for user in users:
                        if str(user['Username']).lower() == u.lower() and str(user['Password']) == p:
                            if user['Status'] == 'Active':
                                st.session_state.logged_in_user = user
                                st.rerun()
                            else: st.error("حساب موقوف"); found=True
                    if not found: st.error("بيانات خاطئة")
                except Exception as e: st.error(f"خطأ: {e}")

    with tab2:
        with st.form("signup"):
            code = st.text_input("كود التفعيل"); st.divider()
            c1, c2 = st.columns(2); nu = c1.text_input("User"); np = c2.text_input("Pass", type="password")
            n = st.text_input("Name"); ph = st.text_input("Phone")
            c3, c4, c5 = st.columns(3); g = c3.text_input("Gov"); ci = c4.text_input("City"); s = c5.text_input("Subject")
            if st.form_submit_button("تسجيل"):
                if nu and np and code:
                    try:
                        db = get_master_db(); c_sh = db.worksheet("ActivationCodes"); u_sh = db.worksheet("Users")
                        try: cell = c_sh.find(code)
                        except: st.error("كود خاطئ"); cell=None
                        
                        if cell and c_sh.cell(cell.row, 3).value == "Available":
                            dur = int(c_sh.cell(cell.row, 2).value)
                            new_sh_name = f"DB_{nu}_{random.randint(1000,9999)}"
                            new_sh = client.create(new_sh_name)
                            email = json.loads(st.secrets["gcp_json"])["client_email"]
                            new_sh.share(email, perm_type='user', role='writer')
                            new_sh.sheet1.append_row(["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"])
                            exp = (datetime.now() + timedelta(days=dur)).strftime("%Y-%m-%d")
                            u_sh.append_row([nu, np, n, ph, g, ci, s, "Premium", exp, "Active", new_sh.id])
                            c_sh.update_cell(cell.row, 3, "Used"); c_sh.update_cell(cell.row, 4, nu); c_sh.update_cell(cell.row, 5, str(date.today()))
                            st.success("تم التسجيل!"); st.balloons()
                        else: st.error("كود غير صالح")
                    except Exception as e: st.error(f"خطأ: {e}")
                else: st.warning("اكمل البيانات")

    with tab3:
        au = st.text_input("A-User"); ap = st.text_input("A-Pass", type="password")
        if st.button("دخول"):
            if au == ADMIN_USERNAME and ap == ADMIN_PASSWORD: st.session_state.logged_in_user = "ADMIN"; st.rerun()

# (2) لوحة الأدمن والمدرس
elif st.session_state.logged_in_user == "ADMIN":
    st.title("Admin"); 
    if st.button("Logout"): st.session_state.logged_in_user = None; st.rerun()
    if st.button("Generate Code"):
        sh = get_master_db().worksheet("ActivationCodes")
        c = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        sh.append_row([c, 30, "Available", "", ""])
        st.success(f"Code: {c}")
    try: st.dataframe(pd.DataFrame(get_master_db().worksheet("ActivationCodes").get_all_records()))
    except: pass

elif st.session_state.logged_in_user:
    u = st.session_state.logged_in_user
    st.title(f"Welcome {u['Full_Name']}")
    if st.button("Logout"): st.session_state.logged_in_user = None; st.rerun()
    try:
        sh = client.open_by_key(u['Database_ID']).sheet1
        data = sh.get_all_values()
        if len(data) > 1: st.dataframe(pd.DataFrame(data[1:], columns=data[0]))
        else: st.info("لا توجد بيانات")
    except Exception as e: st.error(f"خطأ: {e}")
