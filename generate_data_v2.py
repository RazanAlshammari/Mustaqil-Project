# -*- coding: utf-8 -*-
"""
مستقل | Mustaqil — مولّد البيانات الوهمية للفريلانسرز السعوديين
يولّد ملفين:
  1) monthly_data  : صف لكل فريلانسر × كل شهر  (للتحليل + التنبؤ بشهر الجفاف + التنبؤ بالدخل)
  2) projects_data : صف لكل مشروع                (لاقتراح التسعير)
"""

import numpy as np
import pandas as pd

np.random.seed(42)

# ---------------------------------------------------------------------------
# إعدادات عامة
# ---------------------------------------------------------------------------
N_MONTHS      = 18          # عدد الأشهر لكل فريلانسر
START_YEAR    = 2024
START_MONTH   = 1

ARABIC_NAMES = [
    "عبدالله الشهري","نورة القحطاني","محمد العتيبي","سارة الدوسري","فيصل الحربي",
    "ريم المطيري","خالد الزهراني","لمى الغامدي","عبدالعزيز السبيعي","هند العنزي",
    "تركي الرشيدي","جواهر البقمي","سلطان الشمري","أمل الخالدي","ناصر الجهني",
    "دانة العمري","ماجد الثقفي","شهد الحمدان","يوسف البلوي","رغد المالكي",
    "بدر الفيفي","العنود السهلي","راكان الدغيري","وعد القرني","فهد الصاعدي",
    "غادة المنصوري","عمر الخثعمي","لين الراجحي","صالح المحمدي","جنى العسيري",
    "زياد الوادعي","ميساء البراك","طلال الرويلي","رنا الحازمي","نواف الشريف",
    "أروى السديري","مازن الطويرقي","بيان الفهد","عبدالرحمن الزايدي","تالا الحكمي",
    "سعود الدخيل","شوق العامري","وليد المعيوف","دلال الهاجري","إبراهيم البيشي",
    "ملاك الشهراني","حسام الجاسر","رهف العقيل","أنس الخليفة","غيداء التركي",
    "عبدالمجيد القرشي","سلمى الشهراني","يزيد الحارثي","نجلاء الشمري","فارس العنزي",
    "روان الغامدي","ماجد السلمي","هيفاء المري","عبدالوهاب الحميد","لجين الزهراني",
    "عبدالإله الخالدي","سارة الجعيد","بندر الحميدي","العنود الرشيد","تميم الشمري",
    "وجدان الدوسري","ياسر القحطاني","منى العتيبي","راشد الغانم","جود المطيري",
]

# تخصصات الفريلانسر — لكل تخصص ملف دخل وتقلب مختلف
SPECIALTIES = {
    "تطوير برمجيات": {"base": 16000, "volatility": 0.45, "project_base": 9000,  "rate": 220},
    "تصميم جرافيك":  {"base": 9000,  "volatility": 0.55, "project_base": 3500,  "rate": 120},
    "كتابة محتوى":   {"base": 6500,  "volatility": 0.50, "project_base": 1800,  "rate": 80},
    "تسويق رقمي":    {"base": 11000, "volatility": 0.50, "project_base": 5000,  "rate": 150},
    "مونتاج فيديو":  {"base": 8500,  "volatility": 0.60, "project_base": 2800,  "rate": 110},
    "ترجمة":         {"base": 5500,  "volatility": 0.40, "project_base": 1500,  "rate": 70},
    "استشارات":      {"base": 14000, "volatility": 0.50, "project_base": 7500,  "rate": 300},
}

# 10 فريلانسرز لكل تخصّص بالضبط (7 تخصّصات × 10 = 70)، بدل توزيع عشوائي بحت،
# حتى تكون مقارنة الأقران ذات معنى إحصائياً لكل تخصّص بلا استثناء.
FREELANCERS_PER_SPECIALTY = 10
N_FREELANCERS = len(SPECIALTIES) * FREELANCERS_PER_SPECIALTY
SPECIALTY_ASSIGNMENT = list(SPECIALTIES.keys()) * FREELANCERS_PER_SPECIALTY
np.random.shuffle(SPECIALTY_ASSIGNMENT)

CLIENT_TYPES = ["فرد", "شركة صغيرة", "شركة كبيرة", "جهة حكومية"]
CLIENT_MULTIPLIER = {"فرد": 0.8, "شركة صغيرة": 1.0, "شركة كبيرة": 1.4, "جهة حكومية": 1.6}

# سلوك السداد لكل نوع عميل: (متوسط أيام التأخير، التشتت، احتمال التعثّر الكامل)
# واقعياً: الأفراد يدفعون بسرعة لكن يتعثّرون أكثر؛ الجهات الحكومية تدفع بأمان لكن ببطء.
CLIENT_PAYMENT = {
    "فرد":         {"mean_delay": 12, "std": 10, "default_risk": 0.10},
    "شركة صغيرة":  {"mean_delay": 20, "std": 12, "default_risk": 0.06},
    "شركة كبيرة":  {"mean_delay": 35, "std": 15, "default_risk": 0.02},
    "جهة حكومية":  {"mean_delay": 55, "std": 18, "default_risk": 0.01},
}

# مواسم الجفاف: رمضان والصيف عادة دخل أقل للكثير من التخصصات
# (مبسّط: نعطي معامل موسمي لكل شهر ميلادي)
SEASONAL = {
    1: 1.05, 2: 1.00, 3: 0.75, 4: 0.80, 5: 0.95, 6: 0.70,
    7: 0.65, 8: 0.85, 9: 1.10, 10: 1.15, 11: 1.10, 12: 1.20,
}


def month_iter(start_year, start_month, n):
    y, m = start_year, start_month
    for _ in range(n):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# توليد البيانات
# ---------------------------------------------------------------------------
monthly_rows = []
project_rows = []
project_counter = 1

for fid in range(1, N_FREELANCERS + 1):
    name = ARABIC_NAMES[fid - 1]
    specialty = SPECIALTY_ASSIGNMENT[fid - 1]
    spec = SPECIALTIES[specialty]

    # خصائص ثابتة لكل فريلانسر
    fixed_expenses = float(np.random.randint(2500, 7000))   # إيجار + فواتير ثابتة
    savings = float(np.random.randint(0, 25000))            # مدخرات بداية
    emergency_fund = float(np.random.randint(0, 15000))     # صندوق طوارئ
    loan_amount = float(np.random.choice([0, 0, 0, 5000, 12000, 30000]))
    skill_factor = np.random.uniform(0.85, 1.25)           # مهارة الفريلانسر

    months = list(month_iter(START_YEAR, START_MONTH, N_MONTHS))
    incomes = []

    for idx, (year, month) in enumerate(months):
        seasonal = SEASONAL[month]
        noise = np.random.normal(1.0, spec["volatility"])
        noise = max(0.05, noise)  # لا يصير سالب

        income = spec["base"] * skill_factor * seasonal * noise
        # احتمال شهر بلا أي مشروع (دخل شبه صفر)
        if np.random.random() < 0.08:
            income *= np.random.uniform(0.0, 0.15)
        income = round(max(0, income), 0)
        incomes.append(income)

        # المصاريف
        variable_expenses = round(income * np.random.uniform(0.10, 0.30), 0)
        total_expenses = fixed_expenses + variable_expenses

        # عدد المشاريع هذا الشهر
        if income < spec["base"] * 0.2:
            n_projects = np.random.choice([0, 1], p=[0.6, 0.4])
        else:
            n_projects = np.random.randint(1, 5)

        # تحديث المدخرات وصندوق الطوارئ
        net = income - total_expenses
        savings = max(0, savings + net * np.random.uniform(0.3, 0.6))
        emergency_fund = max(0, emergency_fund + max(0, net) * np.random.uniform(0.1, 0.2))
        bank_balance = round(savings + emergency_fund + np.random.uniform(0, 3000), 0)

        payment_delay = int(np.random.choice([0, 5, 10, 15, 30, 45],
                                             p=[0.25, 0.25, 0.2, 0.15, 0.1, 0.05]))

        monthly_rows.append({
            "Freelancer_ID": fid,
            "Name": name,
            "Specialty": specialty,
            "Year": year,
            "Month": month,
            "Income": income,
            "Fixed_Expenses": fixed_expenses,
            "Variable_Expenses": variable_expenses,
            "Total_Expenses": round(total_expenses, 0),
            "Savings": round(savings, 0),
            "Emergency_Fund": round(emergency_fund, 0),
            "Bank_Balance": bank_balance,
            "Number_of_Projects": n_projects,
            "Payment_Delay_Days": payment_delay,
            "Loan_Amount": loan_amount,
        })

        # توليد المشاريع لهذا الشهر
        for _ in range(n_projects):
            client = np.random.choice(CLIENT_TYPES, p=[0.35, 0.30, 0.20, 0.15])
            cmult = CLIENT_MULTIPLIER[client]
            duration = int(np.random.randint(3, 45))            # أيام
            complexity = np.random.uniform(0.7, 1.5)            # تعقيد المشروع
            hours = duration * np.random.uniform(2, 6)          # ساعات عمل تقديرية

            # السعر "العادل" = ساعات × سعر الساعة × تعقيد × معامل العميل × مهارة
            fair_price = spec["rate"] * hours * complexity * cmult * skill_factor
            # ضوضاء سوقية
            project_value = round(fair_price * np.random.normal(1.0, 0.15), 0)
            project_value = max(spec["project_base"] * 0.3, project_value)

            # سلوك سداد هذا المشروع (يعتمد على نوع العميل + حجم المشروع)
            pay = CLIENT_PAYMENT[client]
            size_factor = 1 + (project_value / 20000)      # المشاريع الكبيرة تتأخر أكثر
            delay = np.random.normal(pay["mean_delay"] * size_factor, pay["std"])
            delay = int(max(0, min(120, delay)))
            defaulted = int(np.random.random() < pay["default_risk"])
            if defaulted:
                delay = int(np.random.randint(90, 180))   # التعثّر = تأخير طويل جداً

            project_rows.append({
                "Project_ID": project_counter,
                "Freelancer_ID": fid,
                "Specialty": specialty,
                "Client_Type": client,
                "Project_Duration_Days": duration,
                "Estimated_Hours": round(hours, 1),
                "Complexity": round(complexity, 2),
                "Hourly_Rate": spec["rate"],
                "Project_Value": round(project_value, 0),
                "Payment_Delay_Days": delay,
                "Late_Payment": int(delay > 30),   # الهدف: تأخّر يتجاوز 30 يوماً
                "Defaulted": defaulted,
            })
            project_counter += 1

    # ----- تسميات الهدف (Targets) للجدول الشهري -----
    incomes = np.array(incomes)
    avg_income = incomes.mean()

    for i in range(len(months)):
        row = monthly_rows[-(N_MONTHS) + i]

        # Dry_Month_Label: شهر جفاف إذا الدخل أقل من 50% من متوسط الفريلانسر
        is_dry = "Yes" if incomes[i] < 0.5 * avg_income else "No"
        row["Dry_Month_Label"] = is_dry

        # Next_Month_Income: دخل الشهر التالي (للتنبؤ بالدخل)
        row["Next_Month_Income"] = float(incomes[i + 1]) if i + 1 < len(incomes) else np.nan

monthly_df = pd.DataFrame(monthly_rows)
projects_df = pd.DataFrame(project_rows)

# ─────────────────────────────────────────────────────────────
# معايرة: نجعل مجموع قيم مشاريع كل فريلانسر يساوي مجموع دخله.
# بدونها يصبح مجموع المشاريع أكبر بكثير من الدخل المسجَّل — تناقض.
# ─────────────────────────────────────────────────────────────
for fid in projects_df["Freelancer_ID"].unique():
    total_income   = monthly_df.loc[monthly_df["Freelancer_ID"]==fid, "Income"].sum()
    total_projects = projects_df.loc[projects_df["Freelancer_ID"]==fid, "Project_Value"].sum()
    if total_projects > 0:
        scale = total_income / total_projects
        mask = projects_df["Freelancer_ID"] == fid
        projects_df.loc[mask, "Project_Value"] = (
            projects_df.loc[mask, "Project_Value"] * scale).round(0)

# سعر الساعة = المعدّل السائد لكل تخصّص (خاصية سوقية، لا مشتقّة من المشروع).
# لا نحسبه بقسمة القيمة على الساعات، وإلا صار النموذج يستنتج السعر بالضرب — تسريب.
rate_by_spec = (projects_df["Project_Value"] / projects_df["Estimated_Hours"]) \
                 .groupby(projects_df["Specialty"]).transform("median").round(0)
projects_df["Hourly_Rate"] = rate_by_spec

# إضافة Suggested_Price للمشاريع (الهدف = نفس قيمة المشروع كأساس تدريب)
projects_df["Suggested_Price"] = projects_df["Project_Value"]

# ---------------------------------------------------------------------------
# حفظ الملفات
# ---------------------------------------------------------------------------
with pd.ExcelWriter("mustaqil_dataset_v2.xlsx", engine="openpyxl") as writer:
    monthly_df.to_excel(writer, sheet_name="Monthly_Data", index=False)
    projects_df.to_excel(writer, sheet_name="Projects_Data", index=False)

monthly_df.to_csv("monthly_data_v2.csv", index=False, encoding="utf-8-sig")
projects_df.to_csv("projects_data_v2.csv", index=False, encoding="utf-8-sig")

print("✅ تم توليد البيانات")
print(f"   • الجدول الشهري : {len(monthly_df)} صف ({N_FREELANCERS} فريلانسر × {N_MONTHS} شهر)")
print(f"   • جدول المشاريع : {len(projects_df)} مشروع")
print(f"   • نسبة أشهر الجفاف: {(monthly_df['Dry_Month_Label']=='Yes').mean()*100:.1f}%")
print("\nعينة من الجدول الشهري:")
print(monthly_df[["Freelancer_ID","Name","Specialty","Month","Income","Number_of_Projects","Dry_Month_Label"]].head(8).to_string(index=False))
print("\nعينة من جدول المشاريع:")
print(projects_df.head(6).to_string(index=False))
