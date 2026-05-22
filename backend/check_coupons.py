from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def check_coupons():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        print("--- Coupon Master Columns ---")
        stmt = "DESCRIBE coupon_master"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(r)
        
        print("\n--- Active Coupons ---")
        stmt = "SELECT id, code, status FROM coupon_master WHERE status = '1' LIMIT 5"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(r)

if __name__ == "__main__":
    check_coupons()
