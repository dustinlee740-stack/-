import matplotlib
matplotlib.use('Agg')  # 비대화형 백엔드 (파일 저장 전용, 블로킹 방지)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression

# 한글 폰트 설정 (Windows)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy.stats import shapiro
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import OLSInfluence, variance_inflation_factor

# =============================================
# Phase 1: 데이터 생성 & 기본 다중회귀 모델
# =============================================

np.random.seed(42)
n = 200

X1 = np.random.randn(n)                  # 유의미 변수
X2 = np.random.randn(n)                  # 유의미 변수
X3 = np.random.randn(n)                  # 유의미 변수
X4 = np.random.randn(n)                  # 노이즈 변수 (무관)
X5 = X1 * 0.9 + np.random.randn(n) * 0.3  # X1과 높은 상관 (다중공선성)

noise = np.random.randn(n) * 0.5
y = 3 + 2 * X1 - 1.5 * X2 + 0.7 * X3 + noise

# pandas DataFrame 구성
df = pd.DataFrame({
    'X1': X1, 'X2': X2, 'X3': X3, 'X4': X4, 'X5': X5, 'y': y
})

print("=== 데이터 기본 정보 ===")
print(f"데이터 크기: {df.shape}")
print(f"\n변수 간 상관행렬:")
print(df.corr().round(3))

# 독립변수 / 종속변수 분리
feature_cols = ['X1', 'X2', 'X3', 'X4', 'X5']
X = df[feature_cols].values
y_arr = df['y'].values

# train/test 분리
X_train, X_test, y_train, y_test = train_test_split(
    X, y_arr, test_size=0.25, random_state=42
)

# sklearn 다중회귀 (전체 변수 투입)
lin_reg = LinearRegression()
lin_reg.fit(X_train, y_train)

y_train_pred = lin_reg.predict(X_train)
y_test_pred = lin_reg.predict(X_test)

# =============================================
# Phase 2: 모델 평가 지표
# =============================================

train_r2 = lin_reg.score(X_train, y_train)
test_r2 = lin_reg.score(X_test, y_test)

# Adjusted R² 계산
n_train = X_train.shape[0]
p = X_train.shape[1]
train_adj_r2 = 1 - (1 - train_r2) * (n_train - 1) / (n_train - p - 1)

n_test = X_test.shape[0]
test_adj_r2 = 1 - (1 - test_r2) * (n_test - 1) / (n_test - p - 1)

train_mse = mean_squared_error(y_train, y_train_pred)
test_mse = mean_squared_error(y_test, y_test_pred)
train_rmse = np.sqrt(train_mse)
test_rmse = np.sqrt(test_mse)
train_mae = mean_absolute_error(y_train, y_train_pred)
test_mae = mean_absolute_error(y_test, y_test_pred)

print("\n=== 다중회귀 결과 (전체 변수 투입) ===")
print(f"절편(intercept): {lin_reg.intercept_:.4f}")
for i, col in enumerate(feature_cols):
    print(f"  {col} 계수: {lin_reg.coef_[i]:.4f}")
print(f"\n훈련 R²: {train_r2:.4f},  Adjusted R²: {train_adj_r2:.4f}")
print(f"테스트 R²: {test_r2:.4f},  Adjusted R²: {test_adj_r2:.4f}")
print(f"훈련 MSE: {train_mse:.4f},  RMSE: {train_rmse:.4f},  MAE: {train_mae:.4f}")
print(f"테스트 MSE: {test_mse:.4f},  RMSE: {test_rmse:.4f},  MAE: {test_mae:.4f}")

# =============================================
# Phase 3: 회귀계수 검정 (statsmodels OLS)
# =============================================

X_train_sm = sm.add_constant(X_train)
ols_full = sm.OLS(y_train, X_train_sm).fit()

print("\n=== 회귀계수 검정 결과 (전체 변수) ===")
coef_names = ['const'] + feature_cols
for name, coef, pval in zip(coef_names, ols_full.params, ols_full.pvalues):
    sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else ""
    print(f"  {name:>6}: coef={coef:>8.4f}, p-value={pval:.4f} {sig}")

print(f"\n95% 신뢰구간:")
ci = ols_full.conf_int()
for name, (lo, hi) in zip(coef_names, ci):
    print(f"  {name:>6}: [{lo:.4f}, {hi:.4f}]")

print("\n=== OLS Summary ===")
print(ols_full.summary())

# =============================================
# Phase 4: 다중공선성 확인 (VIF)
# =============================================

print("\n=== 다중공선성 확인 (VIF) ===")
vif_data = pd.DataFrame()
vif_data['Variable'] = feature_cols
vif_data['VIF'] = [
    variance_inflation_factor(X_train_sm, i + 1)  # +1: 상수항 skip
    for i in range(len(feature_cols))
]
print(vif_data.to_string(index=False))

for _, row in vif_data.iterrows():
    if row['VIF'] > 10:
        print(f"  ⚠ 경고: {row['Variable']}의 VIF={row['VIF']:.2f} → 다중공선성 의심!")

# VIF 막대그래프
plt.figure(figsize=(8, 5))
colors = ['red' if v > 10 else 'steelblue' for v in vif_data['VIF']]
plt.bar(vif_data['Variable'], vif_data['VIF'], color=colors, alpha=0.8)
plt.axhline(y=10, color='red', linestyle='--', linewidth=1.5, label='VIF=10 기준선')
plt.xlabel('Variable')
plt.ylabel('VIF')
plt.title('Variance Inflation Factor (VIF)')
plt.legend()
plt.grid(alpha=0.3)

vif_path = 'd:/da/.vscode/vif_plot.png'
plt.savefig(vif_path, dpi=150, bbox_inches='tight')
print(f'\nSaved VIF plot to {vif_path}')
plt.show()

# =============================================
# Phase 5: 단계적 변수 선택 (Stepwise)
# =============================================

# ----- 전진선택법 (Forward Selection, AIC 기반) -----
print("\n=== 전진선택법 (Forward Selection, AIC 기반) ===")

remaining = list(range(len(feature_cols)))
selected_fw = []
current_aic = None

for step in range(len(feature_cols)):
    best_aic = np.inf
    best_var = None

    for var_idx in remaining:
        candidate = selected_fw + [var_idx]
        X_cand = sm.add_constant(X_train[:, candidate])
        model_cand = sm.OLS(y_train, X_cand).fit()
        if model_cand.aic < best_aic:
            best_aic = model_cand.aic
            best_var = var_idx

    if current_aic is not None and best_aic >= current_aic:
        print(f"  Step {step + 1}: AIC 개선 없음 → 종료")
        break

    selected_fw.append(best_var)
    remaining.remove(best_var)
    current_aic = best_aic
    print(f"  Step {step + 1}: + {feature_cols[best_var]:>2} 추가 → AIC={best_aic:.2f}")

fw_selected_names = [feature_cols[i] for i in selected_fw]
print(f"\n전진선택 최종 변수: {fw_selected_names}")

# ----- 후진제거법 (Backward Elimination, p-value 기반) -----
print("\n=== 후진제거법 (Backward Elimination, p-value 기반) ===")

selected_bw = list(range(len(feature_cols)))
alpha_threshold = 0.05
step = 0

while True:
    X_bw = sm.add_constant(X_train[:, selected_bw])
    model_bw = sm.OLS(y_train, X_bw).fit()
    # p-values: index 0 = const, 나머지 = 변수
    pvalues = model_bw.pvalues[1:]  # 상수항 제외
    max_pval = pvalues.max()
    max_idx_in_selected = pvalues.argmax()

    if max_pval > alpha_threshold:
        removed_var = selected_bw[max_idx_in_selected]
        step += 1
        print(
            f"  Step {step}: - {feature_cols[removed_var]:>2} 제거 "
            f"(p-value={max_pval:.4f})"
        )
        selected_bw.pop(max_idx_in_selected)
    else:
        print(f"  Step {step + 1}: 모든 변수 p-value < {alpha_threshold} → 종료")
        break

bw_selected_names = [feature_cols[i] for i in selected_bw]
print(f"\n후진제거 최종 변수: {bw_selected_names}")

# ----- 최종 모델 (후진제거법 결과 사용) -----
print("\n=== 최종 선택 모델 (후진제거법 결과) ===")
X_train_final = sm.add_constant(X_train[:, selected_bw])
X_test_final = sm.add_constant(X_test[:, selected_bw])
ols_final = sm.OLS(y_train, X_train_final).fit()

final_names = ['const'] + bw_selected_names
for name, coef, pval in zip(final_names, ols_final.params, ols_final.pvalues):
    sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else ""
    print(f"  {name:>6}: coef={coef:>8.4f}, p-value={pval:.6f} {sig}")

print(f"\n최종 모델 AIC: {ols_final.aic:.2f}")
print(f"최종 모델 R²: {ols_final.rsquared:.4f}")
print(f"최종 모델 Adjusted R²: {ols_final.rsquared_adj:.4f}")
print(ols_final.summary())

# 최종 모델로 예측
y_train_final_pred = ols_final.predict(X_train_final)
y_test_final_pred = ols_final.predict(X_test_final)

# =============================================
# Phase 6: 잔차 분석 & 정규성 / 등분산성 검정
# =============================================

train_residuals = y_train - y_train_final_pred
test_residuals = y_test - y_test_final_pred

print("\n=== 잔차 분석 (최종 모델) ===")
print(f"훈련 잔차 평균: {train_residuals.mean():.6f}")
print(f"테스트 잔차 평균: {test_residuals.mean():.6f}")
print(f"훈련 잔차 표준편차: {train_residuals.std():.4f}")
print(f"테스트 잔차 표준편차: {test_residuals.std():.4f}")

# Shapiro-Wilk 정규성 검정
train_shapiro_stat, train_shapiro_p = shapiro(train_residuals)
test_shapiro_stat, test_shapiro_p = shapiro(test_residuals)

print("\n=== 잔차 정규성 검정 (Shapiro-Wilk) ===")
print(f"훈련: statistic={train_shapiro_stat:.4f}, p-value={train_shapiro_p:.4f}")
print(f"테스트: statistic={test_shapiro_stat:.4f}, p-value={test_shapiro_p:.4f}")
if train_shapiro_p >= 0.05:
    print("해석: 훈련 잔차의 정규성 가정을 크게 위반하지 않음")
else:
    print("해석: 훈련 잔차가 정규분포를 따르지 않을 수 있음")

# Q-Q Plot
fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
sm.qqplot(train_residuals, line='45', fit=True, ax=ax)
ax.set_title('Q-Q Plot of Train Residuals (Final Model)')
ax.grid(alpha=0.3)

qq_path = 'd:/da/.vscode/qqplot_multi_residuals.png'
plt.savefig(qq_path, dpi=150, bbox_inches='tight')
print(f'Saved Q-Q plot to {qq_path}')
plt.show()

# Breusch-Pagan 등분산성 검정
bp_lm_stat, bp_lm_pvalue, bp_f_stat, bp_f_pvalue = het_breuschpagan(
    ols_final.resid, X_train_final
)

print("\n=== 등분산성 검정 (Breusch-Pagan) ===")
print(f"LM statistic: {bp_lm_stat:.4f}")
print(f"LM p-value: {bp_lm_pvalue:.4f}")
print(f"F statistic: {bp_f_stat:.4f}")
print(f"F p-value: {bp_f_pvalue:.4f}")
if bp_lm_pvalue < 0.05:
    print("해석: 등분산이라고 보기 어려울 수 있음 (이분산성 의심)")
else:
    print("해석: 등분산 가정을 크게 해치지 않는 것으로 볼 수 있음")

# =============================================
# Phase 7: 이상치 / 영향점 확인
# =============================================

influence = OLSInfluence(ols_final)

studentized_residuals = influence.resid_studentized_internal
leverage = influence.hat_matrix_diag
cooks_d = influence.cooks_distance[0]

n_final = X_train_final.shape[0]
param_count = X_train_final.shape[1]
leverage_threshold = 2 * param_count / n_final
cooks_threshold = 4 / n_final

print("\n=== 이상치 / 영향점 확인 ===")
print(f"leverage 기준값: {leverage_threshold:.4f}")
print(f"Cook's distance 기준값: {cooks_threshold:.4f}")

outlier_idx = np.where(
    (np.abs(studentized_residuals) > 2) |
    (leverage > leverage_threshold) |
    (cooks_d > cooks_threshold)
)[0]

print(f"의심 관측치 개수: {len(outlier_idx)}")
for idx in outlier_idx:
    print(
        f"  index={idx}, "
        f"studentized_residual={studentized_residuals[idx]:.3f}, "
        f"leverage={leverage[idx]:.4f}, "
        f"cooks_d={cooks_d[idx]:.4f}"
    )

# =============================================
# Phase 8: 시각화
# =============================================

# ----- 실제값 vs 예측값 산점도 -----
plt.figure(figsize=(8, 6))
plt.scatter(y_train, y_train_final_pred, alpha=0.6, label='Train')
plt.scatter(y_test, y_test_final_pred, alpha=0.8, label='Test')
min_val = min(y_arr.min(), y_train_final_pred.min(), y_test_final_pred.min())
max_val = max(y_arr.max(), y_train_final_pred.max(), y_test_final_pred.max())
plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect fit')

plt.xlabel('Actual y')
plt.ylabel('Predicted y')
plt.title('Actual vs Predicted (Final Model)')
plt.legend()
plt.grid(alpha=0.3)

actual_pred_path = 'd:/da/.vscode/actual_vs_predicted.png'
plt.savefig(actual_pred_path, dpi=150, bbox_inches='tight')
print(f'\nSaved actual vs predicted plot to {actual_pred_path}')
plt.show()

# ----- 잔차 산점도 -----
plt.figure(figsize=(8, 6))
plt.scatter(y_train_final_pred, train_residuals, alpha=0.6, label='Train residuals')
plt.scatter(y_test_final_pred, test_residuals, alpha=0.8, label='Test residuals')
plt.axhline(y=0, color='red', linestyle='--', linewidth=2)

plt.xlabel('Predicted y')
plt.ylabel('Residuals')
plt.title('Residual Plot (Final Model)')
plt.legend()
plt.grid(alpha=0.3)

resid_path = 'd:/da/.vscode/multi_residual_plot.png'
plt.savefig(resid_path, dpi=150, bbox_inches='tight')
print(f'Saved residual plot to {resid_path}')
plt.show()

# ----- 잔차 히스토그램 -----
plt.figure(figsize=(8, 6))
plt.hist(train_residuals, bins=20, alpha=0.6, label='Train residuals')
plt.hist(test_residuals, bins=20, alpha=0.8, label='Test residuals')

plt.xlabel('Residuals')
plt.ylabel('Frequency')
plt.title('Residual Histogram (Final Model)')
plt.legend()
plt.grid(alpha=0.3)

hist_path = 'd:/da/.vscode/multi_residual_histogram.png'
plt.savefig(hist_path, dpi=150, bbox_inches='tight')
print(f'Saved residual histogram to {hist_path}')
plt.show()

# ----- 회귀계수 막대그래프 -----
plt.figure(figsize=(8, 5))
coef_vals = ols_final.params[1:]  # 상수항 제외
coef_colors = ['steelblue' if c >= 0 else 'salmon' for c in coef_vals]
plt.bar(bw_selected_names, coef_vals, color=coef_colors, alpha=0.8)
plt.axhline(y=0, color='black', linewidth=0.8)

plt.xlabel('Variable')
plt.ylabel('Coefficient')
plt.title('Regression Coefficients (Final Model)')
plt.grid(alpha=0.3)

coef_path = 'd:/da/.vscode/coefficients_plot.png'
plt.savefig(coef_path, dpi=150, bbox_inches='tight')
print(f'Saved coefficients plot to {coef_path}')
plt.show()

# ----- Cook's Distance 막대그래프 -----
plt.figure(figsize=(10, 5))
plt.bar(range(n_final), cooks_d, alpha=0.7)
plt.axhline(y=cooks_threshold, color='red', linestyle='--', linewidth=1.5,
            label=f"threshold={cooks_threshold:.4f}")

plt.xlabel('Observation Index')
plt.ylabel("Cook's Distance")
plt.title("Cook's Distance Plot (Final Model)")
plt.legend()
plt.grid(alpha=0.3)

cooks_path = 'd:/da/.vscode/multi_cooks_distance_plot.png'
plt.savefig(cooks_path, dpi=150, bbox_inches='tight')
print(f"Saved Cook's distance plot to {cooks_path}")
plt.show()

print("\n=== 전체 분석 완료 ===")
