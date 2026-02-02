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
# ده الـ ID المباشر للشيت بتاعك (أضمن من الاسم)
MASTER_SHEET_KEY = "1KSuSQiVezg4G8z_cmO4lZ2zZFJ96K0hreNFLyKqpQsA"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# ==========================================
# 🔌 الاتصال بقاعدة البيانات (Fixed Function)
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        # 1. تحميل البيانات وتنظيف المفتاح
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 🔥 الخطوة السحرية: تصحيح مفتاح التشفير يدوياً
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        # 2. الاتصال
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, 
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        # طباعة الخطأ بوضوح لو حصل
        st.error(f"❌ خطأ في الاتصال بالسيرفر: {e}")
        return None

client = get_gspread_client()

# وقف البرنامج لو الاتصال فشل
if not client:
    st.stop()

# ==========================================
# 🛠️ دوال النظام (System Functions)
# ==========================================

def get_master_db():
    try:
        # الفتح باستخدام الـ ID المباشر
        return client.open_by_key(MASTER_SHEET_KEY)
    except Exception as e:
        st.error(f"❌ مش قادر أوصل للشيت الرئيسي. تأكد من مشاركة (Share) الشيت مع إيميل الروبوت!\nالخطأ: {e}")
        st.stop()

def check_login(username, password):
    master = get_master_db()
    try:
        users_sheet = master.worksheet("Users")
    except:
        st.error("❌ مش لاقي صفحة 'Users' في الشيت الرئيسي.")
        st.stop()
        
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
    try:
        codes_sheet = master.worksheet("ActivationCodes")
    except:
        st.error("❌ مش لاقي صفحة 'ActivationCodes'.")
        return False, None, None

    try:
        cell = codes_sheet.find(code)
        if cell:
            row_data = codes_sheet.row_values(cell.row)
            # Code | Duration | Status | Used_By | Date
            if row_data[2] == "Available":
                return True, cell.row, row_data[1] 
    except:
        pass
    return False, None, None

def register_new_user(user_data, code_row, duration):
    master = get_master_db()
    users_sheet = master.worksheet("Users")
    codes_sheet = master.worksheet("ActivationCodes")
    
    existing = users_sheet.col_values(1)
    if user_data['Username'] in existing:
        return False, "اسم المستخدم موجود بالفعل!"

    try:
        # إنشاء شيت جديد
        new_sheet_name = f"DB_{user_data['Username']}_{random.randint(1000,9999)}"
        new_sheet = client.create(new_sheet_name)
        
        # مشاركة الشيت مع إيميل الروبوت نفسه (تأكيد)
        new_sheet.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='writer')
        
        COLUMNS = ["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"]
        new_sheet.sheet1.append_row(COLUMNS)
        
        expiry_date = (datetime.now() + timedelta(days=int(duration))).strftime("%Y-%m-%d")
        
        row_to_add = [
            user_data['Username'], user_data['Password'], user_data['Full_Name'], user_data['Phone'],
            user_data['Gov'], user_data['City'], user_data['Subject'], 
            "Premium", expiry_date, "Active", new_sheet.id
        ]
        users_sheet.append_row(row_to_add)
        
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

if not st.session_state.logged_in_user:
    tab1, tab2, tab3 = st.tabs(["🔒 تسجيل دخول", "📝 إنشاء حساب جديد", "🔑 المطور (Admin)"])
    
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
                    st.error("⛔ هذا الحساب موقوف.")
                else:
                    st.error("بيانات خاطئة.")

    with tab2:
        st.info("لإنشاء حساب، تحتاج إلى كود تفعيل.")
        with st.form("signup_form"):
            c_code = st.text_input("كود التفعيل")
            st.divider()
            c1, c2 = st.columns(2)
            reg_user = c1.text_input("اسم المستخدم (إنجليزي)").strip()
            reg_pass = c2.text_input("كلمة المرور", type="password")
            reg_name = st.text_input("الاسم بالكامل")
            reg_phone = st.text_input("رقم الهاتف")
            c3, c4, c5 = st.columns(3)
            reg_gov = c3.text_input("المحافظة")
            reg_city = c4.text_input("المدينة")
            reg_sub = c5.text_input("المادة")
            
            if st.form_submit_button("إنشاء الحساب"):
                if reg_user and reg_pass and c_code:
                    is_valid, row_idx, duration = verify_code(c_code)
                    if is_valid:
                        with st.spinner("جاري بناء النظام..."):
                            user_data = {"Username": reg_user, "Password": reg_pass, "Full_Name": reg_name, "Phone": reg_phone, "Gov": reg_gov, "City": reg_city, "Subject": reg_sub}
                            success, msg = register_new_user(user_data, row_idx, duration)
                            if success:
                                st.success(msg); st.balloons()
                            else:
                                st.error(msg)
                    else:
                        st.error("كود التفعيل غير صالح.")
                else:
                    st.warning("املأ البيانات.")

    with tab3:
        with st.form("admin_login"):
            au = st.text_input("User"); ap = st.text_input("Pass", type="password")
            if st.form_submit_button("Access"):
                if au == ADMIN_USERNAME and ap == ADMIN_PASSWORD:
                    st.session_state.logged_in_user = "ADMIN_MODE"; st.rerun()
                else: st.error("Access Denied")

elif st.session_state.logged_in_user == "ADMIN_MODE":
    st.markdown("## 👮‍♂️ Admin Panel")
    if st.button("Logout"): st.session_state.logged_in_user = None; st.rerun()
    t1, t2 = st.tabs(["Codes", "Users"])
    with t1:
        c1, c2 = st.columns(2)
        nc = c1.number_input("Count", 1, 50, 5)
        dr = c2.selectbox("Days", [30, 90, 180, 365])
        if st.button("Generate"):
            m = get_master_db(); sh = m.worksheet("ActivationCodes")
            res = []
            for _ in range(nc):
                res.append([''.join(random.choices(string.ascii_uppercase + string.digits, k=10)), dr, "Available", "", ""])
            sh.append_rows(res); st.success("Done!")
        st.dataframe(pd.DataFrame(get_master_db().worksheet("ActivationCodes").get_all_records()))
    with t2:
        st.dataframe(pd.DataFrame(get_master_db().worksheet("Users").get_all_records()))

else:
    # --- USER APP ---
    USER = st.session_state.logged_in_user
    USER_DB_ID = USER['Database_ID']
    
    with st.sidebar:
        st.title(f"Hi, {USER['Full_Name']}")
        st.caption(f"Subject: {USER['Subject']}")
        if st.button("Logout"): st.session_state.logged_in_user = None; st.rerun()
        st.divider()

    def get_user_sheet(): return client.open_by_key(USER_DB_ID).sheet1
    COLUMNS = ["Group", "Type", "Date", "Time", "Price", "Status", "SessionNum", "Students", "Notes", "Attendance"]
    ARABIC_DAYS = {"Saturday": "السبت", "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء", "Wednesday": "الاربعاء", "Thursday": "الخميس", "Friday": "الجمعة"}
    NOW_CAIRO = datetime.utcnow() + timedelta(hours=2)
    TODAY_DATE = NOW_CAIRO.date()

    def load_user_data():
        try:
            sh = get_user_sheet()
            all_val = sh.get_all_values()
            if len(all_val) < 2: return pd.DataFrame(columns=COLUMNS)
            data = all_val[1:]; clean = []
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
        except Exception as e:
            st.error(f"Error loading user DB: {e}")
            return pd.DataFrame(columns=COLUMNS)

    def save_user_data(df):
        sh = get_user_sheet()
        df_up = df.copy()
        df_up['Date'] = df_up['Date'].astype(str)
        df_up['Status'] = df_up['Status'].apply(lambda x: "TRUE" if x else "FALSE")
        df_up = df_up.fillna("")
        sh.clear(); sh.update([COLUMNS] + df_up.values.tolist()); st.cache_data.clear(); return True

    def parse_time_robust(t_str):
        t_str = str(t_str).strip()
        try: return datetime.strptime(t_str, "%I:%M %p").time()
        except:
            try: return datetime.strptime(t_str, "%H:%M:%S").time()
            except:
                try: return datetime.strptime(t_str, "%H:%M").time()
                except: return datetime.strptime("10:00", "%H:%M").time()
    
    def get_students_list(s): return [x.strip() for x in str(s).split(',') if x.strip()]

    if 'df' not in st.session_state: st.session_state.df = load_user_data()
    if st.sidebar.button("Refresh"): st.session_state.df = load_user_data(); st.rerun()
    df = st.session_state.df

    with st.sidebar:
        d_m = TODAY_DATE.month if TODAY_DATE.day <= 25 else (TODAY_DATE.month % 12) + 1
        d_y = TODAY_DATE.year if TODAY_DATE.month != 12 or TODAY_DATE.day <= 25 else TODAY_DATE.year + 1
        s_m = st.selectbox("Month", range(1, 13), index=d_m-1)
        t_d = datetime(d_y, s_m, 1); e_d = t_d.replace(day=25).date()
        s_d = (t_d.replace(day=1) - timedelta(days=1)).replace(day=26).date()
        calc_dates_fin = pd.to_datetime(df['Date'], errors='coerce').dt.date
        date_mask_fin = (calc_dates_fin >= s_d) & (calc_dates_fin <= e_d)
        mask_calc = date_mask_fin & (df['Status'] == True)
        prices = pd.to_numeric(df.loc[mask_calc, 'Price'], errors='coerce').fillna(0)
        st.metric("Income", f"{prices.sum()} EGP")
        real_c = df[df['Type'] != 'Extra']
        all_g = sorted(list(set(real_c['Group']))) if not real_c.empty else []

    tab_today, tab_man, tab_tbl, tab_crd, tab_fin, tab_new = st.tabs(["Today", "Manage", "Table", "Cards", "Finance", "New"])

    with tab_today:
        st.subheader(f"Today: {TODAY_DATE}")
        tds = df[df['Date'] == TODAY_DATE]
        if not tds.empty:
            for i, r in tds.iterrows():
                with st.container(border=True):
                    if r['Type'] == 'Extra': continue
                    st.markdown(f"**{r['Group']}** ({r['SessionNum']})")
                    if r['Status']: st.success("Done")
                    else:
                        c1, c2 = st.columns(2)
                        st_obj = parse_time_robust(r['Time'])
                        start = c1.time_input("Start", value=st_obj, key=f"s{i}")
                        end = c2.time_input("End", value=NOW_CAIRO.time(), key=f"e{i}")
                        sl = get_students_list(r['Students']); pres = []
                        cols = st.columns(3)
                        for idx, s in enumerate(sl):
                            if cols[idx%3].checkbox(s, True, key=f"at{i}{idx}"): pres.append(s)
                        if st.button("Save", key=f"sv{i}", type="primary"):
                            df.at[i, 'Status'] = True; df.at[i, 'Attendance'] = f"P: {len(pres)}"
                            df.at[i, 'Time'] = start.strftime("%I:%M %p")
                            save_user_data(df); st.session_state.df=df; st.success("Saved"); st.rerun()
                        with st.expander("Postpone"):
                            nd = st.date_input("New Date", key=f"pd{i}")
                            if st.button("Confirm", key=f"pb{i}"):
                                delta = nd - r['Date']
                                mask = (df['Group']==r['Group'])&(df['SessionNum']>=r['SessionNum'])
                                for ix in df[mask].index: df.at[ix,'Date'] += delta
                                save_user_data(df); st.session_state.df=df; st.rerun()
        else: st.info("No sessions today")

    with tab_man:
        sg = st.selectbox("Group:", ["..."]+all_g)
        if sg != "...":
            gf = df[df['Group']==sg].copy().sort_values("SessionNum")
            st.data_editor(gf, key=f"ge_{sg}", disabled=["Group"], hide_index=True)
            st.divider()
            c1, c2 = st.columns(2)
            with c1.expander("Students"):
                curr = get_students_list(gf.iloc[0]['Students'] if not gf.empty else "")
                while len(curr) < 12: curr.append("")
                nl = []
                sc = st.columns(3)
                for x in range(12):
                    v = sc[x%3].text_input(f"S{x+1}", curr[x], key=f"st_{sg}_{x}")
                    if v.strip(): nl.append(v.strip())
                if st.button("Save Students", key=f"sv_st_{sg}"):
                    df.loc[df['Group']==sg, 'Students'] = ",".join(nl)
                    save_user_data(df); st.session_state.df=df; st.rerun()
            with c2.expander("Add Session"):
                last = gf['SessionNum'].max() if not gf.empty else 0
                dt = st.date_input("Date", key=f"ad_dt_{sg}")
                if st.button("Add", key=f"ad_btn_{sg}"):
                    lr = gf.iloc[-1] if not gf.empty else None
                    tm = lr['Time'] if lr is not None else "10:00 AM"; pr = lr['Price'] if lr is not None else 0
                    stds = lr['Students'] if lr is not None else ""
                    nr = {"Group": sg, "Type": "Normal", "Date": str(dt), "Time": tm, "Price": pr, "Status": "FALSE", "SessionNum": last+1, "Students": stds, "Notes": "", "Attendance": ""}
                    df = pd.concat([df, pd.DataFrame([nr])], ignore_index=True)
                    save_user_data(df); st.session_state.df=df; st.rerun()
            st.markdown("#### Edit & Shift")
            sn = st.selectbox("Session #:", gf['SessionNum'].unique(), key=f"sn_{sg}")
            if sn:
                t_idx = df[(df['Group']==sg) & (df['SessionNum']==sn)].index
                if not t_idx.empty:
                    idx = t_idx[0]
                    cd = df.at[idx, 'Date']; ct = parse_time_robust(df.at[idx, 'Time'])
                    col1, col2 = st.columns(2)
                    with col1.container(border=True):
                        nd = st.date_input("New Date", cd, key=f"nd_{sg}_{sn}")
                        nt = st.time_input("New Time", ct, key=f"nt_{sg}_{sn}")
                        if st.button("Apply to All", key=f"app_{sg}_{sn}"):
                            delta = nd - cd; msk = (df['Group']==sg) & (df['SessionNum'] >= sn)
                            for i in df[msk].index:
                                df.at[i, 'Date'] += delta; df.at[i, 'Time'] = nt.strftime("%I:%M %p")
                            save_user_data(df); st.session_state.df=df; st.rerun()
                    with col2.container(border=True):
                        if st.button("Delete", key=f"del_{sg}_{sn}", type="primary"):
                            df = df.drop(idx).reset_index(drop=True); save_user_data(df); st.session_state.df=df; st.rerun()

    with tab_tbl:
        if not df.empty:
            res = []
            for g in all_g:
                s = df[df['Group']==g]; d = int(s['Status'].sum()); t = len(s)
                res.append({"Group": g, "Prog": f"{d}/{t}", "Rem": t-d, "End": s['Date'].max()})
            st.dataframe(pd.DataFrame(res), use_container_width=True)

    with tab_crd:
        cols = st.columns(3)
        for idx, g in enumerate(all_g):
            with cols[idx%3]:
                with st.container(border=True):
                    s = df[df['Group']==g]; d = int(s['Status'].sum()); t = len(s)
                    st.markdown(f"### {g}"); st.caption(f"{d}/{t}")
                    curr = float(s.iloc[0]['Price']) if not s.empty else 0.0
                    np = st.number_input("Price", value=curr, key=f"prc_{g}")
                    if st.button("Update", key=f"up_{g}"):
                        df.loc[df['Group']==g, 'Price'] = np; save_user_data(df); st.session_state.df=df; st.rerun()

    with tab_fin:
        c1,c2,c3 = st.columns([3,2,1])
        n = c1.text_input("Desc"); m = c2.number_input("Amount", step=50.0)
        if c3.button("Add"):
            rw = {"Group": n, "Type": "Extra", "Date": str(date.today()), "Price": float(m), "Status": "TRUE", "SessionNum": 0, "Students": "", "Attendance": "", "Notes": "", "Time": ""}
            df = pd.concat([df, pd.DataFrame([rw])], ignore_index=True); save_user_data(df); st.session_state.df=df; st.rerun()
        st.divider()
        md = df[date_mask_fin & (df['Status']==True)].copy()
        if not md.empty:
            st.dataframe(md[['Date', 'Group', 'Price']], use_container_width=True)

    with tab_new:
        c1,c2 = st.columns(2); ng = c1.text_input("Name"); nt = c2.time_input("Time", value=datetime.strptime("10:00", "%H:%M").time())
        sd = st.date_input("Start"); cnt = st.number_input("Count", 1, 50, 12); pr = st.number_input("Price", step=50)
        sl = []; c = st.columns(2)
        for i in range(8):
            v = c[i%2].text_input(f"St {i+1}")
            if v: sl.append(v)
        if st.button("Save"):
            if ng and ng not in all_g:
                ts = nt.strftime("%I:%M %p"); rows = []
                for i in range(cnt): rows.append({"Group": ng, "Type": "Normal", "Date": sd+timedelta(days=i*7), "Time": ts, "Price": pr, "Status": False, "SessionNum": i+1, "Students": ",".join(sl), "Notes": "", "Attendance": ""})
                df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True); save_user_data(df); st.session_state.df=df; st.success("Saved"); st.rerun()
            else: st.error("Exists")
