# -*- coding: utf-8 -*-
"""
اشتقاق أوزان مؤشر الجدارة من البيانات بدل الاجتهاد.

الفكرة: نعرّف "التعثّر المالي" = الفريلانسر عجز عن تغطية مصاريفه من دخله
(دخل الشهر < المصاريف) — هذا الحدث الحقيقي الذي يخشاه البنك.
ثم ندرّب نموذجاً يتعلّم أي المحاور الأربعة يتنبأ بهذا التعثّر،
ونستخدم أهمية كل ميزة (feature importance) كوزن.
"""
import pandas as pd, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

monthly = pd.read_excel("mustaqil_dataset_v2.xlsx", sheet_name="Monthly_Data")
projects = pd.read_excel("mustaqil_dataset_v2.xlsx", sheet_name="Projects_Data")

m = monthly.sort_values(["Freelancer_ID","Year","Month"]).copy()

# ── تعريف الهدف: الضائقة المالية في الشهر القادم ──
# ضائقة = دخل الشهر القادم لا يغطّي مصاريفه الأساسية.
# ملاحظة منهجية: لا نُدخل صندوق الطوارئ في التعريف، وإلا صار النموذج
# يتعلّم شيئاً وضعناه بأيدينا (تسريب بيانات).
m["next_income"]   = m.groupby("Freelancer_ID")["Income"].shift(-1)
m["next_expenses"] = m.groupby("Freelancer_ID")["Total_Expenses"].shift(-1)
m["default"] = (m["next_income"] < m["next_expenses"]).astype(int)

# ── بناء المحاور الأربعة كميزات (بنفس منطق التطبيق) ──
def build_features(g):
    g = g.copy()
    # 1) استقرار الدخل: معكوس معامل الاختلاف على نافذة 6 أشهر
    roll_mean = g["Income"].rolling(6, min_periods=2).mean()
    roll_std  = g["Income"].rolling(6, min_periods=2).std()
    cv = roll_std / roll_mean.clip(lower=1)
    g["f_stability"] = (1 - cv.clip(0,1)).fillna(0)
    # 2) تغطية صندوق الطوارئ بالأشهر (مقصوصة عند 6)
    g["f_emergency"] = (g["Emergency_Fund"] / g["Total_Expenses"].clip(lower=1)).clip(0,6) / 6
    # 3) انتظام التحصيل: معكوس متوسط التأخير
    g["f_collection"] = 1 - (g["Payment_Delay_Days"].rolling(6,min_periods=1).mean().clip(0,45) / 45)
    return g

m = m.groupby("Freelancer_ID", group_keys=False)[m.columns.tolist()].apply(build_features)

# 4) تنوّع العملاء: ثابت لكل فريلانسر (من جدول المشاريع) — HHI
div = {}
for fid, p in projects.groupby("Freelancer_ID"):
    share = p.groupby("Client_Type")["Project_Value"].sum()
    share = share / share.sum()
    hhi = float((share**2).sum())
    vol = min(1.0, len(p)/20)
    div[fid] = max(0.0,(1-hhi)/0.75)*0.7 + vol*0.3
m["f_diversity"] = m["Freelancer_ID"].map(div).fillna(0)

feats = ["f_stability","f_emergency","f_diversity","f_collection"]
data = m.dropna(subset=["default"]+feats)

print("="*62)
print("اشتقاق الأوزان من البيانات")
print("="*62)
print(f"عدد الصفوف الصالحة : {len(data)}")
print(f"نسبة حالات التعثّر  : {data['default'].mean()*100:.1f}%")

X, y = data[feats], data["default"]
Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.25,random_state=1,stratify=y)
clf = RandomForestClassifier(n_estimators=300, random_state=1, class_weight="balanced")
clf.fit(Xtr,ytr)

acc = accuracy_score(yte, clf.predict(Xte))
auc = roc_auc_score(yte, clf.predict_proba(Xte)[:,1])
print(f"\nدقة نموذج التعثّر  : {acc*100:.1f}%")
print(f"AUC               : {auc:.3f}   (0.5=عشوائي، 1=مثالي)")

# ── الأهمية → الأوزان ──
imp = pd.Series(clf.feature_importances_, index=feats).sort_values(ascending=False)
weights = (imp / imp.sum() * 100)

names_ar = {"f_stability":"استقرار الدخل", "f_emergency":"صندوق الطوارئ",
            "f_diversity":"تنوّع العملاء", "f_collection":"انتظام التحصيل"}

print("\n" + "="*62)
print("الأوزان المشتقّة من البيانات (أهمية كل محور في التنبؤ بالتعثّر)")
print("="*62)
for f in imp.index:
    print(f"  {names_ar[f]:16s} : {weights[f]:5.1f} نقطة   (أهمية خام {imp[f]:.3f})")
print(f"  {'المجموع':16s} : {weights.sum():5.1f}")

# نقرّبها لأرقام مستديرة تجمع 100
rounded = (weights/5).round()*5
diff = 100 - rounded.sum()
rounded.iloc[0] += diff   # نضبط الفرق على الأثقل
print("\nبعد التقريب لأرقام عملية:")
for f in imp.index:
    print(f"  {names_ar[f]:16s} : {rounded[f]:.0f} نقطة")
print(f"  {'المجموع':16s} : {rounded.sum():.0f}")

print("\n✅ الأوزان الآن مشتقّة من البيانات، لا من الاجتهاد")
