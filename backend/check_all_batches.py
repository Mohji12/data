from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def check_all_batches():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        print("--- All Batches in batch_master ---")
        stmt = "SELECT id, name, status FROM batch_master ORDER BY id DESC"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(f"ID: {r.id}, Name: {r.name}, Status: {r.status}")
        
        print("\n--- All Active Packages ---")
        stmt = "SELECT id, name, subscription, status, start_date, end_date FROM package WHERE status = '1'"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(f"ID: {r.id}, Name: {r.name}, Subscription: {r.subscription}, Status: {r.status}, Dates: {r.start_date} to {r.end_date}")

if __name__ == "__main__":
    check_all_batches()
