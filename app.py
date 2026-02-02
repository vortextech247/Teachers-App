import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, date
import time
import random
import string

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="EduMaster Pro", layout="wide", page_icon="🎓")

# ==========================================
# ⚙️ إعدادات النظام (Admin Config)
# ==========================================
# بدل الاسم، هنستخدم المعرف المباشر من اللينك بتاعك
MASTER_SHEET_KEY = "1KSuSQiVezg4G8z_cmO4lZ2zZFJ96K0hreNFLyKqpQsA" 
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
# ==========================================
# 🔌 الاتصال بقاعدة البيانات (Master & Users)
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        # الاتصال باستخدام Secrets من Streamlit مباشرة
        # تأكد إنك حطيت بيانات الـ JSON في الـ Secrets
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], 
                                                                 ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

client = get_gspread_client()

if not client:
    st.error("❌ خطأ في الاتصال بالسيرفر. تأكد من إعدادات Secrets.")
    st.stop()

# ==========================================
# 🛠️ دوال النظام (System Functions)
# ==========================================

def get_master_db():
    try:
        # التعديل هنا: الفتح باستخدام الـ Key بدل الاسم
        return client.open_by_key(MASTER_SHEET_KEY)
    except Exception as e:
        st.error(f"❌ مش قادر أوصل لقاعدة البيانات. السبب: {e}")
        st.stop()

def check_login(username, password):
    master = get_master_db()
    users_sheet = master.worksheet("Users")
    all_users = users_sheet.get_all_records()
    
    for user in all_users:
        if str(user['Username']).lower() == username.lower() and str(user['Password']) == password:
            if user['Status'] == 'Active':
                return user
            else:
                return "Suspended"
    return None

def verify_code(code):
    master = get_master_db()
    codes_sheet = master.worksheet("ActivationCodes")
    try:
        cell = codes_sheet.find(code)
        if cell:
            row_data = codes_sheet.row_values(cell.row)
            # التأكد إن الكود مش مستخدم (Status = Available)
            # ترتيب الأعمدة: Code | Duration | Status | Used_By | Date
            if row_data[2] == "Available":
                return True, cell.row, row_data[1] # Return Row Index and Duration
    except:
        pass
    return False, None, None

def register_new_user(user_data, code_row, duration):
    master = get_master_db()
    users_sheet = master.worksheet("Users")
    codes_sheet = master.worksheet("ActivationCodes")
    
    # 1. التأكد إن اليوزر مش موجود
    existing = users_sheet.col_values(1)
    if user_data['Username'] in existing:
        return False, "اسم المستخدم موجود بالفعل!"

    try:
        # 2. إنشاء شيت خاص للمدرس (Isolation)
        new_sheet_name = f"DB_{user_data['Username']}_{random.randint(1000,9999)}"
        new_sheet = client.create(new_sheet_name)
        
        # مشاركة الشيت مع المدرس (اختياري لو عايز يدخل عليه من درايف)
        # new_sheet.share(user_email, perm_type='user', role='writer')
        
        # تجهيز الشيت بالأعمدة
        COLUMNS = ["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"]
        new_sheet.sheet1.append_row(COLUMNS)
        
        # 3. حفظ بيانات المدرس في الماستر
        expiry_date = (datetime.now() + timedelta(days=int(duration))).strftime("%Y-%m-%d")
        
        # الترتيب: Username | Password | Name | Phone | Gov | City | Subject | Plan | Expiry | Status | DB_ID
        row_to_add = [
            user_data['Username'], user_data['Password'], user_data['Full_Name'], user_data['Phone'],
            user_data['Gov'], user_data['City'], user_data['Subject'], 
            "Premium", expiry_date, "Active", new_sheet.id
        ]
        users_sheet.append_row(row_to_add)
        
        # 4. حرق الكود (Mark as Used)
        codes_sheet.update_cell(code_row, 3, "Used")
        codes_sheet.update_cell(code_row, 4, user_data['Username'])
        codes_sheet.update_cell(code_row, 5, str(datetime.now().date()))
        
        return True, "تم إنشاء الحساب وقاعدة البيانات بنجاح!"
        
    except Exception as e:
        return False, f"حدث خطأ أثناء الإنشاء: {str(e)}"

# ==========================================
# 🖥️ واجهة التطبيق (Main App)
# ==========================================

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None

# --- 1. صفحة الدخول والتسجيل ---
if not st.session_state.logged_in_user:
    tab1, tab2, tab3 = st.tabs(["🔒 تسجيل دخول", "📝 إنشاء حساب جديد", "🔑 المطور (Admin)"])
    
    # --- دخول المدرسين ---
    with tab1:
        with st.form("login_form"):
            u = st.text_input("اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                user = check_login(u, p)
                if isinstance(user, dict):
                    st.session_state.logged_in_user = user
                    st.toast("تم تسجيل الدخول بنجاح!")
                    time.sleep(0.5)
                    st.rerun()
                elif user == "Suspended":
                    st.error("⛔ هذا الحساب موقوف، تواصل مع الإدارة.")
                else:
                    st.error("بيانات خاطئة.")

    # --- تسجيل مدرس جديد ---
    with tab2:
        st.info("لإنشاء حساب، تحتاج إلى كود تفعيل من الإدارة.")
        with st.form("signup_form"):
            c_code = st.text_input("كود التفعيل (Activation Code)")
            st.divider()
            c1, c2 = st.columns(2)
            reg_user = c1.text_input("اسم المستخدم (إنجليزي فقط)").strip()
            reg_pass = c2.text_input("كلمة المرور", type="password")
            
            reg_name = st.text_input("الاسم بالكامل")
            reg_phone = st.text_input("رقم الهاتف")
            
            c3, c4, c5 = st.columns(3)
            reg_gov = c3.text_input("المحافظة")
            reg_city = c4.text_input("المدينة")
            reg_sub = c5.text_input("المادة")
            
            if st.form_submit_button("إنشاء الحساب وبدء العمل"):
                if reg_user and reg_pass and c_code:
                    is_valid, row_idx, duration = verify_code(c_code)
                    if is_valid:
                        with st.spinner("جاري بناء النظام الخاص بك..."):
                            user_data = {
                                "Username": reg_user, "Password": reg_pass, "Full_Name": reg_name,
                                "Phone": reg_phone, "Gov": reg_gov, "City": reg_city, "Subject": reg_sub
                            }
                            success, msg = register_new_user(user_data, row_idx, duration)
                            if success:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
                    else:
                        st.error("كود التفعيل غير صالح أو مستخدم من قبل.")
                else:
                    st.warning("يرجى ملء كافة البيانات.")

    # --- دخول الأدمن (أنت) ---
    with tab3:
        with st.form("admin_login"):
            au = st.text_input("Admin User")
            ap = st.text_input("Admin Pass", type="password")
            if st.form_submit_button("Access"):
                if au == ADMIN_USERNAME and ap == ADMIN_PASSWORD:
                    st.session_state.logged_in_user = "ADMIN_MODE"
                    st.rerun()
                else:
                    st.error("Access Denied")

# ==========================================
# 👨‍💼 لوحة تحكم المطور (ADMIN PANEL)
# ==========================================
elif st.session_state.logged_in_user == "ADMIN_MODE":
    st.markdown("## 👮‍♂️ لوحة تحكم الإدارة")
    if st.button("تسجيل خروج"):
        st.session_state.logged_in_user = None
        st.rerun()
    
    adm_tab1, adm_tab2 = st.tabs(["🎫 أكواد التفعيل", "👥 العملاء"])
    
    with adm_tab1:
        st.subheader("توليد أكواد جديدة")
        c1, c2 = st.columns(2)
        num_codes = c1.number_input("عدد الأكواد", 1, 50, 5)
        duration = c2.selectbox("المدة (أيام)", [30, 90, 180, 365])
        
        if st.button("توليد وحفظ"):
            master = get_master_db()
            codes_sh = master.worksheet("ActivationCodes")
            new_codes = []
            for _ in range(num_codes):
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                # Code | Duration | Status | Used_By | Date
                new_codes.append([code, duration, "Available", "", ""])
            
            codes_sh.append_rows(new_codes)
            st.success(f"تم إضافة {num_codes} كود بنجاح!")
            
        st.divider()
        st.write("الأكواد المتاحة حالياً:")
        master = get_master_db()
        codes_df = pd.DataFrame(master.worksheet("ActivationCodes").get_all_records())
        if not codes_df.empty:
            st.dataframe(codes_df)
            
    with adm_tab2:
        st.subheader("قاعدة بيانات العملاء")
        master = get_master_db()
        users_df = pd.DataFrame(master.worksheet("Users").get_all_records())
        st.dataframe(users_df)

# ==========================================
# 🎓 تطبيق المدرس (THE USER APP - V77 Logic)
# ==========================================
else:
    # هنا الكود بتاع المدرس، بس مربوط بالداتابيز بتاعته هو
    USER = st.session_state.logged_in_user
    USER_DB_ID = USER['Database_ID']
    
    # --- Side Bar Info ---
    with st.sidebar:
        st.title(f"أهلاً، أ/ {USER['Full_Name']}")
        st.caption(f"المادة: {USER['Subject']}")
        if st.button("تسجيل خروج"):
            st.session_state.logged_in_user = None
            st.rerun()
        st.divider()

    # --- دوال التعامل مع داتابيز المدرس الخاصة ---
    def get_user_sheet():
        return client.open_by_key(USER_DB_ID).sheet1

    COLUMNS = ["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"]
    ARABIC_DAYS = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الاربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
    NOW_CAIRO = datetime.utcnow() + timedelta(hours=2)
    TODAY_DATE = NOW_CAIRO.date()

    def load_user_data():
        sh = get_user_sheet()
        all_val = sh.get_all_values()
        if len(all_val) < 2: return pd.DataFrame(columns=COLUMNS)
        data = all_val[1:]
        clean = []
        for r in data:
            if len(r) < len(COLUMNS): r += [""] * (len(COLUMNS) - len(r))
            clean.append(r[:len(COLUMNS)])
        df = pd.DataFrame(clean, columns=COLUMNS)
        
        df['Date'] = df['Date'].astype(str).str.strip()
        df['Date_Parsed'] = pd.to_datetime(df['Date'], errors='coerce')
        if df['Date_Parsed'].isna().any(): df['Date_Parsed'] = df['Date_Parsed'].fillna(pd.Timestamp.today())
        df['Date'] = df['Date_Parsed'].dt.date
        df['Status'] = df['Status'].astype(str).str.strip().str.upper() == 'TRUE'
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0).astype(float)
        df['SessionNum'] = pd.to_numeric(df['SessionNum'], errors='coerce').fillna(0).astype(int)
        return df

    def save_user_data(df):
        sh = get_user_sheet()
        df_up = df.copy()
        df_up['Date'] = df_up['Date'].astype(str)
        df_up['Status'] = df_up['Status'].apply(lambda x: "TRUE" if x else "FALSE")
        df_up = df_up.fillna("")
        sh.clear()
        sh.update([COLUMNS] + df_up.values.tolist())
        st.cache_data.clear()
        return True

    def parse_time_robust(t_str):
        t_str = str(t_str).strip()
        try: return datetime.strptime(t_str, "%I:%M %p").time()
        except:
            try: return datetime.strptime(t_str, "%H:%M:%S").time()
            except:
                try: return datetime.strptime(t_str, "%H:%M").time()
                except: return datetime.strptime("10:00", "%H:%M").time()

    def get_students_list(s):
        if not s: return []
        return [x.strip() for x in str(s).split(',') if x.strip()]

    # --- Load Data ---
    if 'df' not in st.session_state: st.session_state.df = load_user_data()
    if st.sidebar.button("🔄 تحديث البيانات"): st.session_state.df = load_user_data(); st.rerun()
    df = st.session_state.df

    # --- Sidebar Stats ---
    with st.sidebar:
        d_m = TODAY_DATE.month if TODAY_DATE.day <= 25 else (TODAY_DATE.month % 12) + 1
        d_y = TODAY_DATE.year if TODAY_DATE.month != 12 or TODAY_DATE.day <= 25 else TODAY_DATE.year + 1
        s_m = st.selectbox("شهر الحساب", range(1, 13), index=d_m-1)
        t_d = datetime(d_y, s_m, 1)
        e_d = t_d.replace(day=25).date()
        s_d = (t_d.replace(day=1) - timedelta(days=1)).replace(day=26).date()
        
        calc_dates_fin = pd.to_datetime(df['Date'], errors='coerce').dt.date
        date_mask_fin = (calc_dates_fin >= s_d) & (calc_dates_fin <= e_d)
        mask_calc = date_mask_fin & (df['Status'] == True)
        prices = pd.to_numeric(df.loc[mask_calc, 'Price'], errors='coerce').fillna(0)
        st.metric("💰 دخل الشهر", f"{prices.sum()} ج.م")
        
        real_c = df[df['Type'] != 'Extra']
        all_g = sorted(list(set(real_c['Group']))) if not real_c.empty else []

    # --- Main Tabs ---
    tab_today, tab_man, tab_tbl, tab_crd, tab_fin, tab_new = st.tabs(["📅 اليوم", "🛠️ إدارة", "📊 جدول", "🗂️ كروت", "💰 حسابات", "➕ جديد"])

    # 1. TAB TODAY
    with tab_today:
        st.subheader(f"📅 حصص اليوم: {TODAY_DATE}")
        tds = df[df['Date'] == TODAY_DATE]
        if not tds.empty:
            for i, r in tds.iterrows():
                with st.container(border=True):
                    if r['Type'] == 'Extra': continue
                    st.markdown(f"**{r['Group']}** ({r['SessionNum']})")
                    if r['Status']: st.success("✅ تم")
                    else:
                        c1, c2 = st.columns(2)
                        st_obj = parse_time_robust(r['Time'])
                        start = c1.time_input("بدأ", value=st_obj, key=f"s{i}")
                        end = c2.time_input("انتهى", value=NOW_CAIRO.time(), key=f"e{i}")
                        
                        st.write("الغياب:"); sl = get_students_list(r['Students'])
                        pres = []; absn = []
                        cols = st.columns(3)
                        for idx, s in enumerate(sl):
                            if cols[idx%3].checkbox(s, True, key=f"at{i}{idx}"): pres.append(s)
                            else: absn.append(s)
                        
                        if st.button("💾 حفظ", key=f"sv{i}", type="primary"):
                            df.at[i, 'Status'] = True
                            df.at[i, 'Attendance'] = f"حضور: {len(pres)}"
                            df.at[i, 'Time'] = start.strftime("%I:%M %p")
                            save_user_data(df); st.session_state.df=df; st.success("تم!"); st.rerun()
                        
                        with st.expander("تأجيل"):
                            nd = st.date_input("يوم جديد", key=f"pd{i}")
                            if st.button("تأكيد", key=f"pb{i}"):
                                delta = nd - r['Date']
                                mask = (df['Group']==r['Group'])&(df['SessionNum']>=r['SessionNum'])
                                for ix in df[mask].index: df.at[ix,'Date'] += delta
                                save_user_data(df); st.session_state.df=df; st.rerun()
        else: st.info("لا توجد حصص اليوم")

    # 2. TAB MANAGE
    with tab_man:
        sg = st.selectbox("اختر الجروب:", ["..."]+all_g)
        if sg != "...":
            gf = df[df['Group']==sg].copy()
            gf = gf.sort_values("SessionNum")
            st.data_editor(gf, key=f"ge_{sg}", disabled=["Group"], hide_index=True)
            st.divider()
            
            c1, c2 = st.columns(2)
            with c1.expander("تعديل الطلاب"):
                curr = get_students_list(gf.iloc[0]['Students'] if not gf.empty else "")
                while len(curr) < 12: curr.append("")
                nl = []
                sc = st.columns(3)
                for x in range(12):
                    v = sc[x%3].text_input(f"طالب {x+1}", curr[x], key=f"st_{sg}_{x}")
                    if v.strip(): nl.append(v.strip())
                if st.button("حفظ الأسماء", key=f"sv_st_{sg}"):
                    df.loc[df['Group']==sg, 'Students'] = ",".join(nl)
                    save_user_data(df); st.session_state.df=df; st.rerun()
            
            with c2.expander("إضافة حصة"):
                last = gf['SessionNum'].max() if not gf.empty else 0
                dt = st.date_input("تاريخ", key=f"ad_dt_{sg}")
                if st.button("إضافة", key=f"ad_btn_{sg}"):
                    lr = gf.iloc[-1] if not gf.empty else None
                    tm = lr['Time'] if lr is not None else "10:00 AM"
                    pr = lr['Price'] if lr is not None else 0
                    stds = lr['Students'] if lr is not None else ""
                    nr = {"Group": sg, "Type": "Normal", "Date": str(dt), "Time": tm, "Price": pr, "Status": "FALSE", "SessionNum": last+1, "Students": stds, "Notes": "", "Attendance": ""}
                    df = pd.concat([df, pd.DataFrame([nr])], ignore_index=True)
                    save_user_data(df); st.session_state.df=df; st.rerun()
            
            st.markdown("#### تعديل وترحيل")
            sn = st.selectbox("رقم الحصة:", gf['SessionNum'].unique(), key=f"sn_{sg}")
            if sn:
                t_idx = df[(df['Group']==sg) & (df['SessionNum']==sn)].index
                if not t_idx.empty:
                    idx = t_idx[0]
                    cd = df.at[idx, 'Date']; ct = parse_time_robust(df.at[idx, 'Time'])
                    col1, col2 = st.columns(2)
                    with col1.container(border=True):
                        st.write("تعديل وترحيل")
                        nd = st.date_input("تاريخ جديد", cd, key=f"nd_{sg}_{sn}")
                        nt = st.time_input("وقت جديد", ct, key=f"nt_{sg}_{sn}")
                        if st.button("تطبيق", key=f"app_{sg}_{sn}"):
                            delta = nd - cd
                            msk = (df['Group']==sg) & (df['SessionNum'] >= sn)
                            for i in df[msk].index:
                                df.at[i, 'Date'] += delta
                                df.at[i, 'Time'] = nt.strftime("%I:%M %p")
                            save_user_data(df); st.session_state.df=df; st.rerun()
                    with col2.container(border=True):
                        st.write("حذف"); st.write("")
                        if st.button("حذف الحصة", key=f"del_{sg}_{sn}", type="primary"):
                            df = df.drop(idx).reset_index(drop=True)
                            save_user_data(df); st.session_state.df=df; st.rerun()

    # 3. TAB TABLE
    with tab_tbl:
        if not df.empty:
            res = []
            for g in all_g:
                s = df[df['Group']==g]
                d = int(s['Status'].sum()); t = len(s)
                res.append({"الجروب": g, "التقدم": f"{d}/{t}", "الباقي": t-d, "النهاية": s['Date'].max()})
            st.dataframe(pd.DataFrame(res), use_container_width=True)

    # 4. TAB CARDS
    with tab_crd:
        cols = st.columns(3)
        for idx, g in enumerate(all_g):
            with cols[idx%3]:
                with st.container(border=True):
                    s = df[df['Group']==g]
                    d = int(s['Status'].sum()); t = len(s)
                    st.markdown(f"### {g}")
                    if t>0: st.progress(d/t)
                    st.caption(f"{d}/{t}")
                    curr = float(s.iloc[0]['Price']) if not s.empty else 0.0
                    np = st.number_input("سعر", value=curr, key=f"prc_{g}")
                    if st.button("تحديث", key=f"up_{g}"):
                        df.loc[df['Group']==g, 'Price'] = np
                        save_user_data(df); st.session_state.df=df; st.rerun()
                    if st.button("حذف", key=f"dd_{g}"):
                        df=df[df['Group']!=g]; save_user_data(df); st.session_state.df=df; st.rerun()

    # 5. TAB FINANCE
    with tab_fin:
        c1,c2,c3 = st.columns([3,2,1])
        n = c1.text_input("وصف")
        m = c2.number_input("مبلغ", step=50.0)
        if c3.button("إضافة"):
            rw = {"Group": n, "Type": "Extra", "Date": str(date.today()), "Price": float(m), "Status": "TRUE", "SessionNum": 0, "Students": "", "Attendance": "", "Notes": "", "Time": ""}
            df = pd.concat([df, pd.DataFrame([rw])], ignore_index=True)
            save_user_data(df); st.session_state.df=df; st.rerun()
        
        st.divider()
        md = df[date_mask_fin & (df['Status']==True)].copy()
        if not md.empty:
            st.dataframe(md[['Date', 'Group', 'Price']], use_container_width=True)
            rem = df[date_mask_fin & (df['Status']==False)]['Price'].apply(pd.to_numeric, errors='coerce').sum()
            act = md['Price'].sum()
            c1,c2,c3 = st.columns(3)
            c1.metric("فعلي", f"{act}")
            c2.metric("متوقع", f"{rem}")
            c3.metric("كلي", f"{act+rem}")

    # 6. TAB NEW
    with tab_new:
        c1,c2 = st.columns(2)
        ng = c1.text_input("اسم الجروب")
        nt = c2.time_input("الوقت", value=datetime.strptime("10:00", "%H:%M").time())
        sd = st.date_input("البداية")
        cnt = st.number_input("عدد الحصص", 1, 50, 12)
        pr = st.number_input("السعر", step=50)
        st.write("الطلاب")
        sl = []
        c = st.columns(2)
        for i in range(8):
            v = c[i%2].text_input(f"ط {i+1}")
            if v: sl.append(v)
        
        if st.button("حفظ"):
            if ng and ng not in all_g:
                ts = nt.strftime("%I:%M %p")
                rows = []
                for i in range(cnt):
                    rows.append({"Group": ng, "Type": "Normal", "Date": sd+timedelta(days=i*7), "Time": ts, "Price": pr, "Status": False, "SessionNum": i+1, "Students": ",".join(sl), "Notes": "", "Attendance": ""})
                df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
                save_user_data(df); st.session_state.df=df; st.success("تم"); st.rerun()
            else: st.error("الاسم مكرر")
