from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def check_packages():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        print("--- Foreign Delegates Packages ---")
        stmt = "SELECT id, name, category_name, total_amount, subscription FROM package WHERE category_name LIKE '%Foreign%' LIMIT 5"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(r)
        
        print("\n--- Indian Delegates Packages ---")
        stmt = "SELECT id, name, category_name, total_amount, subscription FROM package WHERE category_name LIKE '%Indian%' LIMIT 5"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(r)

if __name__ == "__main__":
    check_packages()
