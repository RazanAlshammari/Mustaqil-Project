# -*- coding: utf-8 -*-
"""
مستقل | Mustaqil، الرفيق المالي الذكي للفريلانسر السعودي
هاكاثون أمد، مصرف الإنماء × أكاديمية طويق

طريقة التشغيل:
    1) pip install streamlit pandas numpy scikit-learn plotly openpyxl
    2) ضع هذا الملف بجانب ملف البيانات mustaqil_dataset_v2.xlsx
    3) في الترمنال:  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, r2_score, mean_absolute_error, roc_auc_score
from datetime import datetime, timezone
import qrcode
import db
import os

# ═══════════════════════════════════════════════════════════════
#  إعداد الصفحة والهوية البصرية
# ═══════════════════════════════════════════════════════════════
st.set_page_config(page_title="مستقل | Mustaqil", layout="wide")

# ألوان مصرف الإنماء (أخضر) + لمسة عصرية
PRIMARY   = "#00833E"   # أخضر الإنماء
ACCENT    = "#C9A227"   # ذهبي
DARK      = "#0E2A1F"
DRY_RED   = "#E63946"

# الشعار ورمز الريال: يُقرآن من ملفَي الصورة الموضوعين بجوار app_v2.py
import base64, io

def _img_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

def _riyal_versions(path):
    """يحوّل خلفية رمز الريال البيضاء إلى شفافة، ويُنتج نسختين:
       داكنة (اللون الأصلي) وبيضاء (للخلفيات الملوّنة). يرجّع (dark_b64, white_b64)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        img.thumbnail((64, 64))                       # تصغير لتفادي بطء التطبيق
        px = list(img.getdata())
        dark, white = [], []
        for r, g, b, a in px:
            if r > 225 and g > 225 and b > 225:      # خلفية بيضاء -> شفافة
                dark.append((255, 255, 255, 0))
                white.append((255, 255, 255, 0))
            else:                                     # جسم الرمز
                dark.append((r, g, b, 255))
                white.append((255, 255, 255, 255))
        d = img.copy(); d.putdata(dark)
        w = img.copy(); w.putdata(white)
        def enc(im):
            buf = io.BytesIO(); im.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        return enc(d), enc(w)
    except Exception:
        return "", ""

def _logo_b64(path, maxpx=260):
    """يقرأ الشعار ويصغّره لتفادي بطء التطبيق."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        img.thumbnail((maxpx, maxpx))
        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return _img_b64(path)     # احتياطي: بالحجم الأصلي

LOGO_B64 = _logo_b64("mustaqil_logo.jpeg")
_RIYAL_DARK_B64, _RIYAL_WHITE_B64 = _riyal_versions("Riyal_logo.jpeg")

if _RIYAL_DARK_B64:
    RIYAL = ('<img src="data:image/png;base64,' + _RIYAL_DARK_B64 +
             '" style="height:0.82em;vertical-align:-0.04em;margin:0 2px">')
    RIYAL_WHITE = ('<img src="data:image/png;base64,' + _RIYAL_WHITE_B64 +
                   '" style="height:0.82em;vertical-align:-0.04em;margin:0 2px">')
    _RIYAL_IMG = _RIYAL_DARK_B64      # للوثيقة (خلفية بيضاء)
else:
    RIYAL = RIYAL_WHITE = _RIYAL_IMG = "ريال"

# خط ثمانية (Thmanyah Sans)، مُضمَّن Base64 من مجلد fonts/ بلا اتصال إنترنت،
# يحلّ محل Tajawal في الصفحة الرئيسية وفي كل مستند PDF يُصدره التطبيق.
def _font_face_css():
    weights = [("Regular", 400), ("Medium", 500), ("Bold", 700), ("Black", 900)]
    faces = []
    for name, w in weights:
        b64 = _img_b64(os.path.join("fonts", f"thmanyahsans-{name}.woff2"))
        if not b64:
            continue
        faces.append(f"""@font-face {{
  font-family: 'ThmanyahSans';
  src: url(data:font/woff2;base64,{b64}) format('woff2');
  font-weight: {w}; font-style: normal; font-display: swap;
}}""")
    return "\n".join(faces)

FONT_FACE_CSS = _font_face_css()
FONT_FAMILY = "'ThmanyahSans', 'Tajawal', sans-serif"
FONT_FAMILY_PLOTLY = "ThmanyahSans, Tajawal, sans-serif"
RIYAL_TXT = 'ريال'   # للنصوص التي لا تعرض HTML (st.success / st.caption / plotly)

st.markdown(f"""
<style>
    {FONT_FACE_CSS}

    html, body, [class*="css"] {{
        font-family: {FONT_FAMILY};
        direction: rtl;
    }}
    /* عناصر الإدخال (زر/حقل/قائمة) لا ترث الخط من body افتراضياً في المتصفح،
       لذا نفرض الخط صراحةً عليها وعلى كل عناصر ستريملت مع !important حتى
       لا تُغلَب بخط ستريملت الافتراضي المحمَّل لاحقاً في الصفحة.
       ملاحظة مهمّة: نستثني عناصر أيقونات ستريملت (Material Symbols)، لأن فرض
       خط النصوص عليها يُخفي الأيقونة ويُظهر اسمها كنصّ (مثل keyboard_arrow_down). */
    [data-testid], [data-testid] *,
    button, input, select, textarea, option, label {{
        font-family: {FONT_FAMILY} !important;
    }}
    [data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *,
    .material-symbols-rounded, .material-symbols-outlined, .material-icons,
    span[class*="material-symbols"], span[class*="material-icons"],
    [data-testid="stExpanderToggleIcon"], [data-testid="stBaseButton-headerNoPadding"] *,
    [data-testid="stSidebarCollapseButton"] *, [data-testid="stSidebarCollapsedControl"] *,
    [data-baseweb="icon"], [data-baseweb="icon"] *, svg, svg * {{
        font-family: "Material Symbols Rounded", "Material Symbols Outlined",
                     "Material Icons" !important;
    }}
    .stApp {{ background: linear-gradient(160deg,#f6faf7 0%,#eef5f0 100%); }}

    .hero {{
        background: linear-gradient(135deg,{PRIMARY} 0%,{DARK} 100%);
        padding: 34px 40px; border-radius: 22px; color:#fff;
        box-shadow: 0 12px 40px rgba(0,131,62,.25); margin-bottom: 8px;
    }}
    .hero h1 {{ font-size: 44px; font-weight:800; margin:0; }}
    .hero p  {{ font-size: 18px; opacity:.92; margin:6px 0 0; }}
    .badge {{
        display:inline-block; background:{ACCENT}; color:{DARK};
        padding:4px 14px; border-radius:30px; font-weight:700; font-size:13px;
    }}
    .metric-card {{
        background:#fff; border-radius:18px; padding:22px;
        box-shadow:0 4px 18px rgba(0,0,0,.06); border-right:5px solid {PRIMARY};
        height:100%;
    }}
    .metric-card.gold   {{ border-right-color:{ACCENT}; }}
    .metric-val   {{ font-size:30px; font-weight:800; color:{DARK}; }}
    .metric-label {{ font-size:14px; color:#6b7c72; font-weight:500; }}

    .salary-box {{
        background:linear-gradient(135deg,{PRIMARY},#00a350);
        border-radius:22px; padding:30px; color:#fff; text-align:center;
        box-shadow:0 10px 30px rgba(0,131,62,.3);
    }}
    .salary-box .num {{ font-size:52px; font-weight:800; }}

    .alert-dry {{
        background:linear-gradient(135deg,{DRY_RED},#c1121f); color:#fff;
        padding:20px 26px; border-radius:18px; font-weight:600; font-size:17px;
        box-shadow:0 8px 24px rgba(230,57,70,.3);
    }}
    .alert-safe {{
        background:linear-gradient(135deg,#2a9d8f,#21867a); color:#fff;
        padding:20px 26px; border-radius:18px; font-weight:600; font-size:17px;
    }}
    section[data-testid="stSidebar"] {{ background:{DARK}; }}
    section[data-testid="stSidebar"] * {{ color:#eafff2 !important; }}
    /* بطاقة «اختر الحساب»: خلفية بيضاء ونص داكن مضمون. نستهدف غلاف ستريملت
       الثابت stSelectbox بدل تفاصيل BaseWeb الداخلية التي تتغيّر بين الإصدارات. */
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] {{
        background:#ffffff !important;
        border-radius:10px; padding:6px 10px; margin-bottom:6px;
    }}
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] * {{
        color:#0E2A1F !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSelectbox"] svg {{
        fill:#0E2A1F !important;
    }}
    /* قائمة الخيارات المنسدلة تُعرض خارج الشريط الجانبي (portal)، فتُنسَّق منفصلة */
    div[data-baseweb="popover"] {{ background:#ffffff !important; }}
    div[data-baseweb="popover"] li {{ color:#0E2A1F !important; }}
    div[data-baseweb="popover"] * {{ color:#0E2A1F !important; }}
    .stButton>button {{
        background:{PRIMARY}; color:#fff; border-radius:12px; border:none;
        padding:10px 22px; font-weight:700; font-family:{FONT_FAMILY};
    }}
    /* فرض اتجاه العربية من اليمين في كل العناصر */
    .stApp, .main, section.main {{ direction: rtl; }}
    [data-testid="stMarkdownContainer"], [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"] {{ direction: rtl; text-align: right; }}
    /* شريط التبويبات: أول تبويب (اللوحة الرئيسية) في أقصى اليمين */
    .stTabs [data-baseweb="tab-list"] {{ direction: rtl; }}
    .stTabs [data-baseweb="tab"] {{ direction: rtl; }}
    /* أزرار وأسهم إدخال الأرقام: لونها أسود واضح */
    [data-testid="stNumberInput"] button {{ color:#0E2A1F !important; }}
    [data-testid="stNumberInput"] button svg {{ fill:#0E2A1F !important; stroke:#0E2A1F !important; }}
    [data-testid="stNumberInput"] input {{ color:#0E2A1F !important; }}
    /* أيقونة المساعدة: علامة استفهام واضحة بدل الدائرة الداكنة */
    [data-testid="stTooltipIcon"] {{ color:{PRIMARY} !important; }}
    [data-testid="stTooltipIcon"] svg {{ fill:{PRIMARY} !important; stroke:{PRIMARY} !important;
        width:18px; height:18px; }}
</style>
""", unsafe_allow_html=True)

MONTH_NAMES = {1:"يناير",2:"فبراير",3:"مارس",4:"أبريل",5:"مايو",6:"يونيو",
               7:"يوليو",8:"أغسطس",9:"سبتمبر",10:"أكتوبر",11:"نوفمبر",12:"ديسمبر"}

# ═══════════════════════════════════════════════════════════════
#  تحميل البيانات + تدريب النماذج (مع التخزين المؤقت)
# ═══════════════════════════════════════════════════════════════
@st.cache_data
def load_data():
    """يقرأ البيانات من قاعدة بيانات SQLite المحلية (تُزرع تلقائياً من ملف
    الإكسل عند أول تشغيل، راجع db.py)."""
    monthly = db.load_monthly()
    projects = db.load_projects()
    return monthly, projects

@st.cache_resource
def train_models(monthly, projects):
    """تدرّب النماذج الثلاثة وتحسب دقة كل واحد على بيانات اختبار منفصلة.
    كما تحفظ متوسط كل ميزة (baseline) لاستخدامه لاحقاً في تفسير كل توقّع فردي
    (تبويبات الجفاف/التسعير/العميل الخطر)، راجع explain_prediction أدناه."""
    metrics = {}
    baselines = {}

    # --- النموذج 1: التنبؤ بشهر الجفاف (تصنيف) ---
    m = monthly.sort_values(["Freelancer_ID","Year","Month"]).copy()
    m["dry"] = (m["Dry_Month_Label"]=="Yes").astype(int)
    m["Income_lag1"]  = m.groupby("Freelancer_ID")["Income"].shift(1)
    m["Income_roll3"] = m.groupby("Freelancer_ID")["Income"].transform(
        lambda x: x.rolling(3,min_periods=1).mean())
    m = m.dropna(subset=["Income_lag1"])
    f1 = ["Income_lag1","Income_roll3","Number_of_Projects","Total_Expenses","Month","Payment_Delay_Days"]
    Xtr,Xte,ytr,yte = train_test_split(m[f1], m["dry"], test_size=0.25,
                                       random_state=1, stratify=m["dry"])
    clf = RandomForestClassifier(n_estimators=150,random_state=1,class_weight="balanced")
    clf.fit(Xtr,ytr)
    metrics["dry_acc"] = accuracy_score(yte, clf.predict(Xte)) * 100
    clf.fit(m[f1], m["dry"])   # إعادة التدريب على كل البيانات للاستخدام الفعلي
    baselines["F1"] = m[f1].mean()

    # --- النموذج 2: التنبؤ بالدخل القادم (انحدار) ---
    # نضيف ميزات موسمية دورية (جيب/جيب تمام) لأن أشهر السنة دائرية:
    # ديسمبر ويناير متجاوران واقعياً، لكن رقمَيهما (12 و 1) متباعدان.
    m2 = m.dropna(subset=["Next_Month_Income"]).copy()
    m2["next_month"] = (m2["Month"] % 12) + 1
    m2["sin_m"] = np.sin(2*np.pi*m2["next_month"]/12)
    m2["cos_m"] = np.cos(2*np.pi*m2["next_month"]/12)
    m2["fl_mean"] = m2.groupby("Freelancer_ID")["Income"].transform("mean")
    m2["roll6"]   = m2.groupby("Freelancer_ID")["Income"].transform(
        lambda x: x.rolling(6, min_periods=1).mean())
    f2 = ["Income","Income_lag1","Income_roll3","roll6","fl_mean",
          "Number_of_Projects","next_month","sin_m","cos_m"]
    Xtr,Xte,ytr,yte = train_test_split(m2[f2], m2["Next_Month_Income"],
                                       test_size=0.25, random_state=1)
    reg = RandomForestRegressor(n_estimators=200,random_state=1)
    reg.fit(Xtr,ytr)
    pred = reg.predict(Xte)
    metrics["income_r2"]  = r2_score(yte, pred)
    metrics["income_mae"] = mean_absolute_error(yte, pred)
    reg.fit(m2[f2], m2["Next_Month_Income"])

    # --- النموذج 3: اقتراح تسعير المشروع (انحدار) ---
    p = pd.get_dummies(projects, columns=["Specialty","Client_Type"])
    # نستبعد أعمدة السداد لأنها تحدث *بعد* المشروع، استخدامها للتسعير تسريب بيانات
    drop = ["Project_ID","Freelancer_ID","Project_Value","Suggested_Price",
            "Payment_Delay_Days","Late_Payment","Defaulted"]
    f3 = [c for c in p.columns if c not in drop]
    Xtr,Xte,ytr,yte = train_test_split(p[f3], p["Suggested_Price"],
                                       test_size=0.25, random_state=1)
    reg2 = RandomForestRegressor(n_estimators=200,random_state=1)
    reg2.fit(Xtr,ytr)
    pred = reg2.predict(Xte)
    metrics["price_r2"]  = r2_score(yte, pred)
    metrics["price_mae"] = mean_absolute_error(yte, pred)
    reg2.fit(p[f3], p["Suggested_Price"])
    baselines["F3"] = p[f3].mean()

    # --- النموذج 4: كاشف العميل الخطر (تصنيف) ---
    pc = pd.get_dummies(projects, columns=["Client_Type","Specialty"])
    f4 = [c for c in pc.columns if c.startswith(("Client_Type_","Specialty_"))] + \
         ["Project_Value","Project_Duration_Days","Estimated_Hours","Complexity"]
    Xtr,Xte,ytr,yte = train_test_split(pc[f4], pc["Late_Payment"], test_size=0.25,
                                       random_state=1, stratify=pc["Late_Payment"])
    clf_late = RandomForestClassifier(n_estimators=200,random_state=1,class_weight="balanced")
    clf_late.fit(Xtr,ytr)
    metrics["late_acc"] = accuracy_score(yte, clf_late.predict(Xte)) * 100
    metrics["late_auc"] = roc_auc_score(yte, clf_late.predict_proba(Xte)[:,1])
    clf_late.fit(pc[f4], pc["Late_Payment"])
    baselines["F4"] = pc[f4].mean()

    return clf, f1, reg, f2, reg2, f3, clf_late, f4, metrics, baselines

monthly, projects = load_data()
(clf, F1, reg_income, F2, reg_price, F3, clf_late, F4, METRICS, BASELINES) = \
    train_models(monthly, projects)

# ═══════════════════════════════════════════════════════════════
#  الهيدر
# ═══════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="hero" style="display:flex;align-items:center;gap:26px">
  <img src="data:image/jpeg;base64,{LOGO_B64}"
       style="height:110px;background:#fff;border-radius:18px;padding:8px;flex-shrink:0">
  <div>
    <span class="badge">هاكاثون أمد · مصرف الإنماء</span>
    <h1 style="margin:8px 0 0">مستقل</h1>
    <p>الرفيق المالي الذكي للفريلانسر السعودي، راتبك أنت من يحدده</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  الشريط الجانبي، اختيار الفريلانسر
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### حساب الفريلانسر")
    names = monthly[["Freelancer_ID","Name"]].drop_duplicates()
    options = {f"{r.Name} (#{r.Freelancer_ID})": r.Freelancer_ID for r in names.itertuples()}
    pick = st.selectbox("اختر الحساب", list(options.keys()))
    fid = options[pick]
    st.markdown("---")
    SALARY_WINDOW = st.number_input("نافذة عدد الأشهر لحساب الراتب الاصطناعي",
                                    min_value=2, max_value=6, value=3, step=1)
    st.markdown("---")
    st.caption("مستقل، كل ريال له وظيفة،\nوكل فريلانسر له راتب")

user = monthly[monthly["Freelancer_ID"]==fid].sort_values(["Year","Month"]).reset_index(drop=True)
uname = user["Name"].iloc[0]
specialty = user["Specialty"].iloc[0]

# ═══════════════════════════════════════════════════════════════
#  مؤشر الجدارة الائتمانية للفريلانسر
#  الأوزان مشتقّة من البيانات (feature importance) لا من الاجتهاد:
#  درّبنا نموذجاً يتنبأ بالضائقة المالية (دخل الشهر القادم < مصاريفه)،
#  ثم استخدمنا أهمية كل محور في التنبؤ كوزن له. النتيجة:
#  صندوق الطوارئ 35 · استقرار الدخل 25 · تنوّع العملاء 20 · انتظام التحصيل 20
#  (AUC = 0.63، راجع derive_weights.py)
# ═══════════════════════════════════════════════════════════════
W_EMERGENCY, W_STABILITY, W_DIVERSITY, W_COLLECTION = 35, 25, 20, 20

def compute_credit_score(user_df, pj_df):
    """درجة جدارة من 100 على أربعة محاور، مع تفصيل كل محور."""
    inc  = user_df["Income"].tail(12)
    avg  = inc.mean()
    last = user_df.iloc[-1]

    # 1) صندوق الطوارئ (35)، 6 أشهر تغطية = الدرجة الكاملة
    cover = last.Emergency_Fund / max(1, last.Total_Expenses)
    s_eme = min(1.0, cover / 6) * W_EMERGENCY

    # 2) استقرار الدخل (25)
    cv = inc.std() / max(1, avg)
    s_sta = max(0.0, 1 - min(cv, 1.0)) * W_STABILITY

    # 3) تنوّع العملاء (20)، مؤشر HHI الاقتصادي لقياس التركّز
    if len(pj_df):
        share = pj_df.groupby("Client_Type")["Project_Value"].sum()
        share = share / share.sum()
        hhi = float((share**2).sum())          # 0.25 = تنوّع مثالي، 1 = عميل واحد
        div = max(0.0, (1 - hhi) / 0.75)
        vol = min(1.0, len(pj_df) / 20)
        s_div = (div * 0.7 + vol * 0.3) * W_DIVERSITY
    else:
        s_div = 0.0

    # 4) انتظام التحصيل (20)
    delay = user_df["Payment_Delay_Days"].tail(12).mean()
    s_col = max(0.0, 1 - min(delay, 45) / 45) * W_COLLECTION

    parts = {"صندوق الطوارئ": (s_eme, W_EMERGENCY),
             "استقرار الدخل": (s_sta, W_STABILITY),
             "تنوّع العملاء": (s_div, W_DIVERSITY),
             "انتظام التحصيل": (s_col, W_COLLECTION)}
    return round(s_eme+s_sta+s_div+s_col), parts, cover, delay

def score_grade(score):
    if score >= 80: return "ممتاز", "مؤهّل لتمويل بشروط تفضيلية", "#00833E"
    if score >= 65: return "جيد جداً", "مؤهّل لمعظم منتجات التمويل", "#2a9d8f"
    if score >= 50: return "جيد", "مؤهّل لتمويل محدود", "#C9A227"
    if score >= 35: return "مقبول", "يحتاج تحسيناً قبل التقديم", "#E76F51"
    return "ضعيف", "غير مؤهّل حالياً، ابدأ ببناء صندوق الطوارئ", "#E63946"

def improvement_tips(parts, cover, delay):
    """توصيات مرتّبة حسب أكبر فجوة."""
    tips = []
    gaps = sorted(parts.items(), key=lambda kv: (kv[1][1]-kv[1][0]), reverse=True)
    for name,(got,mx) in gaps:
        gap = mx - got
        if gap < 2: continue
        if name == "صندوق الطوارئ":
            tips.append(f"ارفع صندوق الطوارئ ليغطي 6 أشهر (يغطي حالياً {cover:.1f} شهر) "
                        f" يضيف حتى {gap:.0f} نقطة.")
        elif name == "استقرار الدخل":
            tips.append(f"ثبّت دخلك عبر عقود شهرية متكرّرة بدل المشاريع المتفرّقة "
                        f" يضيف حتى {gap:.0f} نقطة.")
        elif name == "تنوّع العملاء":
            tips.append(f"نوّع عملاءك ولا تعتمد على جهة واحدة، يضيف حتى {gap:.0f} نقطة.")
        elif name == "انتظام التحصيل":
            tips.append(f"قلّل تأخّر التحصيل (متوسّطه {delay:.0f} يوم) بطلب دفعة مقدّمة "
                        f" يضيف حتى {gap:.0f} نقطة.")
    return tips[:3]

# ═══════════════════════════════════════════════════════════════
#  تفسير كل توقّع فردي (لماذا خرج هذا الرقم بالذات)
#  الطريقة: نقارن توقّع النموذج على مدخلات المستخدم الفعلية بتوقّعه
#  لو استُبدلت كل ميزة، واحدة تلو الأخرى، بمتوسّطها عبر كل الفريلانسرز
#  (baseline). الفرق بين التوقّعين هو أثر تلك الميزة تحديداً على هذه
#  الحالة. طريقة تفسير قياسية (occlusion)، لا تحتاج مكتبات إضافية،
#  ونتيجتها بنفس وحدة توقّع النموذج (نقاط احتمال أو ريال).
# ═══════════════════════════════════════════════════════════════
FEATURE_LABELS = {
    "Income_lag1": "دخل الشهر الماضي", "Income_roll3": "متوسط آخر 3 أشهر",
    "Number_of_Projects": "عدد المشاريع", "Total_Expenses": "المصاريف",
    "Month": "الشهر", "Payment_Delay_Days": "تأخّر التحصيل السابق",
    "Project_Duration_Days": "مدة المشروع", "Estimated_Hours": "عدد الساعات",
    "Complexity": "درجة التعقيد", "Hourly_Rate": "سعر الساعة المعتاد",
    "Project_Value": "قيمة المشروع",
}

def feature_label(f):
    if f in FEATURE_LABELS:
        return FEATURE_LABELS[f]
    if f.startswith("Client_Type_"):
        return f"نوع العميل: {f[len('Client_Type_'):]}"
    if f.startswith("Specialty_"):
        return f"التخصّص: {f[len('Specialty_'):]}"
    return f

def explain_prediction(predict_fn, row, features, baseline_means, top_n=3):
    """يرجّع (التوقّع الفعلي، قائمة أهم top_n عوامل مؤثّرة مع إشارة أثرها)."""
    base = float(predict_fn(row[features])[0])
    contribs = []
    for f in features:
        modified = row.copy()
        modified[f] = baseline_means[f]
        alt = float(predict_fn(modified[features])[0])
        contribs.append((f, base - alt))
    contribs.sort(key=lambda x: abs(x[1]), reverse=True)
    return base, contribs[:top_n]

def render_explanation(contribs, up_phrase, down_phrase, value_fmt):
    shown = [c for c in contribs if abs(c[1]) > 1e-9]
    st.markdown("###### أهم العوامل المؤثّرة في هذا التوقّع")
    if not shown:
        st.caption("لا يوجد عامل مؤثّر بوضوح، توقّعك قريب من المتوسط العام لبقية الفريلانسرز.")
        return
    for f, c in shown:
        phrase = up_phrase if c > 0 else down_phrase
        st.markdown(f"- **{feature_label(f)}** {phrase} بمقدار **{value_fmt(abs(c))}**")
    st.caption("الطريقة: نقارن توقّعك الفعلي بتوقّع افتراضي لو كان هذا العامل وحده "
               "عند متوسط بيانات كل الفريلانسرز، والفرق هو أثره على توقّعك تحديداً.")

# ═══════════════════════════════════════════════════════════════
#  مطابقة التمويل الإسلامي، من درجة الجدارة إلى منتج تمويلي فعلي
#  المستويات وأسعار الربح ونِسب التغطية إرشادية لأغراض النموذج الأولي،
#  وتُبنى في المنتج الحقيقي على سياسة ائتمانية معتمدة من الجهة المموّلة.
# ═══════════════════════════════════════════════════════════════
FIN_TIERS = [
    # (أدنى درجة، اسم المنتج، الغرض، نسبة ربح دنيا، نسبة ربح عليا، أقصى مدة بالشهور، مضاعف السقف السنوي)
    (80, "تورّق ميسّر",        "تمويل عام أو تنمية مشروعك، بأفضل الشروط",      0.06, 0.08, 48, 0.9),
    (65, "إجارة تمويلية",      "تأجير منتهٍ بالتمليك لمعدّات أو سيارة عمل",     0.08, 0.11, 36, 0.6),
    (50, "مرابحة مصغّرة",      "تمويل مستلزمات مشروع صغير أو أدوات عمل",        0.11, 0.14, 24, 0.35),
    (35, "قرض حسن تأهيلي",    "تمويل صغير بلا هامش ربح لبناء سجلّك الائتماني", 0.00, 0.00, 12, 0.08),
]

def match_financing(score):
    for min_score, name, purpose, rmin, rmax, max_tenor, cap_mult in FIN_TIERS:
        if score >= min_score:
            return {"name": name, "purpose": purpose, "rmin": rmin, "rmax": rmax,
                    "max_tenor": max_tenor, "cap_mult": cap_mult, "min_score": min_score}
    return None

def estimate_financing(avg_income, score, tenor_months):
    """يقدّر القسط الشهري المحتمل والتمويل المقابل له لمدّة مختارة.
    نسبة الالتزام المسموحة تتحرّك 15%-35% من الدخل حسب الدرجة (مفهوم
    نسبة عبء الدين المعتمد في التمويل الشخصي بالسعودية)، والربح يُحتسب
    بطريقة القسط الثابت (Flat) على مدّة التمويل."""
    tier = match_financing(score)
    if tier is None:
        return None
    capacity_ratio = 0.15 + 0.20 * (score / 100)
    monthly_installment = avg_income * capacity_ratio
    tenor = min(tenor_months, tier["max_tenor"])
    annual_rate = (tier["rmin"] + tier["rmax"]) / 2
    total_payable = monthly_installment * tenor
    principal = total_payable / (1 + annual_rate * (tenor / 12))
    cap = avg_income * 12 * tier["cap_mult"]
    principal = min(principal, cap)
    return {"tier": tier, "tenor": tenor, "monthly_installment": monthly_installment,
            "annual_rate": annual_rate, "principal": round(principal)}

# ═══════════════════════════════════════════════════════════════
#  محاكي «ماذا لو»، أثر تغيير السعر/العملاء/الساعات على السنة القادمة
# ═══════════════════════════════════════════════════════════════
MONTHS_SPAN = 18          # مدى البيانات بالأشهر
PRICE_ELASTICITY = -0.8   # رفع السعر 10% يُفقد ~8% من المشاريع (تقدير محافظ)

def simulate_scenario(pj, price_pct=0, drop_client=None, hours_pct=0):
    """يقارن الوضع الحالي بالسيناريو الافتراضي على أساس سنوي."""
    if len(pj) == 0:
        return None

    def summarize(df):
        if len(df) == 0:
            return {"income":0,"hours":0,"projects":0,"delay":0,"default":0,"rate":0}
        inc = df["Project_Value"].sum() / MONTHS_SPAN * 12
        hrs = df["Estimated_Hours"].sum() / MONTHS_SPAN * 12
        return {"income":inc, "hours":hrs, "projects":len(df)/MONTHS_SPAN*12,
                "delay":df["Payment_Delay_Days"].mean(),
                "default":df["Defaulted"].mean(),
                "rate":inc/max(1,hrs)}

    base = summarize(pj)
    sim = pj.copy()

    # 1) رفض نوع عميل
    if drop_client:
        sim = sim[sim["Client_Type"] != drop_client]
    if len(sim) == 0:
        return {"base":base, "new":summarize(sim), "empty":True}

    # 2) تغيير السعر، مع مرونة الطلب (تفقد بعض المشاريع)
    p = price_pct / 100
    if p != 0:
        sim = sim.copy()
        sim["Project_Value"] = sim["Project_Value"] * (1 + p)
        keep = max(0.1, 1 + PRICE_ELASTICITY * p)
        n_keep = max(1, int(round(len(sim) * keep)))
        sim["_ph"] = sim["Project_Value"] / sim["Estimated_Hours"]
        sim = sim.nlargest(n_keep, "_ph")     # يُبقي الأعلى ربحية بالساعة

    # 3) تغيير ساعات العمل المتاحة
    h = hours_pct / 100
    if h != 0:
        cap = sim["Estimated_Hours"].sum() * (1 + h)
        sim = sim.sort_values("Project_Value", ascending=False)
        cum = sim["Estimated_Hours"].cumsum()
        sim = sim[cum <= cap] if (cum <= cap).any() else sim.head(1)

    return {"base":base, "new":summarize(sim), "empty":False}

# ═══════════════════════════════════════════════════════════════
#  أشجار الأهداف، تحويل الادخار إلى قصّة بصرية
# ═══════════════════════════════════════════════════════════════
TREE_STAGES = [
    (0.00, "بذرة",          "🌱", "زُرعت البذرة. كل رحلة تبدأ بخطوة."),
    (0.10, "نبتة صغيرة",    "🌿", "بدأت الجذور تمتدّ. استمر."),
    (0.30, "شجرة متوسّطة",  "🌳", "الشجرة تكبر. النصف في المتناول."),
    (0.60, "شجرة كبيرة",    "🌲", "قاربت الثمر. لا تتوقّف الآن."),
    (0.90, "شجرة مثمرة",    "🍎", "الشجرة أثمرت. تهانينا!"),
]

def tree_stage(progress):
    """يُرجع (الاسم، الرمز، الرسالة) حسب نسبة التقدّم."""
    stage = TREE_STAGES[0]
    for threshold, name, icon, msg in TREE_STAGES:
        if progress >= threshold:
            stage = (threshold, name, icon, msg)
    return stage[1], stage[2], stage[3]

def months_to_goal(target, saved, monthly_save):
    """كم شهراً حتى يثمر الهدف بمعدّل الادخار الحالي."""
    if monthly_save <= 0:
        return None
    remaining = max(0, target - saved)
    return int(np.ceil(remaining / monthly_save))

# ═══════════════════════════════════════════════════════════════
#  مقارنة الأقران، ترتيب مئوي داخل نفس التخصّص
# ═══════════════════════════════════════════════════════════════
@st.cache_data
def compute_peer_table(monthly, projects):
    """جدول لكل فريلانسر: متوسط دخل 12 شهر، استقرار الدخل، وربحية الساعة."""
    rows = []
    for fid_, g in monthly.sort_values(["Freelancer_ID","Year","Month"]).groupby("Freelancer_ID"):
        avg12 = g["Income"].tail(12).mean()
        inc6 = g["Income"].tail(6)
        stab = 100 - min(100, inc6.std()/max(1,avg12)*100) if len(inc6) > 1 else 100.0
        pj = projects[projects["Freelancer_ID"]==fid_]
        hourly = (pj["Project_Value"]/pj["Estimated_Hours"]).mean() if len(pj) else np.nan
        rows.append({"Freelancer_ID": fid_, "Specialty": g["Specialty"].iloc[0],
                     "avg_income_12": avg12, "stability": stab, "hourly_rate": hourly})
    return pd.DataFrame(rows)

def percentile_rank(series, value):
    s = series.dropna()
    if len(s) == 0 or pd.isna(value):
        return 50.0
    return float((s <= value).mean() * 100)

def render_percentile_card(label, value_txt, pctl, peer_label):
    color = PRIMARY if pctl >= 50 else (ACCENT if pctl >= 25 else DRY_RED)
    st.markdown(f"""<div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-val">{value_txt}</div>
      <div style="background:#e3ebe6;border-radius:8px;height:10px;margin-top:10px;overflow:hidden">
        <div style="background:{color};height:100%;width:{pctl:.0f}%"></div>
      </div>
      <div class="metric-label" style="margin-top:6px">أعلى من {pctl:.0f}% من {peer_label}</div>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  الفاتورة الإلكترونية المبسّطة، ترميز TLV القياسي لفوترة (ZATCA)
#  المرحلة الأولى + رمز QR يحوي الحقول الخمسة الإلزامية.
# ═══════════════════════════════════════════════════════════════
VAT_RATE = 0.15

def _tlv(tag, value):
    vb = str(value).encode("utf-8")
    return bytes([tag, len(vb)]) + vb

def zatca_tlv_payload(seller_name, vat_number, timestamp_iso, total_incl_vat, vat_amount):
    """يبني الحمولة القياسية (TLV) المعتمدة في فوترة (ZATCA) المرحلة الأولى، Base64.
    هذه هي الصيغة التي يحملها رمز QR فعلياً في نظام فوترة معتمد: بيانات مرمَّزة
    تُقرأ آلياً بواسطة أنظمة الجهة الضريبية، وليست نصاً يظهر عند المسح."""
    payload = (_tlv(1, seller_name) + _tlv(2, vat_number) + _tlv(3, timestamp_iso) +
               _tlv(4, f"{total_incl_vat:.2f}") + _tlv(5, f"{vat_amount:.2f}"))
    return base64.b64encode(payload).decode()

def make_qr_png_b64(content):
    """يحوّل أي نص إلى صورة QR بصيغة PNG مُرمَّزة Base64."""
    img = qrcode.make(content)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ═══════════════════════════════════════════════════════════════
#  التبويبات
# ═══════════════════════════════════════════════════════════════
(tab1, tab2, tab_islamic, tab3, tab4, tab5, tab6, tab7, tab8, tab9,
 tab_invoice, tab10) = st.tabs([
    "اللوحة الرئيسية", "مؤشر الجدارة", "التمويل الإسلامي", "تحذير الجفاف",
    "محفظة المشاريع", "حاسبة التسعير", "كاشف العميل الخطر", "محاكي ماذا لو",
    "أشجار الأهداف", "حاسبة الزكاة", "الفاتورة الإلكترونية", "أداء النماذج"
])

# ───────────────────────── تبويب 1 : اللوحة ─────────────────────
with tab1:
    last = user.iloc[-1]
    avg_income = user["Income"].tail(SALARY_WINDOW).mean()   # الراتب الاصطناعي
    total_income_12 = user["Income"].tail(12).sum()
    avg_12 = user["Income"].tail(12).mean()
    stability = 100 - min(100, user["Income"].tail(6).std()/max(1,avg_12)*100)

    st.markdown(f"#### مرحباً {uname}، التخصص: {specialty}")

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">آخر دخل شهري</div>'
                    f'<div class="metric-val">{last.Income:,.0f} {RIYAL}</div>'
                    f'<div class="metric-label">الشهر الأخير</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card gold"><div class="metric-label">متوسط دخل 12 شهر</div>'
                    f'<div class="metric-val">{avg_12:,.0f} {RIYAL}</div>'
                    f'<div class="metric-label">شهرياً</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">صندوق الطوارئ</div>'
                    f'<div class="metric-val">{last.Emergency_Fund:,.0f} {RIYAL}</div>'
                    f'<div class="metric-label">الرصيد الحالي</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card gold"><div class="metric-label">مؤشر استقرار الدخل</div>'
                    f'<div class="metric-val">{stability:.0f}%</div>'
                    f'<div class="metric-label">كلما زاد كان أفضل</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    cc1, cc2 = st.columns([1,2.4])
    with cc1:
        st.markdown(f"""
        <div class="salary-box">
          <div style="font-size:16px;opacity:.9">راتبك الاصطناعي الثابت</div>
          <div class="num">{avg_income:,.0f} {RIYAL_WHITE}</div>
          <div style="font-size:15px;opacity:.9">شهرياً · محسوب من آخر {SALARY_WINDOW} أشهر</div>
        </div>""", unsafe_allow_html=True)
        st.info("هذا هو المبلغ الثابت الذي يصرفه لك «صندوق التسوية» كل بداية شهر، "
                "والفائض يوزّع تلقائياً: 50% طوارئ · 30% مشاريع · 20% ادخار.")

    with cc2:
        user["label"] = user["Month"].map(MONTH_NAMES) + " " + user["Year"].astype(str).str[-2:]
        user["smoothed"] = user["Income"].rolling(SALARY_WINDOW, min_periods=1).mean()
        fig = go.Figure()
        fig.add_bar(x=user["label"], y=user["Income"], name="الدخل الفعلي",
                    marker_color="#bcd9c7")
        fig.add_scatter(x=user["label"], y=user["smoothed"], name="الراتب الاصطناعي",
                        mode="lines+markers", line=dict(color=PRIMARY,width=4))
        fig.update_layout(height=460, margin=dict(t=90,b=120,l=10,r=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.08,
                                      xanchor="right", x=1, font=dict(size=14)),
                          plot_bgcolor="white", font=dict(family=FONT_FAMILY_PLOTLY, size=13),
                          bargap=0.25,
                          xaxis=dict(tickangle=-45, automargin=True),
                          yaxis=dict(automargin=True, title="ريال"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### وثيقة الدخل الموثق (بديل شهادة الراتب للبنك)")
    d1,d2,d3 = st.columns(3)
    d1.markdown(f'<div class="metric-card"><div class="metric-label">متوسط الدخل (12 شهر)</div>'
                f'<div class="metric-val">{avg_12:,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)
    d2.markdown(f'<div class="metric-card"><div class="metric-label">إجمالي دخل السنة</div>'
                f'<div class="metric-val">{total_income_12:,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)
    d3.markdown(f'<div class="metric-card"><div class="metric-label">استقرار الدخل</div>'
                f'<div class="metric-val">{stability:.0f}%</div></div>', unsafe_allow_html=True)
    st.caption("الوثيقة الرسمية الكاملة القابلة للتحميل متوفّرة في تبويب «مؤشر الجدارة».")

    st.markdown("---")
    st.markdown(f"#### مقارنتك مع أقرانك في «{specialty}»")
    peer_table = compute_peer_table(monthly, projects)
    peers = peer_table[(peer_table["Specialty"]==specialty) & (peer_table["Freelancer_ID"]!=fid)]
    if len(peers) < 3:
        st.info("عدد الفريلانسرز في نفس تخصّصك قليل حالياً، المقارنة ستكون أدق مع مزيد من البيانات.")
    else:
        pj_user_bench = projects[projects["Freelancer_ID"]==fid]
        user_hourly = ((pj_user_bench["Project_Value"]/pj_user_bench["Estimated_Hours"]).mean()
                       if len(pj_user_bench) else np.nan)
        peer_lbl = f"زملائك في {specialty}"
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            render_percentile_card("متوسط الدخل الشهري", f"{avg_12:,.0f} {RIYAL_TXT}",
                                   percentile_rank(peers["avg_income_12"], avg_12), peer_lbl)
        with pc2:
            render_percentile_card("استقرار الدخل", f"{stability:.0f}%",
                                   percentile_rank(peers["stability"], stability), peer_lbl)
        with pc3:
            if pd.isna(user_hourly):
                st.markdown('<div class="metric-card"><div class="metric-label">ربحية الساعة</div>'
                            '<div class="metric-val">—</div>'
                            '<div class="metric-label">لا توجد مشاريع كافية</div></div>',
                            unsafe_allow_html=True)
            else:
                render_percentile_card("ربحية الساعة", f"{user_hourly:,.0f} {RIYAL_TXT}",
                                       percentile_rank(peers["hourly_rate"], user_hourly), peer_lbl)
        st.caption(f"المقارنة مبنية على {len(peers)} فريلانسر آخر في نفس التخصّص من بيانات التطبيق.")

# ───────────────────────── تبويب 2 : مؤشر الجدارة + الوثيقة ─────────────────────
with tab2:
    st.markdown("#### مؤشر الجدارة الائتمانية للفريلانسر")
    st.caption("درجة تُحسب من سلوكك المالي الفعلي: استقرار دخلك، صندوق طوارئك، تنوّع عملائك، وانتظام تحصيلك.")

    pj_all = projects[projects["Freelancer_ID"]==fid]
    score, parts, cover, delay = compute_credit_score(user, pj_all)
    g_label, g_msg, g_color = score_grade(score)

    cS, cD = st.columns([1,1.3])
    with cS:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=score,
            number={"suffix":" / 100", "font":{"size":38}},
            title={"text":"درجة الجدارة"},
            gauge={"axis":{"range":[0,100]},
                   "bar":{"color":g_color, "thickness":0.75},
                   "steps":[{"range":[0,35],"color":"#fbdcdf"},
                            {"range":[35,50],"color":"#fde8dc"},
                            {"range":[50,65],"color":"#faf1d6"},
                            {"range":[65,80],"color":"#dff1ee"},
                            {"range":[80,100],"color":"#d8f0e0"}]}))
        gauge.update_layout(height=320, margin=dict(t=60,b=20,l=30,r=30),
                            font=dict(family=FONT_FAMILY_PLOTLY))
        st.plotly_chart(gauge, use_container_width=True)
        st.markdown(f"""<div style="background:{g_color};color:#fff;padding:16px 20px;
        border-radius:16px;text-align:center;font-weight:700;font-size:17px">
        التصنيف: {g_label}<br><span style="font-weight:400;font-size:15px">{g_msg}</span></div>""",
        unsafe_allow_html=True)

    with cD:
        st.markdown("##### من أين جاءت الدرجة؟")
        names  = list(parts.keys())
        got    = [parts[k][0] for k in names]
        remain = [parts[k][1]-parts[k][0] for k in names]
        maxv   = [parts[k][1] for k in names]
        figb = go.Figure()
        figb.add_bar(x=names, y=got, name="النقاط المحقّقة",
                     marker_color=PRIMARY, text=[f"{v:.0f}" for v in got],
                     textposition="inside", textfont=dict(color="white", size=14))
        figb.add_bar(x=names, y=remain, name="النقاط المتبقّية",
                     marker_color="#e3ebe6",
                     text=[f"{parts[n][1]:.0f}" for n in names], textposition="outside")
        figb.update_layout(barmode="stack", height=400,
                           margin=dict(t=60,b=90,l=40,r=20), plot_bgcolor="white",
                           font=dict(family=FONT_FAMILY_PLOTLY, size=13),
                           legend=dict(orientation="h", yanchor="bottom", y=1.08, x=1, xanchor="right"),
                           yaxis=dict(title="النقاط", automargin=True),
                           xaxis=dict(automargin=True, tickangle=0))
        st.plotly_chart(figb, use_container_width=True)

    st.markdown("##### كيف ترفع درجتك؟")
    for t in improvement_tips(parts, cover, delay):
        st.markdown(f"- {t}")

    with st.expander("من أين جاءت أوزان المحاور؟"):
        st.markdown("الأوزان مُشتقّة من البيانات: درّبنا نموذجاً يتنبأ بالضائقة المالية، وقِسنا أهمية كل محور فيه.")
        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;text-align:center;margin:10px 0">
          <tr style="background:#f2f8f4">
            <th style="border:1px solid #d6e2da;padding:8px;text-align:center">المحور</th>
            <th style="border:1px solid #d6e2da;padding:8px;text-align:center">الوزن</th>
            <th style="border:1px solid #d6e2da;padding:8px;text-align:center">لماذا</th>
          </tr>
          <tr><td style="border:1px solid #d6e2da;padding:8px">صندوق الطوارئ</td>
              <td style="border:1px solid #d6e2da;padding:8px">{W_EMERGENCY}</td>
              <td style="border:1px solid #d6e2da;padding:8px">السيولة أقوى حماية من الضائقة</td></tr>
          <tr><td style="border:1px solid #d6e2da;padding:8px">استقرار الدخل</td>
              <td style="border:1px solid #d6e2da;padding:8px">{W_STABILITY}</td>
              <td style="border:1px solid #d6e2da;padding:8px">التقلّب هو سبب رفض البنوك</td></tr>
          <tr><td style="border:1px solid #d6e2da;padding:8px">تنوّع العملاء</td>
              <td style="border:1px solid #d6e2da;padding:8px">{W_DIVERSITY}</td>
              <td style="border:1px solid #d6e2da;padding:8px">مقاس بمؤشر HHI الاقتصادي</td></tr>
          <tr><td style="border:1px solid #d6e2da;padding:8px">انتظام التحصيل</td>
              <td style="border:1px solid #d6e2da;padding:8px">{W_COLLECTION}</td>
              <td style="border:1px solid #d6e2da;padding:8px">التأخّر يخلق فجوات نقدية</td></tr>
        </table>
        <p style="text-align:center;color:#6b7c72;font-size:14px">
        نموذج الضائقة حقّق AUC = 0.63 (فوق العشوائي البالغ 0.50).
        في المنتج الحقيقي تُعايَر هذه الأوزان ببيانات تعثّر فعلية من البنك.</p>
        """, unsafe_allow_html=True)

    # ─── وثيقة الدخل الموثق ───
    st.markdown("---")
    st.markdown("#### وثيقة الدخل الموثق")
    st.caption("بديل شهادة الراتب. اضغط زر «تحميل PDF» داخل المعاينة ليُحفظ الملف مباشرة بصيغة PDF.")

    inc12 = user["Income"].tail(12)
    if _RIYAL_IMG:
        _riyal_doc = f'<img src="data:image/jpeg;base64,{_RIYAL_IMG}" style="height:0.8em;vertical-align:-0.03em;margin:0 2px">'
    else:
        _riyal_doc = "ريال"
    doc_inner = f"""<div class="head">
  <img src="data:image/jpeg;base64,{LOGO_B64}" style="height:70px;margin-bottom:10px">
  <h1>وثيقة الدخل الموثق</h1>
  <p>مستقل · Mustaqil، الرفيق المالي للفريلانسر السعودي</p>
</div>
<table>
  <tr><th>الاسم</th><td>{uname}</td></tr>
  <tr><th>رقم الحساب</th><td>#{fid}</td></tr>
  <tr><th>التخصّص</th><td>{specialty}</td></tr>
  <tr><th>متوسّط الدخل الشهري (12 شهراً)</th><td>{inc12.mean():,.0f} {_riyal_doc}</td></tr>
  <tr><th>إجمالي الدخل السنوي</th><td>{inc12.sum():,.0f} {_riyal_doc}</td></tr>
  <tr><th>أعلى دخل شهري</th><td>{inc12.max():,.0f} {_riyal_doc}</td></tr>
  <tr><th>أدنى دخل شهري</th><td>{inc12.min():,.0f} {_riyal_doc}</td></tr>
  <tr><th>الراتب الاصطناعي المقترح</th><td>{avg_income:,.0f} {_riyal_doc} / شهرياً</td></tr>
  <tr><th>مؤشّر استقرار الدخل</th><td>{stability:.0f}%</td></tr>
  <tr><th>عدد المشاريع المنفّذة</th><td>{len(pj_all)} مشروعاً</td></tr>
  <tr><th>تغطية صندوق الطوارئ</th><td>{cover:.1f} شهر</td></tr>
</table>
<div class="score">
  درجة الجدارة الائتمانية<br><b>{score} / 100</b><br>{g_label}، {g_msg}
</div>
<div class="foot">
  صدرت هذه الوثيقة آلياً من تطبيق «مستقل» بناءً على السجلّ المالي الفعلي للمستخدم.<br>
  نموذج أولي، هاكاثون أمد · مصرف الإنماء × أكاديمية طويق.
</div>"""

    doc_component = f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<style>
 {FONT_FACE_CSS}
 body {{ font-family:{FONT_FAMILY}; direction:rtl; margin:0; color:#0E2A1F;
        background:#eef2f0; padding:16px; }}
 #doc {{ background:#fff; padding:40px; max-width:720px; margin:0 auto; }}
 .head {{ border-bottom:4px solid #00833E; padding-bottom:16px; margin-bottom:20px; text-align:center; }}
 .head h1 {{ margin:6px 0 0; color:#00833E; font-size:28px; }}
 .head p {{ margin:4px 0 0; color:#6b7c72; }}
 table {{ width:100%; border-collapse:collapse; margin-top:14px; }}
 th,td {{ border:1px solid #d6e2da; padding:11px 14px; text-align:right; }}
 th {{ background:#f2f8f4; width:48%; font-weight:700; }}
 .score {{ background:#00833E; color:#fff; padding:18px; border-radius:12px;
          text-align:center; margin-top:22px; }}
 .score b {{ font-size:28px; }}
 .foot {{ margin-top:28px; font-size:13px; color:#6b7c72; border-top:1px solid #d6e2da;
         padding-top:14px; text-align:center; }}
 #btn {{ display:block; margin:0 auto 16px; background:#00833E; color:#fff; border:none;
        padding:12px 30px; border-radius:12px; font-family:{FONT_FAMILY}; font-weight:700;
        font-size:16px; cursor:pointer; }}
</style></head><body>
<button id="btn" onclick="dl()">تحميل PDF</button>
<div id="doc">{doc_inner}</div>
<script>
function dl() {{
  var el = document.getElementById('doc');
  html2pdf().set({{
    margin: 8, filename: 'وثيقة_الدخل_{uname}.pdf',
    image: {{type:'jpeg', quality:0.98}},
    html2canvas: {{scale:2, useCORS:true}},
    jsPDF: {{unit:'mm', format:'a4', orientation:'portrait'}}
  }}).from(el).save();
}}
</script>
</body></html>"""

    components.html(doc_component, height=760, scrolling=True)

# ───────────────────────── تبويب : التمويل الإسلامي ─────────────────────
with tab_islamic:
    st.markdown("#### التمويل الإسلامي المناسب لك")
    st.caption("نحوّل درجة جدارتك إلى منتج تمويلي فعلي متوافق مع الشريعة، "
               "بدل ترك الدرجة مجرّد رقم.")

    fin_tier = match_financing(score)
    tenor_choice = st.select_slider("مدّة التمويل المرغوبة (بالشهور)",
                                    options=[12, 24, 36, 48], value=24)
    est = estimate_financing(avg_12, score, tenor_choice)

    if est is None:
        st.markdown(f"""<div class="alert-dry">
        <b>غير مؤهّل لمنتج تمويلي حالياً</b><br><br>
        درجتك الحالية {score}/100 أقل من الحدّ الأدنى لأي مستوى تمويلي.<br>
        ابدأ ببناء صندوق الطوارئ واستقرار دخلك، راجع تبويب «مؤشر الجدارة» للتفاصيل.
        </div>""", unsafe_allow_html=True)
    else:
        tier = est["tier"]
        fc1, fc2 = st.columns([1.3, 1])
        with fc1:
            st.markdown(f"""<div class="salary-box">
              <div style="font-size:16px;opacity:.9">المنتج الأنسب لك الآن</div>
              <div class="num" style="font-size:36px">{tier['name']}</div>
              <div style="font-size:15px;opacity:.9">{tier['purpose']}</div>
            </div>""", unsafe_allow_html=True)
        with fc2:
            st.markdown(f"""<div class="metric-card gold">
              <div class="metric-label">التمويل التقديري الأقصى</div>
              <div class="metric-val">{est['principal']:,.0f} {RIYAL}</div>
              <div class="metric-label">على {est['tenor']} شهراً</div>
            </div>""", unsafe_allow_html=True)

        gc1, gc2, gc3 = st.columns(3)
        gc1.markdown(f'<div class="metric-card"><div class="metric-label">القسط الشهري التقديري</div>'
                     f'<div class="metric-val">{est["monthly_installment"]:,.0f} {RIYAL}</div></div>',
                     unsafe_allow_html=True)
        gc2.markdown(f'<div class="metric-card"><div class="metric-label">نسبة الربح الإرشادية</div>'
                     f'<div class="metric-val">{tier["rmin"]*100:.0f}–{tier["rmax"]*100:.0f}%</div>'
                     f'<div class="metric-label">سنوياً، وفق التصنيف</div></div>', unsafe_allow_html=True)
        gc3.markdown(f'<div class="metric-card"><div class="metric-label">أقصى مدّة لهذا المستوى</div>'
                     f'<div class="metric-val">{tier["max_tenor"]} شهراً</div></div>',
                     unsafe_allow_html=True)

        st.markdown("##### مستويات التمويل الأربعة")
        rows_html = ""
        for t_min, name, purpose, rmin, rmax, max_tenor, cap_mult in FIN_TIERS:
            eligible = score >= t_min
            mark = "مؤهّل" if eligible else "يحتاج درجة " + str(t_min) + "+"
            row_bg = "#eaf6ee" if eligible else "#f7f7f7"
            rows_html += f"""<tr style="background:{row_bg}">
              <td style="border:1px solid #d6e2da;padding:8px">{name}</td>
              <td style="border:1px solid #d6e2da;padding:8px">{purpose}</td>
              <td style="border:1px solid #d6e2da;padding:8px">{rmin*100:.0f}–{rmax*100:.0f}%</td>
              <td style="border:1px solid #d6e2da;padding:8px">{max_tenor} شهراً</td>
              <td style="border:1px solid #d6e2da;padding:8px;font-weight:700">{mark}</td>
            </tr>"""
        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;text-align:center">
          <tr style="background:#f2f8f4">
            <th style="border:1px solid #d6e2da;padding:8px">المنتج</th>
            <th style="border:1px solid #d6e2da;padding:8px">الغرض</th>
            <th style="border:1px solid #d6e2da;padding:8px">نسبة الربح</th>
            <th style="border:1px solid #d6e2da;padding:8px">أقصى مدّة</th>
            <th style="border:1px solid #d6e2da;padding:8px">أهليتك</th>
          </tr>
          {rows_html}
        </table>""", unsafe_allow_html=True)

        if tier["min_score"] < 80:
            next_tier = next((t for t in FIN_TIERS if t[0] > tier["min_score"]), None)
            if next_tier is None:
                gap_needed = 80 - score
                st.info(f"ارفع درجتك {gap_needed:.0f} نقطة إضافية لتصل لأفضل مستوى «تورّق ميسّر».")

    with st.expander("كيف حسبنا المبلغ والقسط؟"):
        st.markdown("""
        - **نسبة الالتزام المسموحة** تتحرّك بين 15% و35% من متوسّط دخلك الشهري (12 شهراً)
          حسب درجة جدارتك، أقرب لمفهوم «نسبة عبء الدين» (Debt Burden Ratio) المستخدم
          في التمويل الشخصي بالسعودية.
        - **القسط الشهري التقديري** = دخلك × نسبة الالتزام المسموحة.
        - **مبلغ التمويل** يُحسب عكسياً من مجموع الأقساط على مدّة التمويل، بعد خصم هامش
          الربح الإرشادي لكل مستوى (طريقة القسط الثابت).
        - سقف أعلى إضافي لكل مستوى يمنع أن يتجاوز التمويل مضاعفاً معقولاً من دخلك السنوي.
        """)

    st.warning("هذا نموذج أوّلي لأغراض الهاكاثون. الأسماء والنِسب والمبالغ إرشادية "
               "لتوضيح الفكرة، وليست عرض تمويل فعلياً من أي بنك. الموافقة النهائية "
               "تتطلّب تقييماً ائتمانياً رسمياً من الجهة المموّلة.")

# ───────────────────────── تبويب 2 : الجفاف ─────────────────────
with tab3:
    st.markdown("#### نظام التنبؤ بشهر الجفاف")
    st.caption("النموذج يحلل نمطك التاريخي ويتوقع إن كان الشهر القادم شهر جفاف (دخل منخفض) قبل وقوعه.")

    u = user.copy()
    u["Income_lag1"]  = u["Income"].shift(1)
    u["Income_roll3"] = u["Income"].rolling(3,min_periods=1).mean()
    nextmonth = (int(last.Month)%12)+1
    row = pd.DataFrame([{
        "Income_lag1": last.Income,
        "Income_roll3": u["Income"].tail(3).mean(),
        "Number_of_Projects": last.Number_of_Projects,
        "Total_Expenses": last.Total_Expenses,
        "Month": nextmonth,
        "Payment_Delay_Days": last.Payment_Delay_Days,
    }])
    proba = clf.predict_proba(row[F1])[0][1]
    _sin = np.sin(2*np.pi*nextmonth/12); _cos = np.cos(2*np.pi*nextmonth/12)
    pred_income = reg_income.predict(pd.DataFrame([{
        "Income": last.Income,
        "Income_lag1": u["Income"].iloc[-2] if len(u)>1 else last.Income,
        "Income_roll3": u["Income"].tail(3).mean(),
        "roll6": u["Income"].tail(6).mean(),
        "fl_mean": u["Income"].mean(),
        "Number_of_Projects": last.Number_of_Projects,
        "next_month": nextmonth, "sin_m": _sin, "cos_m": _cos }])[F2])[0]

    cL, cR = st.columns([1,1])
    with cL:
        if proba >= 0.5:
            st.markdown(f"""<div class="alert-dry">
            <b>تحذير: {MONTH_NAMES[nextmonth]} قد يكون شهر جفاف</b><br><br>
            احتمال انخفاض الدخل: <b>{proba*100:.0f}%</b><br>
            الدخل المتوقع: <b>{pred_income:,.0f} {RIYAL_WHITE}</b><br><br>
            ننصح بخفض راتبك الاصطناعي 20% هذا الشهر، وتفعيل صندوق الطوارئ.<br>
            الآن وقت مناسب لتجديد العقود أو البحث عن عميل جديد.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="alert-safe">
            <b>{MONTH_NAMES[nextmonth]} يبدو شهراً آمناً</b><br><br>
            احتمال الجفاف منخفض: <b>{proba*100:.0f}%</b><br>
            الدخل المتوقع: <b>{pred_income:,.0f} {RIYAL_WHITE}</b><br><br>
            استمر على خطتك، وهذا وقت جيد لتعزيز صندوق الطوارئ.
            </div>""", unsafe_allow_html=True)
    with cR:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=proba*100,
            number={"suffix":"%","font":{"size":40}},
            title={"text":"احتمال شهر الجفاف"},
            gauge={"axis":{"range":[0,100]},
                   "bar":{"color":DRY_RED if proba>=0.5 else PRIMARY},
                   "steps":[{"range":[0,50],"color":"#d8f0e0"},
                            {"range":[50,100],"color":"#fbdcdf"}]}))
        gauge.update_layout(height=300, margin=dict(t=60,b=20,l=30,r=30),
                            font=dict(family=FONT_FAMILY_PLOTLY))
        st.plotly_chart(gauge, use_container_width=True)

    _dry_predict = lambda X: clf.predict_proba(X)[:, 1]
    _, _dry_contribs = explain_prediction(_dry_predict, row, F1, BASELINES["F1"])
    render_explanation(_dry_contribs, "يرفع احتمال الجفاف", "يخفّض احتمال الجفاف",
                       lambda v: f"{v*100:.1f} نقطة")

    st.markdown("##### أشهر الجفاف في سجلك")
    u["label"] = u["Month"].map(MONTH_NAMES)+" "+u["Year"].astype(str).str[-2:]
    colors = [DRY_RED if x=="Yes" else "#bcd9c7" for x in u["Dry_Month_Label"]]
    figd = go.Figure(go.Bar(x=u["label"], y=u["Income"], marker_color=colors))
    figd.update_layout(height=400, margin=dict(t=70,b=110,l=10,r=10), plot_bgcolor="white",
                       font=dict(family=FONT_FAMILY_PLOTLY),
                       xaxis=dict(tickangle=-45, automargin=True),
                       yaxis=dict(automargin=True, title="ريال"),
                       title="أحمر = شهر جفاف   |   أخضر = شهر عادي")
    st.plotly_chart(figd, use_container_width=True)

# ───────────────────────── تبويب 3 : المشاريع ─────────────────────
with tab4:
    st.markdown("#### محفظة المشاريع")
    pj = projects[projects["Freelancer_ID"]==fid].copy()
    if len(pj)==0:
        st.warning("لا توجد مشاريع مسجلة لهذا الحساب.")
    else:
        m1,m2,m3,m4 = st.columns(4)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">عدد المشاريع</div>'
                    f'<div class="metric-val">{len(pj)}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">إجمالي قيمة المشاريع</div>'
                    f'<div class="metric-val">{pj["Project_Value"].sum():,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="metric-label">متوسط قيمة المشاريع</div>'
                    f'<div class="metric-val">{pj["Project_Value"].mean():,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">أعلى مشروع</div>'
                    f'<div class="metric-val">{pj["Project_Value"].max():,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        cA, cB = st.columns(2)
        with cA:
            by_client = pj.groupby("Client_Type")["Project_Value"].sum().reset_index()
            greens = ["#00833E", "#2E9E5B", "#57B97E", "#0E6B39"]
            figp = px.pie(by_client, names="Client_Type", values="Project_Value",
                          title="توزيع الدخل حسب نوع العميل",
                          color_discrete_sequence=greens)
            figp.update_traces(textposition="inside", textinfo="percent",
                               insidetextfont=dict(color="white", size=15, family=FONT_FAMILY_PLOTLY),
                               marker=dict(line=dict(color="white", width=2)))
            figp.update_layout(font=dict(family=FONT_FAMILY_PLOTLY), margin=dict(t=60,b=20,l=10,r=10),
                               legend=dict(orientation="h", y=-0.1),
                               uniformtext=dict(minsize=12, mode="hide"))
            st.plotly_chart(figp, use_container_width=True)
        with cB:
            pj["ربحية_بالساعة"] = pj["Project_Value"]/pj["Estimated_Hours"]
            top = pj.sort_values("ربحية_بالساعة",ascending=False).head(10)
            figh = px.bar(top, x="Project_ID", y="ربحية_بالساعة",
                          title="أعلى 10 مشاريع ربحية بالساعة",
                          labels={"Project_ID":"رقم المشروع","ربحية_بالساعة":"ريال/ساعة"},
                          color="ربحية_بالساعة", color_continuous_scale="Greens")
            figh.update_layout(font=dict(family=FONT_FAMILY_PLOTLY), margin=dict(t=60,b=40,l=10,r=10),
                               xaxis=dict(type="category"))
            st.plotly_chart(figh, use_container_width=True)

        st.markdown("##### تفاصيل المشاريع")
        show = pj[["Project_ID","Client_Type","Project_Duration_Days",
                   "Estimated_Hours","Project_Value"]].copy()
        show.columns = ["رقم المشروع","نوع العميل","المدة (يوم)","الساعات","القيمة (ريال)"]
        st.dataframe(show, use_container_width=True, hide_index=True)

# ───────────────────────── تبويب 4 : التسعير ─────────────────────
with tab5:
    st.markdown("#### حاسبة التسعير الذكية")
    st.caption(f"تخصّصك: **{specialty}**. أدخل تفاصيل المشروع والنموذج يقترح السعر العادل بناءً على بيانات السوق.")

    in_spec = specialty     # يؤخذ تلقائياً من حساب الفريلانسر

    c1,c2 = st.columns(2)
    with c1:
        in_client = st.selectbox("نوع العميل", sorted(projects["Client_Type"].unique()))
        in_rate = st.number_input(f"سعر ساعتك الحالي ({RIYAL_TXT})", 20, 500,
                                   int(projects[projects["Specialty"]==in_spec]["Hourly_Rate"].median()))
    with c2:
        in_duration = st.number_input("مدة المشروع (أيام)", 1, 120, 14)
        in_hours = st.number_input("ساعات العمل المقدّرة", min_value=1, max_value=400, value=60, step=1)
        in_complexity_raw = st.number_input("درجة تعقيد المشروع", min_value=0.0, max_value=1.0,
                                            value=0.5, step=0.5)
        st.caption("0 = بسيط · 0.5 = متوسط · 1 = معقّد جداً")

    # نحوّل مقياس المستخدم (0..1) إلى مقياس النموذج (0.7..1.5)
    in_complexity = 0.7 + in_complexity_raw * 0.8

    if st.button("احسب السعر المقترح"):
        base = pd.DataFrame([{
            "Project_Duration_Days": in_duration, "Estimated_Hours": float(in_hours),
            "Complexity": in_complexity, "Hourly_Rate": in_rate }])
        for c in projects["Specialty"].unique():
            base[f"Specialty_{c}"] = 1 if c==in_spec else 0
        for c in projects["Client_Type"].unique():
            base[f"Client_Type_{c}"] = 1 if c==in_client else 0
        for col in F3:
            if col not in base: base[col]=0
        price = reg_price.predict(base[F3])[0]

        st.markdown(f"""
        <div class="salary-box" style="margin-top:14px">
          <div style="font-size:16px;opacity:.9">السعر المقترح لهذا المشروع</div>
          <div class="num">{price:,.0f} {RIYAL_WHITE}</div>
          <div style="font-size:15px;opacity:.9">نطاق عادل: {price*0.85:,.0f} – {price*1.15:,.0f} {RIYAL_TXT}</div>
        </div>""", unsafe_allow_html=True)
        st.success(f"ربحية ساعتك في هذا المشروع = {price/in_hours:,.0f} {RIYAL_TXT} "
                   f"(السعر المقترح {price:,.0f} ÷ {in_hours} ساعة).")
        st.caption(f"لاحظ الفرق: «سعر ساعتك الحالي» ({in_rate} {RIYAL_TXT}) هو ما تطلبه أنت عادةً. "
                   f"أمّا «ربحية الساعة» فهي ما ستكسبه فعلياً في هذا المشروع تحديداً بعد أن يوازن "
                   f"النموذج مدّته وتعقيده ونوع عميله، وقد تكون أعلى أو أقل من سعرك المعتاد.")

        _price_predict = lambda X: reg_price.predict(X)
        _, _price_contribs = explain_prediction(_price_predict, base, F3, BASELINES["F3"])
        render_explanation(_price_contribs, "يرفع السعر المقترح", "يخفّض السعر المقترح",
                           lambda v: f"{v:,.0f} {RIYAL_TXT}")

# ───────────────────────── تبويب 6 : كاشف العميل الخطر ─────────────────────
with tab6:
    st.markdown("#### كاشف العميل الخطر")
    st.caption(f"قبل أن تقبل مشروعاً، اعرف سلوك سداد عميلك. تخصّصك: **{specialty}** "
               "(يؤخذ تلقائياً). النموذج تعلّم من سجل السداد الفعلي لأنواع العملاء.")

    rc_spec = specialty

    r1, r2 = st.columns(2)
    with r1:
        rc_client = st.selectbox("نوع العميل", sorted(projects["Client_Type"].unique()),
                                 key="rc_client")
    with r2:
        rc_value = st.number_input(f"قيمة المشروع ({RIYAL_TXT})", min_value=1,
                                   max_value=1_000_000, value=15000, step=1)
    rc_days = st.number_input("مدة المشروع (أيام)", 1, 120, 14, key="rc_days")

    rc_hours = rc_days * 3.5
    row4 = pd.DataFrame([{ "Project_Value": rc_value, "Project_Duration_Days": rc_days,
                           "Estimated_Hours": rc_hours, "Complexity": 1.0 }])
    for c in projects["Client_Type"].unique():
        row4[f"Client_Type_{c}"] = 1 if c==rc_client else 0
    for c in projects["Specialty"].unique():
        row4[f"Specialty_{c}"] = 1 if c==rc_spec else 0
    for col in F4:
        if col not in row4: row4[col] = 0

    risk = clf_late.predict_proba(row4[F4])[0][1]

    hist = projects[projects["Client_Type"]==rc_client]
    avg_delay = hist["Payment_Delay_Days"].mean()
    default_rate = hist["Defaulted"].mean()

    k1, k2 = st.columns([1,1])
    with k1:
        gz = go.Figure(go.Indicator(
            mode="gauge+number", value=risk*100,
            number={"suffix":"%","font":{"size":38}},
            title={"text":"احتمال تأخّر السداد"},
            gauge={"axis":{"range":[0,100]},
                   "bar":{"color":ACCENT if risk>=0.5 else PRIMARY},
                   "steps":[{"range":[0,50],"color":"#d8f0e0"},
                            {"range":[50,100],"color":"#faf1d6"}]}))
        gz.update_layout(height=300, margin=dict(t=60,b=20,l=30,r=30), font=dict(family=FONT_FAMILY_PLOTLY))
        st.plotly_chart(gz, use_container_width=True)

    with k2:
        if default_rate >= 0.08:
            advice = ("خطر تعثّر مرتفع نسبياً. اطلب دفعة مقدّمة لا تقلّ عن <b>40%</b> "
                      "وربط الدفعات بالتسليم.")
            box = "alert-dry"
        elif risk >= 0.6:
            advice = ("قد يدفع متأخّراً لكن نادراً يتعثّر. اطلب دفعة مقدّمة <b>25-30%</b> "
                      "واحسب التأخير في تخطيطك النقدي.")
            box = "alert-safe"
        else:
            advice = ("سلوك سداد جيّد. دفعة مقدّمة <b>15-20%</b> كافية.")
            box = "alert-safe"

        st.markdown(f"""<div class="{box}">
        <b>عملاء «{rc_client}»</b><br><br>
        احتمال أن يدفع <b>متأخّراً</b> (بعد 30 يوماً): <b>{risk*100:.0f}%</b><br>
        متوسّط مدّة التأخير: <b>{avg_delay:.0f} يوماً</b><br>
        احتمال ألّا يدفع <b>إطلاقاً</b> (تعثّر كامل): <b>{default_rate*100:.1f}%</b><br><br>
        {advice}
        </div>""", unsafe_allow_html=True)

    _risk_predict = lambda X: clf_late.predict_proba(X)[:, 1]
    _, _risk_contribs = explain_prediction(_risk_predict, row4, F4, BASELINES["F4"])
    render_explanation(_risk_contribs, "يرفع احتمال التأخّر", "يخفّض احتمال التأخّر",
                       lambda v: f"{v*100:.1f} نقطة")

    st.info("**فرّق بين أمرين:** «التأخّر» يعني أنه سيدفع لكن متأخّراً (مشكلة سيولة مؤقّتة). "
            "«التعثّر الكامل» يعني احتمال ألّا يدفع أبداً (خسارة نهائية). "
            "قد يكون عميل عالي التأخّر لكن منخفض التعثّر، أي يدفع دائماً، وإن تأخّر.")

    st.markdown("##### مقارنة أنواع العملاء")
    beh = projects.groupby("Client_Type").agg(
        متوسط_التأخير=("Payment_Delay_Days","mean"),
        نسبة_التعثر=("Defaulted","mean")).reset_index()
    beh["نسبة_التعثر"] = beh["نسبة_التعثر"]*100

    figc = go.Figure()
    figc.add_bar(x=beh["Client_Type"], y=beh["متوسط_التأخير"],
                 name="متوسّط التأخير (يوم)", marker_color=PRIMARY,
                 text=beh["متوسط_التأخير"].round(0), textposition="outside")
    figc.add_scatter(x=beh["Client_Type"], y=beh["نسبة_التعثر"],
                     name="نسبة التعثّر الكامل (%)", mode="lines+markers",
                     line=dict(color=DRY_RED,width=3), yaxis="y2")
    figc.update_layout(height=440, margin=dict(t=90,b=80,l=70,r=70), plot_bgcolor="white",
                       font=dict(family=FONT_FAMILY_PLOTLY, size=13),
                       legend=dict(orientation="h", yanchor="bottom", y=1.12, x=1, xanchor="right"),
                       yaxis=dict(title=dict(text="أيام التأخير", standoff=15),
                                  automargin=True, side="right"),
                       yaxis2=dict(title=dict(text="% تعثّر", standoff=15),
                                   overlaying="y", side="left", automargin=True, range=[0,15]),
                       xaxis=dict(automargin=True, tickangle=0))
    st.plotly_chart(figc, use_container_width=True)


# ───────────────────────── تبويب 7 : محاكي ماذا لو ─────────────────────
with tab7:
    st.markdown("#### محاكي «ماذا لو؟»")
    st.caption("جرّب قرارات مختلفة قبل أن تتّخذها. المحاكي يعيد حساب سنتك القادمة "
               "بناءً على مشاريعك الفعلية.")

    pj_sim = projects[projects["Freelancer_ID"]==fid]

    if len(pj_sim) == 0:
        st.warning("لا توجد مشاريع كافية لهذا الحساب.")
    else:
        s1, s2, s3 = st.columns(3)
        with s1:
            sim_price = st.number_input("كم ترفع أو تخفض أسعارك؟ (%)",
                                        min_value=-30, max_value=60, value=0, step=5)
            st.caption("موجب يرفع، سالب يخفّض. مثال: +20 ترفع أسعارك 20%.")
        with s2:
            client_opts = ["لا أرفض أحداً"] + sorted(pj_sim["Client_Type"].unique().tolist())
            sim_drop = st.selectbox("ارفض نوع عميل", client_opts)
            sim_drop = None if sim_drop=="لا أرفض أحداً" else sim_drop
        with s3:
            sim_hours = st.number_input("كم تزيد أو تقلّل ساعات عملك؟ (%)",
                                        min_value=-50, max_value=30, value=0, step=5)
            st.caption("مثال: -20 تعمل ساعات أقل، فتقبل مشاريع أقل.")

        res = simulate_scenario(pj_sim, sim_price, sim_drop, sim_hours)

        if res["empty"]:
            st.error(f"لو رفضت «{sim_drop}» لما بقي لك أي مشروع. جرّب خياراً آخر.")
        else:
            b, n = res["base"], res["new"]

            def delta(new, old):
                if old == 0: return 0
                return (new-old)/abs(old)*100

            d_inc  = delta(n["income"], b["income"])
            d_hrs  = delta(n["hours"],  b["hours"])
            d_rate = delta(n["rate"],   b["rate"])

            st.markdown("<br>", unsafe_allow_html=True)
            e1,e2,e3,e4 = st.columns(4)
            for col, label, bv, nv, dv, unit in [
                (e1, "الدخل السنوي",  b["income"], n["income"], d_inc,  "ريال"),
                (e2, "ساعات العمل",   b["hours"],  n["hours"],  d_hrs,  "ساعة"),
                (e3, "ربح الساعة",    b["rate"],   n["rate"],   d_rate, "ريال"),
                (e4, "عدد المشاريع",  b["projects"],n["projects"],
                     delta(n["projects"],b["projects"]), "مشروع")]:
                sign  = "+" if dv >= 0 else ""
                color = PRIMARY if dv >= 0 else DRY_RED
                col.markdown(f'''<div class="metric-card">
                  <div class="metric-label">{label}</div>
                  <div class="metric-val">{nv:,.0f}</div>
                  <div class="metric-label">{unit} · من {bv:,.0f}</div>
                  <div style="color:{color};font-weight:700;font-size:17px;margin-top:6px">
                    {sign}{dv:.1f}%</div>
                </div>''', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            cc1, cc2 = st.columns([1.75,1])
            with cc1:
                cats = ["الدخل السنوي","ساعات العمل","ربح الساعة","عدد المشاريع"]
                changes = [d_inc, d_hrs, d_rate, delta(n["projects"],b["projects"])]
                bar_colors = [PRIMARY if v>=0 else DRY_RED for v in changes]
                # حشوة سخية حول أعلى قيمة مطلقة حتى لا تُقصّ أرقام النِّسب عند حافة
                # الرسم، مع cliponaxis=False كضمان إضافي لعدم اقتصاصها.
                max_abs = max(5.0, max(abs(v) for v in changes))
                pad = max_abs * 0.45 + 8
                figs = go.Figure(go.Bar(
                    x=changes, y=cats, orientation="h",
                    marker_color=bar_colors, marker_line_width=0,
                    text=[f"{'+' if v>=0 else ''}{v:.0f}%" for v in changes],
                    textposition="outside", cliponaxis=False,
                    textfont=dict(size=16, family=FONT_FAMILY_PLOTLY, color=DARK),
                    width=0.55))
                figs.update_layout(height=400, margin=dict(t=70,b=55,l=110,r=40),
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   font=dict(family=FONT_FAMILY_PLOTLY, size=14),
                                   bargap=0.35, showlegend=False,
                                   title=dict(text="كم يتغيّر كل شيء مقارنةً بوضعك الحالي؟",
                                              x=0.5, xanchor="center", font=dict(size=16)),
                                   xaxis=dict(title="% التغيّر", range=[-max_abs-pad, max_abs+pad],
                                              zeroline=True, zerolinecolor=DARK, zerolinewidth=2,
                                              showgrid=True, gridcolor="#eef2f0", automargin=True),
                                   yaxis=dict(automargin=True, autorange="reversed",
                                              tickfont=dict(size=14, family=FONT_FAMILY_PLOTLY),
                                              ticklabelposition="outside"))
                st.plotly_chart(figs, use_container_width=True)

            with cc2:
                # قراءة ذكية للنتيجة
                lines = []
                if d_rate > 5:
                    lines.append(f"<b>ربح ساعتك يرتفع {d_rate:.0f}%</b>")
                if d_inc < -5 and d_rate > 5:
                    lines.append(f"دخلك ينخفض {abs(d_inc):.0f}% لكنك تعمل ساعات أقل.")
                if d_inc > 5 and d_hrs < 0:
                    lines.append("<b>أفضل سيناريو:</b> دخل أعلى بساعات أقل.")
                if sim_drop:
                    dd = (n["default"]-b["default"])*100
                    ddl = n["delay"]-b["delay"]
                    lines.append(f"رفض «{sim_drop}» يغيّر نسبة التعثّر بمقدار {dd:+.1f}% "
                                 f"ومتوسّط التأخير {ddl:+.0f} يوماً.")
                if not lines:
                    lines.append("غيّر القيم لترى أثر قراراتك.")

                st.markdown(f"""<div class="alert-safe" style="line-height:1.9">
                <b>قراءة النتيجة</b><br><br>{"<br><br>".join(lines)}
                </div>""", unsafe_allow_html=True)

# ───────────────────────── تبويب 8 : أشجار الأهداف ─────────────────────
with tab8:
    st.markdown("#### أشجار الأهداف")
    st.caption("حوّل ادخارك إلى غابة: أنشئ أهدافك بنفسك، وشاهد كل شجرة تنمو مع ادخارك حتى تُثمر. "
               "أهدافك محفوظة في قاعدة البيانات، فتبقى كما تركتها في أي زيارة قادمة.")

    monthly_surplus = max(0, avg_12 - last.Total_Expenses)
    total_monthly_save = round(monthly_surplus * 0.20)

    # أهداف افتراضية مبدئية تُزرع في قاعدة البيانات مرّة واحدة فقط لكل فريلانسر،
    # بعدها يقرأ التطبيق ويكتب مباشرةً من/إلى الجدول، لا من ذاكرة الجلسة.
    default_goals = [
        {"name":"تعليم الأبناء", "target":150_000, "share":50, "balance":round(last.Savings*0.50)},
        {"name":"شراء منزل",     "target":500_000, "share":25, "balance":round(last.Savings*0.25)},
        {"name":"رأس مال مشروع", "target":100_000, "share":15, "balance":round(last.Savings*0.15)},
        {"name":"سيارة",         "target":80_000,  "share":10, "balance":round(last.Savings*0.10)},
    ]
    db.seed_default_goals(fid, default_goals)
    forest = {"goals": db.load_goals(fid), "months": db.get_months_simulated(fid)}

    st.markdown(f"""<div class="metric-card" style="margin-bottom:14px">
      <div class="metric-label">إجمالي ادخارك الشهري (20% من فائضك: {monthly_surplus:,.0f} {RIYAL})</div>
      <div class="metric-val">{total_monthly_save:,.0f} {RIYAL}</div>
    </div>""", unsafe_allow_html=True)

    # ─── تعريف الأهداف يدوياً ───
    with st.expander("إدارة أهدافك (الاسم · المبلغ المستهدف · نسبة الادخار)", expanded=True):
        st.caption("لكل فريلانسر أهدافه. عدّل الاسم والمبلغ ونسبة الادخار لكل هدف. "
                   "النِّسب تحدّد كيف يُوزَّع ادخارك الشهري، ويُفضّل أن يكون مجموعها 100%.")
        new_goals = []
        delete_idx = None
        for i, g in enumerate(forest["goals"]):
            gc1, gc2, gc3, gc4 = st.columns([3,3,2,1])
            with gc1:
                nm = st.text_input("اسم الهدف", value=g["name"], key=f"gn_{fid}_{i}")
            with gc2:
                tg = st.number_input(f"المبلغ المستهدف ({RIYAL_TXT})", min_value=1000,
                                     max_value=5_000_000, value=int(g["target"]),
                                     step=1000, key=f"gt_{fid}_{i}")
            with gc3:
                sh = st.number_input("نسبة الادخار %", min_value=0, max_value=100,
                                     value=int(g["share"]), step=5, key=f"gs_{fid}_{i}")
            with gc4:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("حذف", key=f"gd_{fid}_{i}", use_container_width=True):
                    delete_idx = i
            new_goals.append({"name":nm, "target":tg, "share":sh,
                              "balance":g.get("balance",0)})
        if delete_idx is not None:
            new_goals.pop(delete_idx)
        forest["goals"] = new_goals
        db.save_goals(fid, new_goals)
        if delete_idx is not None:
            st.rerun()

        ac1, ac2 = st.columns([1,3])
        with ac1:
            if st.button("+ أضف هدفاً", use_container_width=True):
                forest["goals"].append({"name":"هدف جديد", "target":50_000,
                                        "share":0, "balance":0})
                db.save_goals(fid, forest["goals"])
                st.rerun()

    total_share = sum(g["share"] for g in forest["goals"])
    if forest["goals"] and total_share != 100:
        st.warning(f"مجموع نِسب الادخار **{total_share}%**، يُفضّل ضبطها على 100% "
                   f"({'انقص' if total_share>100 else 'أضف'} {abs(100-total_share)}%).")

    # ─── أزرار المحاكاة ───
    st.markdown(f"""<div style="background:#f2f8f4;border-radius:12px;padding:12px 16px;margin:8px 0;
    font-size:14px;color:#0E2A1F">
    <b>الأشهر المُحاكاة: {forest['months']}</b> 
    زر «محاكاة شهر» يضيف ادخار شهر واحد لكل شجرة حسب نسبتها، لتشاهد النموّ.
    زر «إعادة تعيين» يرجّع كل الأهداف والأرصدة إلى البداية.
    </div>""", unsafe_allow_html=True)

    b1, b2, _ = st.columns([1,1,2])
    with b1:
        valid = (total_share == 100) and len(forest["goals"])>0
        sim_month = st.button("محاكاة شهر", disabled=not valid, use_container_width=True)
    with b2:
        reset = st.button("إعادة تعيين", use_container_width=True)

    if sim_month and valid:
        for g in forest["goals"]:
            g["balance"] += total_monthly_save * (g["share"]/100)
        forest["months"] += 1
        db.save_goals(fid, forest["goals"])
        db.set_months_simulated(fid, forest["months"])
        st.rerun()
    if reset:
        db.reset_forest(fid)
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── عرض الأشجار ───
    if not forest["goals"]:
        st.info("أضف هدفاً واحداً على الأقل لتبدأ غابتك.")
    else:
        cols = st.columns(len(forest["goals"]))
        for col, g in zip(cols, forest["goals"]):
            saved = g["balance"]
            target = g["target"]
            share_save = total_monthly_save * (g["share"]/100)
            progress = min(1.0, saved / max(1, target))
            name, icon, msg = tree_stage(progress)
            m_left = months_to_goal(target, saved, share_save)

            if progress >= 1.0:
                when_txt = "أثمرت! \U0001F389"
            elif m_left is None:
                when_txt = "زد نسبته لينمو"
            elif m_left > 180:
                when_txt = "هدف بعيد المدى"
            else:
                yrs, mos = m_left//12, m_left%12
                when_txt = (f"{yrs} سنة و{mos} شهر" if yrs else f"{mos} شهر")

            with col:
                st.markdown(f"""<div style="background:linear-gradient(160deg,#eaf6ee,#d8f0e0);
                border-radius:20px;padding:18px 12px;text-align:center;
                border:2px solid {PRIMARY}22;min-height:400px">
                  <div style="font-weight:800;color:{DARK};font-size:15px;min-height:40px">{g['name']}</div>
                  <div style="font-size:60px;line-height:1.2;margin:6px 0">{icon}</div>
                  <div style="font-weight:700;color:{PRIMARY};font-size:14px">{name}</div>
                  <div style="color:#6b7c72;font-size:11px;margin:4px 6px;min-height:32px">{msg}</div>
                  <div style="font-size:24px;font-weight:800;color:{DARK};margin-top:6px">
                    {progress*100:.0f}%</div>
                  <div style="color:#6b7c72;font-size:11px">
                    {saved:,.0f} / {target:,.0f} {RIYAL}</div>
                  <div style="background:#fff;border-radius:10px;padding:8px;margin-top:10px;
                              font-size:11px;color:#0E2A1F">
                    نصيبه: <b>{g['share']}%</b> = <b>{share_save:,.0f} {RIYAL}</b>/شهر<br>
                    يُثمر خلال: <b>{when_txt}</b>
                  </div>
                </div>""", unsafe_allow_html=True)

    # ─── تصدير الغابة PDF ───
    if forest["goals"]:
        st.markdown("<br>", unsafe_allow_html=True)
        cards_html = ""
        for g in forest["goals"]:
            saved=g["balance"]; target=g["target"]; pr=min(1.0,saved/max(1,target))
            nm,ic,mg = tree_stage(pr)
            cards_html += f"""<div style="display:inline-block;width:30%;margin:1%;vertical-align:top;
            background:#eaf6ee;border-radius:14px;padding:14px;text-align:center;border:1px solid #00833E33">
              <div style="font-weight:700;color:#0E2A1F">{g['name']}</div>
              <div style="font-size:44px">{ic}</div>
              <div style="color:#00833E;font-weight:700">{nm}، {pr*100:.0f}%</div>
              <div style="font-size:12px;color:#555">{saved:,.0f} / {target:,.0f} ريال</div>
            </div>"""
        forest_pdf = f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<style>
 {FONT_FACE_CSS}
 body {{ font-family:{FONT_FAMILY}; direction:rtl; margin:0; background:#eef2f0; padding:16px }}
 #doc {{ background:#fff; padding:30px; max-width:760px; margin:0 auto }}
 h1 {{ color:#00833E; text-align:center; border-bottom:3px solid #00833E; padding-bottom:12px }}
 #btn {{ display:block; margin:0 auto 14px; background:#00833E; color:#fff; border:none;
        padding:11px 28px; border-radius:12px; font-family:{FONT_FAMILY}; font-weight:700;
        font-size:15px; cursor:pointer }}
</style></head><body>
<button id="btn" onclick="dl()">تصدير الأهداف PDF</button>
<div id="doc">
  <img src="data:image/jpeg;base64,{LOGO_B64}" style="height:56px;display:block;margin:0 auto 8px">
  <h1>خطة أهداف الادخار، {uname}</h1>
  <p style="text-align:center;color:#6b7c72">ادخار شهري {total_monthly_save:,.0f} ريال ·
     أشهر مُحاكاة: {forest['months']}</p>
  <div style="text-align:center">{cards_html}</div>
  <p style="text-align:center;color:#6b7c72;font-size:12px;margin-top:20px">
     مستقل · Mustaqil، هاكاثون أمد</p>
</div>
<script>
function dl() {{
  html2pdf().set({{margin:8, filename:'أهداف_{uname}.pdf',
    image:{{type:'jpeg',quality:0.98}}, html2canvas:{{scale:2,useCORS:true}},
    jsPDF:{{unit:'mm',format:'a4',orientation:'portrait'}}}}
  ).from(document.getElementById('doc')).save();
}}
</script></body></html>"""
        with st.expander("تصدير خطة الأهداف كملف PDF"):
            components.html(forest_pdf, height=520, scrolling=True)

    # اقتراح ذكي
    if valid and total_monthly_save > 0:
        incomplete = [g for g in forest["goals"]
                      if g["balance"] < g["target"] and g["share"] > 0]
        if incomplete:
            slow = max(incomplete, key=lambda g: months_to_goal(
                g["target"], g["balance"], total_monthly_save*(g["share"]/100)) or 0)
            cur = total_monthly_save*(slow["share"]/100)
            boost = max(200, round(total_monthly_save*0.15/50)*50)
            ms = months_to_goal(slow["target"], slow["balance"], cur)
            mf = months_to_goal(slow["target"], slow["balance"], cur+boost)
            if ms and mf and (ms-mf)>0 and ms<=600:
                st.info(f"**اقتراح ذكي:** لو رفعت نصيب «{slow['name']}» بما يعادل "
                        f"{boost:,.0f} {RIYAL_TXT} شهرياً، لأثمر قبل **{ms-mf} شهراً** من موعده.")

    st.markdown("---")
    st.info("**الربط بالراتب الاصطناعي:** فائض الأشهر الجيدة يُوزَّع تلقائياً، "
            "50% صندوق الطوارئ · 30% المشاريع · **20% يُسقي غابة أهدافك**.")


# ───────────────────────── تبويب 9 : حاسبة الزكاة ─────────────────────
with tab9:
    st.markdown("#### حاسبة زكاة المال")
    st.caption("زكاة المال: **2.5%** ممّا بلغ النصاب وحال عليه الحول. "
               "أدخل المبلغ الذي معك وسعر جرام الذهب، وتُحسب الزكاة تلقائياً.")

    z1, z2 = st.columns(2)
    with z1:
        gold_price = st.number_input(f"سعر جرام الذهب عيار 24 ({RIYAL_TXT})",
                                     100.0, 1000.0, 480.0, step=1.0)
        st.caption("اكتب سعر الجرام الحالي من السوق.")
    with z2:
        savings = st.number_input(f"المبلغ الذي معك ({RIYAL_TXT})", 0.0, 5_000_000.0,
                                  float(round(last.Savings)), step=100.0)

    nisab = gold_price * 85          # النصاب الشرعي
    wealth = savings
    due = max(0.0, wealth) * 0.025

    st.markdown("<br>", unsafe_allow_html=True)
    zc1, zc2, zc3 = st.columns(3)
    zc1.markdown(f'<div class="metric-card"><div class="metric-label">النصاب (85 جم ذهب)</div>'
                 f'<div class="metric-val">{nisab:,.0f} {RIYAL}</div></div>', unsafe_allow_html=True)
    zc2.markdown(f'<div class="metric-card gold"><div class="metric-label">وعاء الزكاة</div>'
                 f'<div class="metric-val">{max(0,wealth):,.0f} {RIYAL}</div>'
                 f'<div class="metric-label">المبلغ الذي معك</div></div>', unsafe_allow_html=True)
    zc3.markdown(f'<div class="metric-card"><div class="metric-label">نسبة الزكاة</div>'
                 f'<div class="metric-val">2.5%</div>'
                 f'<div class="metric-label">ربع العشر</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if wealth < nisab:
        st.markdown(f"""<div class="alert-safe">
        <b>لم يبلغ مالك النصاب</b><br><br>
        وعاء الزكاة: <b>{max(0,wealth):,.0f} {RIYAL_WHITE}</b>، والنصاب <b>{nisab:,.0f} {RIYAL_WHITE}</b><br>
        ينقصك <b>{nisab-max(0,wealth):,.0f} {RIYAL_WHITE}</b> لبلوغ النصاب.<br><br>
        لا زكاة عليك في هذا المال حالياً.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="salary-box">
          <div style="font-size:16px;opacity:.9">الزكاة الواجبة</div>
          <div class="num">{due:,.0f} {RIYAL_WHITE}</div>
          <div style="font-size:15px;opacity:.9">2.5% من {wealth:,.0f} {RIYAL_WHITE}، بعد حَوَلان الحول</div>
        </div>""", unsafe_allow_html=True)
        st.success(f"بلغ مالك النصاب. تُخرَج الزكاة عند تمام الحول (354 يوماً) على المال.")

    with st.expander("كيف حُسبت الزكاة؟"):
        st.markdown("""
        - **النصاب**: أقلّ مقدار تجب فيه الزكاة، ويُقدَّر بقيمة **85 جراماً من الذهب** عيار 24.
        - **وعاء الزكاة** = المبلغ النقدي الذي بلغ النصاب وحال عليه الحول.
        - **المقدار** = 2.5% (ربع العشر) ممّا بلغ النصاب.
        - **الحول**: يشترط مرور سنة (354 يوماً) على بلوغ المال النصاب.

        هذه الحاسبة **إرشادية**، وللحالات الخاصّة (زكاة الأسهم، العقار، الدَّين المشكوك فيه)
        يُرجع إلى أهل العلم أو الهيئة الشرعية.
        """)

    st.markdown("""
    <a href="https://zakaty.zatca.gov.sa/fm/long_zakah" target="_blank"
       style="display:inline-block;background:#00833E;color:#fff;padding:12px 26px;
       border-radius:12px;font-weight:700;text-decoration:none;margin-top:8px">
       احسب زكاتك رسمياً عبر منصّة «زكاتي» من هيئة الزكاة والضريبة
    </a>
    """, unsafe_allow_html=True)
    st.caption("حاسبتنا تعطيك تقديراً فورياً من بياناتك. وللحساب الرسمي المعتمد، "
               "تنقلك المنصّة الحكومية «زكاتي».")

# ───────────────────────── تبويب : الفاتورة الإلكترونية ─────────────────────
with tab_invoice:
    st.markdown("#### الفاتورة الإلكترونية المبسّطة")
    st.caption("فاتورة ضريبية مبسّطة برمز QR مبني على ترميز TLV القياسي المعتمد في فوترة "
               "(ZATCA) المرحلة الأولى، للفريلانسرز المسجّلين في ضريبة القيمة المضافة.")

    iv1, iv2 = st.columns(2)
    with iv1:
        inv_client = st.text_input("اسم العميل", value="عميل تجريبي")
        inv_desc = st.text_input("وصف الخدمة", value=f"خدمات {specialty}")
        inv_vat_number = st.text_input("الرقم الضريبي للمنشأة (15 رقماً)",
                                       value="300000000000003", max_chars=15)
    with iv2:
        inv_amount = st.number_input(f"المبلغ قبل الضريبة ({RIYAL_TXT})", min_value=1.0,
                                     max_value=1_000_000.0, value=5000.0, step=100.0)
        inv_number = db.next_invoice_number(fid)
        st.text_input("رقم الفاتورة", value=inv_number, disabled=True)
        st.caption("يُنشأ رقم الفاتورة تلقائياً بالتسلسل داخل قاعدة البيانات.")

    valid_vat = (inv_vat_number.isdigit() and len(inv_vat_number) == 15
                and inv_vat_number[0] == "3" and inv_vat_number[-1] == "3")
    if not valid_vat:
        st.caption("الرقم الضريبي السعودي 15 رقماً، يبدأ وينتهي بالرقم 3، "
                   "القيمة الحالية للتجربة فقط.")

    vat_amount = round(inv_amount * VAT_RATE, 2)
    total_incl_vat = round(inv_amount + vat_amount, 2)
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tc1, tc2, tc3 = st.columns(3)
    tc1.markdown(f'<div class="metric-card"><div class="metric-label">المبلغ قبل الضريبة</div>'
                f'<div class="metric-val">{inv_amount:,.2f} {RIYAL}</div></div>', unsafe_allow_html=True)
    tc2.markdown(f'<div class="metric-card gold"><div class="metric-label">ضريبة القيمة المضافة (15%)</div>'
                f'<div class="metric-val">{vat_amount:,.2f} {RIYAL}</div></div>', unsafe_allow_html=True)
    tc3.markdown(f'<div class="metric-card"><div class="metric-label">الإجمالي شامل الضريبة</div>'
                f'<div class="metric-val">{total_incl_vat:,.2f} {RIYAL}</div></div>', unsafe_allow_html=True)

    if st.button("إصدار الفاتورة وتوليد رمز QR"):
        payload_b64 = zatca_tlv_payload(uname, inv_vat_number, issued_at,
                                        total_incl_vat, vat_amount)
        # رمز QR الظاهر للمستخدم يحمل ملخّصاً مقروءاً للفاتورة كي يعرضه أي جوال
        # عند المسح مباشرةً، بدل حمولة TLV الثنائية التي لا تُقرأ إلا آلياً
        # (هي محفوظة أدناه وفي قاعدة البيانات لأغراض التوثيق التقني).
        readable_summary = (
            f"فاتورة مستقل | Mustaqil\n"
            f"رقم الفاتورة: {inv_number}\n"
            f"البائع: {uname} ({specialty})\n"
            f"الرقم الضريبي للبائع: {inv_vat_number}\n"
            f"العميل: {inv_client}\n"
            f"الوصف: {inv_desc}\n"
            f"التاريخ: {issued_at}\n"
            f"المبلغ قبل الضريبة: {inv_amount:,.2f} ريال\n"
            f"ضريبة القيمة المضافة (15%): {vat_amount:,.2f} ريال\n"
            f"الإجمالي شامل الضريبة: {total_incl_vat:,.2f} ريال"
        )
        qr_png_b64 = make_qr_png_b64(readable_summary)
        db.save_invoice(fid, inv_number, inv_client, inv_desc, inv_amount,
                        vat_amount, total_incl_vat, inv_vat_number, issued_at, payload_b64)
        st.session_state["_last_invoice"] = {
            "qr": qr_png_b64, "payload": payload_b64, "number": inv_number,
            "client": inv_client, "desc": inv_desc, "amount": inv_amount,
            "vat": vat_amount, "total": total_incl_vat, "issued_at": issued_at,
        }
        st.success(f"صدرت الفاتورة {inv_number} وحُفظت في سجلّك.")

    if "_last_invoice" in st.session_state:
        li = st.session_state["_last_invoice"]
        qc1, qc2 = st.columns([1, 2])
        with qc1:
            st.image(base64.b64decode(li["qr"]), caption="امسح الرمز لعرض تفاصيل الفاتورة", width=200)
        with qc2:
            st.caption("رمز QR أعلاه يعرض تفاصيل الفاتورة مباشرةً عند مسحه بكاميرا أي جوال.")
            with st.expander("الحمولة القياسية المعتمدة في فوترة (ZATCA) — TLV Base64"):
                st.caption("في نظام فوترة معتمد فعلياً يحمل رمز QR هذه البيانات المرمَّزة بدل "
                           "النص المقروء، لتُقرأ آلياً من أنظمة الجهة الضريبية. نعرضها هنا "
                           "للتوثيق التقني، وهي المحفوظة في قاعدة البيانات مع الفاتورة.")
                st.code(li["payload"], language=None)

        inv_doc_inner = f"""<div class="head">
  <img src="data:image/jpeg;base64,{LOGO_B64}" style="height:60px;margin-bottom:8px">
  <h1>فاتورة ضريبية مبسّطة</h1>
  <p>مستقل · Mustaqil، الرفيق المالي للفريلانسر السعودي</p>
</div>
<table>
  <tr><th>رقم الفاتورة</th><td>{li['number']}</td></tr>
  <tr><th>التاريخ</th><td>{li['issued_at']}</td></tr>
  <tr><th>البائع</th><td>{uname} · {specialty}</td></tr>
  <tr><th>الرقم الضريبي للبائع</th><td>{inv_vat_number}</td></tr>
  <tr><th>العميل</th><td>{li['client']}</td></tr>
  <tr><th>وصف الخدمة</th><td>{li['desc']}</td></tr>
  <tr><th>المبلغ قبل الضريبة</th><td>{li['amount']:,.2f} {_riyal_doc}</td></tr>
  <tr><th>ضريبة القيمة المضافة (15%)</th><td>{li['vat']:,.2f} {_riyal_doc}</td></tr>
</table>
<div class="score">الإجمالي شامل الضريبة<br><b>{li['total']:,.2f} {_riyal_doc}</b></div>
<div style="text-align:center;margin-top:18px">
  <img src="data:image/png;base64,{li['qr']}" style="height:150px">
  <p style="color:#6b7c72;font-size:12px">رمز QR متوافق مع ترميز فوترة (ZATCA) المرحلة الأولى</p>
</div>
<div class="foot">
  هذا نموذج أوّلي لأغراض الهاكاثون، وليس فاتورة ضريبية معتمدة رسمياً.<br>
  مستقل · Mustaqil، هاكاثون أمد · مصرف الإنماء × أكاديمية طويق.
</div>"""

        inv_doc_component = f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<style>
 {FONT_FACE_CSS}
 body {{ font-family:{FONT_FAMILY}; direction:rtl; margin:0; color:#0E2A1F;
        background:#eef2f0; padding:16px; }}
 #doc {{ background:#fff; padding:40px; max-width:720px; margin:0 auto; }}
 .head {{ border-bottom:4px solid #00833E; padding-bottom:16px; margin-bottom:20px; text-align:center; }}
 .head h1 {{ margin:6px 0 0; color:#00833E; font-size:26px; }}
 .head p {{ margin:4px 0 0; color:#6b7c72; }}
 table {{ width:100%; border-collapse:collapse; margin-top:14px; }}
 th,td {{ border:1px solid #d6e2da; padding:11px 14px; text-align:right; }}
 th {{ background:#f2f8f4; width:48%; font-weight:700; }}
 .score {{ background:#00833E; color:#fff; padding:18px; border-radius:12px;
          text-align:center; margin-top:22px; }}
 .score b {{ font-size:26px; }}
 .foot {{ margin-top:22px; font-size:13px; color:#6b7c72; border-top:1px solid #d6e2da;
         padding-top:14px; text-align:center; }}
 #btn {{ display:block; margin:0 auto 16px; background:#00833E; color:#fff; border:none;
        padding:12px 30px; border-radius:12px; font-family:{FONT_FAMILY}; font-weight:700;
        font-size:16px; cursor:pointer; }}
</style></head><body>
<button id="btn" onclick="dl()">تحميل PDF</button>
<div id="doc">{inv_doc_inner}</div>
<script>
function dl() {{
  var el = document.getElementById('doc');
  html2pdf().set({{
    margin: 8, filename: 'فاتورة_{li["number"]}.pdf',
    image: {{type:'jpeg', quality:0.98}},
    html2canvas: {{scale:2, useCORS:true}},
    jsPDF: {{unit:'mm', format:'a4', orientation:'portrait'}}
  }}).from(el).save();
}}
</script>
</body></html>"""
        with st.expander("تصدير الفاتورة كملف PDF"):
            components.html(inv_doc_component, height=760, scrolling=True)

    st.markdown("---")
    st.markdown("##### سجلّ فواتيرك")
    inv_hist = db.load_invoices(fid)
    if len(inv_hist) == 0:
        st.info("لم تُصدر أي فاتورة بعد من هذا الحساب.")
    else:
        inv_show = inv_hist.rename(columns={
            "invoice_number": "رقم الفاتورة", "client_name": "العميل",
            "description": "الوصف", "amount_excl_vat": "قبل الضريبة",
            "vat_amount": "الضريبة", "total_incl_vat": "الإجمالي",
            "issued_at": "التاريخ"})
        st.dataframe(inv_show, use_container_width=True, hide_index=True)

    st.warning("هذا نموذج أوّلي لأغراض الهاكاثون. للاستخدام الرسمي المعتمد من هيئة "
               "الزكاة والضريبة والجمارك (ZATCA) يلزم ربط فعلي بمزوّد حلول فوترة معتمد.")

# ───────────────────────── تبويب 10 : أداء النماذج ─────────────────────
with tab10:
    st.markdown("#### أداء النماذج الأربعة")
    st.caption("هذه النتائج محسوبة على بيانات اختبار منفصلة (25%) لم تُدرَّب عليها النماذج.")

    g1,g2 = st.columns(2)
    with g1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">النموذج 1 · التنبؤ بشهر الجفاف</div>'
                    f'<div class="metric-val">{METRICS["dry_acc"]:.1f}%</div>'
                    f'<div class="metric-label">دقة التصنيف (Accuracy)</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card"><div class="metric-label">النموذج 3 · اقتراح التسعير</div>'
                    f'<div class="metric-val">R² = {METRICS["price_r2"]:.2f}</div>'
                    f'<div class="metric-label">متوسط الخطأ: {METRICS["price_mae"]:,.0f} ريال</div></div>', unsafe_allow_html=True)
    with g2:
        st.markdown(f'<div class="metric-card gold"><div class="metric-label">النموذج 2 · التنبؤ بالدخل القادم</div>'
                    f'<div class="metric-val">R² = {METRICS["income_r2"]:.2f}</div>'
                    f'<div class="metric-label">متوسط الخطأ: {METRICS["income_mae"]:,.0f} ريال</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card gold"><div class="metric-label">النموذج 4 · كاشف العميل الخطر</div>'
                    f'<div class="metric-val">{METRICS["late_acc"]:.1f}%</div>'
                    f'<div class="metric-label">الدقة · AUC = {METRICS["late_auc"]:.3f}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    **ماذا تعني هذه الأرقام؟ (بلغة بسيطة)**

    - **الدقة**: من كل 100 حالة اختبار، كم واحدة توقّعها النموذج صحيحة. مثلاً دقة 90% تعني
      أنه أصاب في 90 من كل 100.
    - **معامل الجودة (R²)**: رقم بين 0 و 1 يقيس مدى قرب توقّعات النموذج من الحقيقة.
      كلما اقترب من 1، كان النموذج أدقّ. نموذج التسعير قريب من 1 لأن سعر المشروع يتبع
      منطقاً واضحاً (ساعات العمل، التعقيد، نوع العميل).
    - **قوة التمييز (AUC)**: خاصّ بالنماذج التي تجيب بنعم/لا. 0.5 يعني تخمين عشوائي،
      و1 يعني تمييزاً مثالياً. كاشف العميل الخطر قويّ في التمييز.
    - **متوسّط الخطأ**: بالريال، كم يبتعد توقّع النموذج عن القيمة الحقيقية في المتوسّط.
    - **لماذا نموذج الدخل رقمه منخفض؟** لأن دخل الفريلانسر متقلّب وصعب التنبؤ به أصلاً
      وهذه هي المشكلة التي يحلّها التطبيق. رغم ذلك يلتقط النموذج الاتجاه الموسمي العام،
      ونعرض رقمه الحقيقي بشفافية دون تجميل.
    """)

    st.markdown("---")
    st.markdown("##### قاعدة البيانات")
    st.caption("قاعدة بيانات SQLite الحيّة تعيش داخل خادم التطبيق ولا تظهر في أي رابط "
               "عام، نزّل نسخة منها لفتحها ببرنامج مثل DB Browser for SQLite أو بأي "
               "أداة تتعامل مع SQLite.")
    if os.path.exists(db.DB_PATH):
        with open(db.DB_PATH, "rb") as _dbf:
            st.download_button("⬇️ تنزيل قاعدة البيانات الحالية (mustaqil.db)",
                               data=_dbf.read(), file_name="mustaqil.db",
                               mime="application/octet-stream")
    else:
        st.info("لم تُنشأ قاعدة البيانات بعد.")

st.markdown("---")
st.markdown("<center style='color:#6b7c72'>مستقل · Mustaqil، هاكاثون أمد · "
            "مصرف الإنماء × أكاديمية طويق</center>", unsafe_allow_html=True)
