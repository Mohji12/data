from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def check_batch_15():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        print("--- Batch 15 Packages ---")
        stmt = "SELECT id, name, category_name, total_amount, subscription FROM package WHERE subscription = 'Batch 15'"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(r)

if __name__ == "__main__":
    check_batch_15()
