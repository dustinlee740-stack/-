import pandas as pd

# 데이터프레임 생성
data = {
    'order_id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'user_id': ['u001', 'u002', 'u001', 'u003', 'u002', 'u004', 'u005', 'u001', 'u003', 'u002', 'u004', 'u005'],
    'order_date': ['2024-01-02', '2024-01-03', '2024-01-03', '2024-01-05', '2024-01-06', '2024-01-07', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10', '2024-01-10', '2024-01-11'],
    'category': ['Electronics', 'Electronics', 'Home', 'Home', 'Electronics', 'Fashion', 'Fashion', 'Electronics', 'Home', 'Fashion', 'Electronics', 'Home'],
    'product': ['Keyboard', 'Mouse', 'Cleaner', 'Vacuum', 'Monitor', 'T-shirt', 'Jeans', 'USB Cable', 'Table', 'Jacket', 'Webcam', 'Chair'],
    'price': [30000, 15000, 50000, 120000, 200000, 20000, 60000, 5000, 150000, 120000, 80000, 70000],
    'quantity': [1, 2, 1, 1, 1, 3, 1, 0, 1, 1, 1, 1],
    'payment_method': ['card', 'card', 'cash', 'card', 'card', 'point', 'card', 'cash', 'card', 'card', 'point', 'cash']
}

df = pd.DataFrame(data)

# total_amount 컬럼 생성
df['total_amount'] = df['price'] * df['quantity']

# 카테고리별 총 매출 계산 및 정렬
category_sales = df.groupby('category')['total_amount'].sum().reset_index()
category_sales = category_sales.sort_values(by='total_amount', ascending=False)

print(category_sales)