import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy.stats import shapiro
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import OLSInfluence

X = 2 * np.random.rand(100, 1)
y = 4 + 3 * X + np.random.randn(100, 1)

lin_reg = LinearRegression()
X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42)

lin_reg.fit(X_train, y_train)

# 예측값 생성
y_train_pred = lin_reg.predict(X_train)
y_test_pred = lin_reg.predict(X_test)

# 기존 지표
train_r2 = lin_reg.score(X_train, y_train)
test_r2 = lin_reg.score(X_test, y_test)

# 오차 지표
train_mse = mean_squared_error(y_train, y_train_pred)
test_mse = mean_squared_error(y_test, y_test_pred)

train_rmse = np.sqrt(train_mse)
test_rmse = np.sqrt(test_mse)

train_mae = mean_absolute_error(y_train, y_train_pred)
test_mae = mean_absolute_error(y_test, y_test_pred)

print("=== 선형회귀 결과 ===")
print(f"절편(intercept): {lin_reg.intercept_[0]}")
print(f"기울기(coef): {lin_reg.coef_[0][0]}")
print(f"훈련 데이터 R^2: {train_r2}")
print(f"테스트 데이터 R^2: {test_r2}")
print(f"훈련 데이터 MSE: {train_mse}")
print(f"테스트 데이터 MSE: {test_mse}")
print(f"훈련 데이터 RMSE: {train_rmse}")
print(f"테스트 데이터 RMSE: {test_rmse}")
print(f"훈련 데이터 MAE: {train_mae}")
print(f"테스트 데이터 MAE: {test_mae}")

# -----------------------------
# 3번: 회귀계수 검정(statsmodels)
# -----------------------------

# statsmodels는 절편을 자동 추가하지 않으므로 상수항(const) 추가
X_train_sm = sm.add_constant(X_train)

# y는 1차원으로 넣는 것이 깔끔함
ols_model = sm.OLS(y_train.ravel(), X_train_sm).fit()

print("\n=== 회귀계수 검정 결과 ===")
print("계수(절편, 기울기):")
print(ols_model.params)

print("\np-value:")
print(ols_model.pvalues)

print("\n95% 신뢰구간:")
print(ols_model.conf_int())

print("\n=== OLS Summary ===")
print(ols_model.summary())

# -----------------------------
# 4번: 잔차 분석
# -----------------------------

# 잔차 = 실제값 - 예측값
train_residuals = y_train - y_train_pred
test_residuals = y_test - y_test_pred

print("\n=== 잔차 분석 ===")
print(f"훈련 데이터 잔차 평균: {train_residuals.mean()}")
print(f"테스트 데이터 잔차 평균: {test_residuals.mean()}")
print(f"훈련 데이터 잔차 표준편차: {train_residuals.std()}")
print(f"테스트 데이터 잔차 표준편차: {test_residuals.std()}")

# x, y 간 관계성 확인을 위한 관계성(산점도, 회귀선)을 확인할 때 사용
intercept = lin_reg.intercept_[0]
coef = lin_reg.coef_[0][0]
train_score = lin_reg.score(X_train, y_train)
test_score = lin_reg.score(X_test, y_test)

plt.figure(figsize=(8, 6))
plt.scatter(X_train, y_train, color='blue', alpha=0.6, label='Train')
plt.scatter(X_test, y_test, color='orange', alpha=0.8, label='Test')

X_line = np.linspace(X.min(), X.max(), 100).reshape(-1, 1)
y_line = intercept + coef * X_line
plt.plot(X_line, y_line, color='red', linewidth=2, label='Regression line')

plt.xlabel('X')
plt.ylabel('y')
plt.title(
    f'Linear Regression: intercept={intercept:.3f}, coef={coef:.3f}\n'
    f'Train R^2={train_score:.3f}, Test R^2={test_score:.3f}'
)
plt.legend()
plt.grid(alpha=0.3)

output_path = 'd:/da/.vscode/regression_result.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print('Saved plot to', output_path)
plt.show()

# -----------------------------
# 잔차 산점도
# 예측값 대비 잔차가 0 근처에 고르게 퍼지는지 확인
# -----------------------------
plt.figure(figsize=(8, 6))
plt.scatter(y_train_pred, train_residuals, alpha=0.6, label='Train residuals')
plt.scatter(y_test_pred, test_residuals, alpha=0.8, label='Test residuals')
plt.axhline(y=0, color='red', linestyle='--', linewidth=2)

plt.xlabel('Predicted y')
plt.ylabel('Residuals')
plt.title('Residual Plot')
plt.legend()
plt.grid(alpha=0.3)

residual_plot_path = 'd:/da/.vscode/residual_plot.png'
plt.savefig(residual_plot_path, dpi=150, bbox_inches='tight')
print('Saved residual plot to', residual_plot_path)
plt.show()

# -----------------------------
# 잔차 히스토그램
# 잔차가 0을 중심으로 어느 정도 대칭적인지 확인
# -----------------------------
plt.figure(figsize=(8, 6))
plt.hist(train_residuals, bins=15, alpha=0.6, label='Train residuals')
plt.hist(test_residuals, bins=15, alpha=0.8, label='Test residuals')

plt.xlabel('Residuals')
plt.ylabel('Frequency')
plt.title('Residual Histogram')
plt.legend()
plt.grid(alpha=0.3)

residual_hist_path = 'd:/da/.vscode/residual_histogram.png'
plt.savefig(residual_hist_path, dpi=150, bbox_inches='tight')
print('Saved residual histogram to', residual_hist_path)
plt.show()

# -----------------------------
# 5번: 잔차의 정규성 확인
# -----------------------------

# Shapiro-Wilk 정규성 검정
train_shapiro_stat, train_shapiro_p = shapiro(train_residuals.ravel())
test_shapiro_stat, test_shapiro_p = shapiro(test_residuals.ravel())

print("\n=== 잔차 정규성 검정 (Shapiro-Wilk) ===")
print(f"훈련 데이터 Shapiro statistic: {train_shapiro_stat}")
print(f"훈련 데이터 Shapiro p-value: {train_shapiro_p}")
print(f"테스트 데이터 Shapiro statistic: {test_shapiro_stat}")
print(f"테스트 데이터 Shapiro p-value: {test_shapiro_p}")

# Q-Q plot : 훈련 데이터 잔차
fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
sm.qqplot(train_residuals.ravel(), line='45', fit=True, ax=ax)
ax.set_title('Q-Q Plot of Train Residuals')
ax.grid(alpha=0.3)

qq_train_path = 'd:/da/.vscode/qqplot_train_residuals.png'
plt.savefig(qq_train_path, dpi=150, bbox_inches='tight')
print('Saved train residual Q-Q plot to', qq_train_path)
plt.show()

# Q-Q plot : 테스트 데이터 잔차
fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
sm.qqplot(test_residuals.ravel(), line='45', fit=True, ax=ax)
ax.set_title('Q-Q Plot of Test Residuals')
ax.grid(alpha=0.3)

qq_test_path = 'd:/da/.vscode/qqplot_test_residuals.png'
plt.savefig(qq_test_path, dpi=150, bbox_inches='tight')
print('Saved test residual Q-Q plot to', qq_test_path)
plt.show()

# -----------------------------
# 6번: 등분산성 확인
# -----------------------------

# Breusch-Pagan 검정
# 귀무가설(H0): 잔차의 분산이 일정하다(등분산)
bp_lm_stat, bp_lm_pvalue, bp_f_stat, bp_f_pvalue = het_breuschpagan(
    ols_model.resid,   # 회귀모델 잔차
    X_train_sm         # 상수항 포함 설명변수
)

print("\n=== 등분산성 검정 (Breusch-Pagan) ===")
print(f"LM statistic: {bp_lm_stat}")
print(f"LM p-value: {bp_lm_pvalue}")
print(f"F statistic: {bp_f_stat}")
print(f"F p-value: {bp_f_pvalue}")

# 간단 해석 문구
# 보통은 설정한 유의수준과 p-value를 비교해서 해석
if bp_lm_pvalue < 0.05:
    print("해석: 등분산이라고 보기 어려울 수 있음 (이분산성 의심)")
else:
    print("해석: 등분산 가정을 크게 해치지 않는 것으로 볼 수 있음")

# -----------------------------
# 7번: 이상치 / 영향점 확인
# -----------------------------

influence = OLSInfluence(ols_model)

# 표준화된 잔차와 leverage, Cook's distance 추출
studentized_residuals = influence.resid_studentized_internal
leverage = influence.hat_matrix_diag
cooks_d = influence.cooks_distance[0]

# 기준값 설정
n = len(X_train)                 # 훈련 데이터 개수
param_count = X_train_sm.shape[1]  # 상수항 포함 파라미터 개수
leverage_threshold = 2 * param_count / n
cooks_threshold = 4 / n

print("\n=== 이상치 / 영향점 확인 ===")
print(f"leverage 기준값: {leverage_threshold}")
print(f"Cook's distance 기준값: {cooks_threshold}")

# 조건에 걸리는 관측치 인덱스 찾기
outlier_idx = np.where(
    (np.abs(studentized_residuals) > 2) |
    (leverage > leverage_threshold) |
    (cooks_d > cooks_threshold)
)[0]

print(f"의심 관측치 개수: {len(outlier_idx)}")
print(f"의심 관측치 인덱스: {outlier_idx}")

# 각 의심 관측치 상세 출력
for idx in outlier_idx:
    print(
        f"index={idx}, "
        f"X={X_train[idx][0]}, "
        f"y={y_train[idx][0]}, "
        f"studentized_residual={studentized_residuals[idx]}, "
        f"leverage={leverage[idx]}, "
        f"cooks_d={cooks_d[idx]}"
    )

# -----------------------------
# 표준화 잔차 그래프
# -----------------------------
plt.figure(figsize=(8, 6))
plt.scatter(range(n), studentized_residuals, alpha=0.7)
plt.axhline(y=2, color='red', linestyle='--', linewidth=1.5)
plt.axhline(y=-2, color='red', linestyle='--', linewidth=1.5)

plt.xlabel('Observation Index')
plt.ylabel('Studentized Residual')
plt.title('Studentized Residual Plot')
plt.grid(alpha=0.3)

studentized_plot_path = 'd:/da/.vscode/studentized_residual_plot.png'
plt.savefig(studentized_plot_path, dpi=150, bbox_inches='tight')
print('Saved studentized residual plot to', studentized_plot_path)
plt.show()

# -----------------------------
# 레버리지 그래프
# -----------------------------
plt.figure(figsize=(8, 6))
plt.scatter(range(n), leverage, alpha=0.7)
plt.axhline(y=leverage_threshold, color='red', linestyle='--', linewidth=1.5)

plt.xlabel('Observation Index')
plt.ylabel('Leverage')
plt.title('Leverage Plot')
plt.grid(alpha=0.3)

leverage_plot_path = 'd:/da/.vscode/leverage_plot.png'
plt.savefig(leverage_plot_path, dpi=150, bbox_inches='tight')
print('Saved leverage plot to', leverage_plot_path)
plt.show()

# -----------------------------
# 영향점 확인 그래프 (cook's distance)
# -----------------------------
plt.figure(figsize=(8, 6))
plt.bar(range(n), cooks_d, alpha=0.7)
plt.axhline(y=cooks_threshold, color='red', linestyle='--', linewidth=1.5)

plt.xlabel('Observation Index')
plt.ylabel("Cook's Distance")
plt.title("Cook's Distance Plot")
plt.grid(alpha=0.3)

cooks_plot_path = 'd:/da/.vscode/cooks_distance_plot.png'
plt.savefig(cooks_plot_path, dpi=150, bbox_inches='tight')
print("Saved Cook's distance plot to", cooks_plot_path)
plt.show()