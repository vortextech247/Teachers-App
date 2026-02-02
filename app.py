import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, date
import time
import random
import string

# --- إعدادات الصفحة ---
st.set_page_config(page_title="EduMaster Pro", layout="wide", page_icon="🎓")

# --- إعدادات المدير ---
# هام: غير اسم الشيت هنا لو كنت سميته حاجة تانية
MASTER_SHEET_NAME = "Teachers_Master_DB"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# --- الاتصال بقاعدة البيانات (الطريقة الآمنة) ---
@st.cache_resource
def get_client():
    try:
        # هنا الكود بيسحب البيانات من Secrets تلقائياً
        # Scopes: الصلاحيات المطلوبة
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # تحويل بيانات السيكريت لبيانات اعتماد
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بجوجل: {e}")
        return None

client = get_client()

# لو مفيش اتصال نوقف التطبيق
if not client:
    st.info("💡 تأكد من وضع بيانات ملف JSON في الـ Secrets بشكل صحيح.")
    st.stop()

# --- دوال المساعدة ---
def get_master_db():
    try:
        return client.open(MASTER_SHEET_NAME)
    except Exception as e:
        st.error(f"❌ مش لاقي ملف الشيت '{MASTER_SHEET_NAME}'. تأكد إنك عملت Share لإيميل الروبوت.")
        st.stop()

# --- واجهة التطبيق ---
if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# (1) شاشة الدخول والتسجيل
if not st.session_state.logged_in_user:
    tab1, tab2, tab3 = st.tabs(["تسجيل دخول", "مدرس جديد", "إدارة"])
    
    # دخول المدرس
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
                except: st.error("خطأ في قراءة قاعدة البيانات")

    # تسجيل مدرس جديد
    with tab2:
        with st.form("signup"):
            code = st.text_input("كود التفعيل"); st.divider()
            c1, c2 = st.columns(2)
            new_u = c1.text_input("اسم المستخدم (إنجليزي)"); new_p = c2.text_input("كلمة المرور", type="password")
            name = st.text_input("الاسم"); phone = st.text_input("هاتف"); 
            c3, c4, c5 = st.columns(3); gov = c3.text_input("محافظة"); city = c4.text_input("مدينة"); sub = c5.text_input("مادة")
            
            if st.form_submit_button("إنشاء حساب"):
                if new_u and new_p and code:
                    try:
                        db = get_master_db()
                        codes_sh = db.worksheet("ActivationCodes")
                        users_sh = db.worksheet("Users")
                        
                        # التحقق من الكود
                        cell = codes_sh.find(code)
                        if cell and codes_sh.cell(cell.row, 3).value == "Available":
                            duration = int(codes_sh.cell(cell.row, 2).value)
                            
                            # إنشاء شيت خاص
                            new_sh_name = f"DB_{new_u}_{random.randint(1000,9999)}"
                            new_sh = client.create(new_sh_name)
                            # مشاركة الشيت مع الروبوت (بيحصل أوتوماتيك) ومع الإيميل الرئيسي لو حابب
                            new_sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='writer')
                            
                            # الهيكل
                            cols = ["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"]
                            new_sh.sheet1.append_row(cols)
                            
                            # الحفظ
                            exp = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")
                            users_sh.append_row([new_u, new_p, name, phone, gov, city, sub, "Premium", exp, "Active", new_sh.id])
                            
                            # حرق الكود
                            codes_sh.update_cell(cell.row, 3, "Used")
                            st.success("تم إنشاء الحساب بنجاح!"); st.balloons()
                        else:
                            st.error("كود غير صالح")
                    except Exception as e: st.error(f"خطأ: {e}")
                else: st.warning("اكمل البيانات")

    # دخول الأدمن
    with tab3:
        if st.text_input("Admin User") == ADMIN_USERNAME and st.text_input("Admin Pass", type="password") == ADMIN_PASSWORD:
            if st.button("توليد كود تجريبي"):
                db = get_master_db(); sh = db.worksheet("ActivationCodes")
                c = str(random.randint(10000,99999)); sh.append_row([c, 30, "Available", "", ""])
                st.success(f"الكود: {c}")

# (2) السيستم الداخلي (بعد الدخول)
elif st.session_state.logged_in_user:
    USER = st.session_state.logged_in_user
    st.title(f"أهلاً {USER['Full_Name']}")
    if st.button("خروج"): st.session_state.logged_in_user = None; st.rerun()
    
    # الاتصال بقاعدة بيانات المدرس
    try:
        user_sh = client.open_by_key(USER['Database_ID']).sheet1
        data = user_sh.get_all_records()
        df = pd.DataFrame(data)
        
        t1, t2 = st.tabs(["الحصص", "إضافة حصة"])
        with t1:
            st.dataframe(df)
        with t2:
            g = st.text_input("اسم المجموعة")
            if st.button("حفظ"):
                user_sh.append_row([g, "Normal", str(date.today()), "10:00", 100, "FALSE", 1, "", "", ""])
                st.success("تم"); st.rerun()
    except:
        st.error("جاري تجهيز قاعدة البيانات...")
