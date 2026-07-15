# -*- coding: utf-8 -*-
"""
تشغيل النماذج الأربعة ورؤية نتائجها في الترمنال.
الطريقة:  python run_models.py
"""
import pandas as pd, numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, r2_score, mean_absolute_error,
                             roc_auc_score, classification_report)

print("جارٍ تحميل البيانات...")
monthly = pd.read_excel("mustaqil_dataset_v2.xlsx", sheet_name="Monthly_Data")
projects = pd.read_excel("mustaqil_dataset_v2.xlsx", sheet_name="Projects_Data")

m = monthly.sort_values(["Freelancer_ID","Year","Month"]).copy()
m["dry"] = (m["Dry_Month_Label"]=="Yes").astype(int)
m["Income_lag1"]  = m.groupby("Freelancer_ID")["Income"].shift(1)
m["Income_roll3"] = m.groupby("Freelancer_ID")["Income"].transform(
    lambda x: x.rolling(3,min_periods=1).mean())
m = m.dropna(subset=["Income_lag1"])

# ═══ النموذج 1: شهر الجفاف ═══
print("\n" + "="*58)
print("النموذج 1: التنبؤ بشهر الجفاف (تصنيف)")
print("="*58)
f1 = ["Income_lag1","Income_roll3","Number_of_Projects","Total_Expenses","Month","Payment_Delay_Days"]
Xtr,Xte,ytr,yte = train_test_split(m[f1], m["dry"], test_size=0.25, random_state=1, stratify=m["dry"])
clf = RandomForestClassifier(n_estimators=150, random_state=1, class_weight="balanced").fit(Xtr,ytr)
print(f"الدقة: {accuracy_score(yte, clf.predict(Xte))*100:.1f}%\n")
print(classification_report(yte, clf.predict(Xte), target_names=["شهر عادي","شهر جفاف"]))

# ═══ النموذج 2: الدخل القادم ═══
print("="*58)
print("النموذج 2: التنبؤ بدخل الشهر القادم (انحدار)")
print("="*58)
m2 = m.dropna(subset=["Next_Month_Income"]).copy()
m2["next_month"] = (m2["Month"] % 12) + 1
m2["sin_m"] = np.sin(2*np.pi*m2["next_month"]/12)
m2["cos_m"] = np.cos(2*np.pi*m2["next_month"]/12)
m2["fl_mean"] = m2.groupby("Freelancer_ID")["Income"].transform("mean")
m2["roll6"] = m2.groupby("Freelancer_ID")["Income"].transform(lambda x: x.rolling(6,min_periods=1).mean())
f2 = ["Income","Income_lag1","Income_roll3","roll6","fl_mean","Number_of_Projects","next_month","sin_m","cos_m"]
Xtr,Xte,ytr,yte = train_test_split(m2[f2], m2["Next_Month_Income"], test_size=0.25, random_state=1)
reg = RandomForestRegressor(n_estimators=200, random_state=1).fit(Xtr,ytr)
pred = reg.predict(Xte)
print(f"R²: {r2_score(yte,pred):.3f}")
print(f"متوسط الخطأ (MAE): {mean_absolute_error(yte,pred):,.0f} ر.س")
print("ملاحظة: R² منخفض لأن الدخل متقلّب بطبيعته — نعرضه كما هو بلا تجميل.")

# ═══ النموذج 3: التسعير ═══
print("\n" + "="*58)
print("النموذج 3: اقتراح سعر المشروع (انحدار)")
print("="*58)
p = pd.get_dummies(projects, columns=["Specialty","Client_Type"])
drop = ["Project_ID","Freelancer_ID","Project_Value","Suggested_Price",
        "Payment_Delay_Days","Late_Payment","Defaulted"]
f3 = [c for c in p.columns if c not in drop]
Xtr,Xte,ytr,yte = train_test_split(p[f3], p["Suggested_Price"], test_size=0.25, random_state=1)
reg2 = RandomForestRegressor(n_estimators=200, random_state=1).fit(Xtr,ytr)
pred = reg2.predict(Xte)
print(f"R²: {r2_score(yte,pred):.3f}")
print(f"متوسط الخطأ (MAE): {mean_absolute_error(yte,pred):,.0f} ر.س")

# ═══ النموذج 4: كاشف العميل الخطر ═══
print("\n" + "="*58)
print("النموذج 4: كاشف العميل الخطر (تصنيف)")
print("="*58)
pc = pd.get_dummies(projects, columns=["Client_Type","Specialty"])
f4 = [c for c in pc.columns if c.startswith(("Client_Type_","Specialty_"))] + \
     ["Project_Value","Project_Duration_Days","Estimated_Hours","Complexity"]
Xtr,Xte,ytr,yte = train_test_split(pc[f4], pc["Late_Payment"], test_size=0.25,
                                   random_state=1, stratify=pc["Late_Payment"])
clf4 = RandomForestClassifier(n_estimators=200, random_state=1, class_weight="balanced").fit(Xtr,ytr)
print(f"الدقة: {accuracy_score(yte, clf4.predict(Xte))*100:.1f}%")
print(f"AUC: {roc_auc_score(yte, clf4.predict_proba(Xte)[:,1]):.3f}\n")
print("سلوك السداد الفعلي حسب نوع العميل:")
beh = projects.groupby("Client_Type").agg(
    متوسط_التأخير=("Payment_Delay_Days","mean"),
    نسبة_التأخر=("Late_Payment","mean"),
    نسبة_التعثر=("Defaulted","mean")).round(3)
print(beh.to_string())

print("\n✅ انتهى تشغيل النماذج الأربعة")
