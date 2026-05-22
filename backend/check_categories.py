from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def check_categories():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    with engine.connect() as conn:
        print("--- Unique Categories ---")
        stmt = "SELECT DISTINCT category_name FROM package"
        res = conn.execute(text(stmt)).fetchall()
        for r in res:
            print(f"'{r[0]}'")

if __name__ == "__main__":
    check_categories()
