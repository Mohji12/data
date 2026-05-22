from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

def fix_all_tables():
    db_pass = quote_plus('Admin@12345')
    url = f'mysql+pymysql://admin:{db_pass}@13.127.212.121:3306/admin_CriticalCareClasses'
    engine = create_engine(url)
    
    tables_to_check = ['package', 'country', 'batch_master', 'coupon_master', 'folder_master', 'testimonial']
    
    with engine.connect() as conn:
        for table in tables_to_check:
            print(f"Checking table: {table}")
            try:
                res = conn.execute(text(f"DESCRIBE {table}")).fetchall()
                existing_cols = [r[0] for r in res]
                if 'status' not in existing_cols:
                    print(f"Adding 'status' to {table}...")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN status VARCHAR(1) DEFAULT '1'"))
                    conn.commit()
                else:
                    print(f"OK: {table} already has 'status'")
            except Exception as e:
                print(f"Error on {table}: {e}")

if __name__ == "__main__":
    fix_all_tables()
