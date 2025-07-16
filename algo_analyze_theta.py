import matplotlib.pyplot as plt
import seaborn as sns

def analyze_theta(intercept, coefs, X, y):
    from numpy import mean, std

    print("\n[세타 분석 결과]")
    print("- 절편 (theta_0):", round(intercept, 4))

    mean_y = mean(y)
    std_y = std(y)

    print(f"- 목표 변수 평균: {mean_y:.4f}, 표준편차: {std_y:.4f}")
    if abs(intercept) > mean_y + 2 * std_y:
        print("절편이 목표변수 범위에 비해 매우 큰 편입니다.")

    print("- 계수:")
    for name, coef in zip(X.columns, coefs):
        print(f"  {name}: {coef:.6f}")

    # 목표 변수 분포 시각화
    plt.figure(figsize=(8, 4))
    sns.histplot(y, kde=True, bins=20, color='skyblue')
    plt.axvline(intercept, color='red', linestyle='--', label=f'Intercept: {intercept:.2f}')
    plt.title('목표 변수 분포 및 절편 위치')
    plt.xlabel('y')
    plt.ylabel('빈도')
    plt.legend()
    plt.tight_layout()
    plt.show()
