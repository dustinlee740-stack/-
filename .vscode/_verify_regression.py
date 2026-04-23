import numpy as np
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from statsmodels.stats.outliers_influence import variance_inflation_factor

np.random.seed(42)
n = 200
X1 = np.random.randn(n)
X2 = np.random.randn(n)
X3 = np.random.randn(n)
X4 = np.random.randn(n)
X5 = X1 * 0.9 + np.random.randn(n) * 0.3
noise = np.random.randn(n) * 0.5
y = 3 + 2*X1 - 1.5*X2 + 0.7*X3 + noise

X = np.column_stack([X1, X2, X3, X4, X5])
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

passed = 0
total = 6

# === 검증 1: Adjusted R2 수식 ===
print("=== 검증 1: Adjusted R^2 수식 ===")
lr = LinearRegression().fit(X_train, y_train)
r2 = lr.score(X_train, y_train)
n_t, p = X_train.shape
adj_r2_manual = 1 - (1 - r2) * (n_t - 1) / (n_t - p - 1)
ols = sm.OLS(y_train, sm.add_constant(X_train)).fit()
match1 = np.isclose(adj_r2_manual, ols.rsquared_adj)
print(f"  수동 계산 Adj R^2:     {adj_r2_manual:.6f}")
print(f"  statsmodels Adj R^2:   {ols.rsquared_adj:.6f}")
print(f"  PASS: {match1}")
if match1: passed += 1

# === 검증 2: VIF ===
print("\n=== 검증 2: VIF 다중공선성 확인 ===")
X_sm = sm.add_constant(X_train)
vifs = [variance_inflation_factor(X_sm, i+1) for i in range(5)]
x1_high = vifs[0] > 10
x5_high = vifs[4] > 10
x234_low = all(v < 5 for v in vifs[1:4])
match2 = x1_high and x5_high and x234_low
print(f"  X1 VIF={vifs[0]:.2f} (>10? {x1_high})")
print(f"  X5 VIF={vifs[4]:.2f} (>10? {x5_high})")
print(f"  X2,X3,X4 VIF < 5? {x234_low}")
print(f"  PASS: {match2}")
if match2: passed += 1

# === 검증 3: Forward Selection ===
print("\n=== 검증 3: Forward Selection AIC 검증 ===")
m4var = sm.OLS(y_train, sm.add_constant(X_train[:, [4,1,2,0]])).fit()
m5var = sm.OLS(y_train, sm.add_constant(X_train)).fit()
match3 = m5var.aic >= m4var.aic  # X4 추가하면 AIC가 개선 안 됨
print(f"  4변수(X5,X2,X3,X1) AIC: {m4var.aic:.2f}")
print(f"  5변수(전체)          AIC: {m5var.aic:.2f}")
print(f"  X4 추가 시 AIC 악화? {match3}")
print(f"  PASS: {match3}")
if match3: passed += 1

# === 검증 4: Backward Elimination ===
print("\n=== 검증 4: Backward Elimination 검증 ===")
full = sm.OLS(y_train, sm.add_constant(X_train)).fit()
x4_pval = full.pvalues[4]  # X4 p-value (1-indexed after const)
x4_highest = x4_pval == full.pvalues[1:].max()

m_no4 = sm.OLS(y_train, sm.add_constant(X_train[:, [0,1,2,4]])).fit()
x5_pval_after = m_no4.pvalues[4]  # X5 p-value
x5_highest = x5_pval_after == m_no4.pvalues[1:].max()
x5_over_05 = x5_pval_after > 0.05

m_final = sm.OLS(y_train, sm.add_constant(X_train[:, [0,1,2]])).fit()
all_sig = all(m_final.pvalues < 0.05)

match4 = x4_highest and x5_highest and x5_over_05 and all_sig
print(f"  전체모델에서 X4 p-value={x4_pval:.4f} (최대? {x4_highest})")
print(f"  X4 제거 후 X5 p-value={x5_pval_after:.4f} (>0.05? {x5_over_05})")
print(f"  최종모델(X1,X2,X3) 모든 p-value < 0.05? {all_sig}")
print(f"  PASS: {match4}")
if match4: passed += 1

# === 검증 5: 최종 계수 vs 실제 생성 계수 ===
print("\n=== 검증 5: 추정 계수 vs 실제 생성 계수 ===")
true_vals = [3.0, 2.0, -1.5, 0.7]
ci = m_final.conf_int()
all_in_ci = True
for i, (name, true_val) in enumerate(zip(['intercept','X1','X2','X3'], true_vals)):
    est = m_final.params[i]
    lo, hi = ci[i]
    in_ci = lo <= true_val <= hi
    if not in_ci: all_in_ci = False
    print(f"  {name}: true={true_val}, est={est:.4f}, 95%CI=[{lo:.4f},{hi:.4f}], 포함={in_ci}")
match5 = all_in_ci
print(f"  PASS: {match5}")
if match5: passed += 1

# === 검증 6: sklearn vs statsmodels 일치 ===
print("\n=== 검증 6: sklearn vs statsmodels 계수 일치 ===")
lr_final = LinearRegression().fit(X_train[:, [0,1,2]], y_train)
int_match = np.isclose(lr_final.intercept_, m_final.params[0])
coef_match = np.allclose(lr_final.coef_, m_final.params[1:])
match6 = int_match and coef_match
print(f"  sklearn  intercept={lr_final.intercept_:.6f}, coefs={lr_final.coef_}")
print(f"  statsmod intercept={m_final.params[0]:.6f}, coefs={m_final.params[1:]}")
print(f"  intercept 일치: {int_match}, coefs 일치: {coef_match}")
print(f"  PASS: {match6}")
if match6: passed += 1

print(f"\n{'='*50}")
print(f"검증 결과: {passed}/{total} PASSED")
if passed == total:
    print("*** 모든 검증 통과 — 코드 정확성 증명 완료 ***")
else:
    print("!!! 일부 검증 실패 — 코드 점검 필요 !!!")
