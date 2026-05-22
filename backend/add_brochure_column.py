from sqlalchemy import text
from app.db import engine

def add_missing_column():
    with engine.connect() as conn:
        print("Checking for brochure_file column in batch_master table...")
        # Check if column exists
        result = conn.execute(text("SHOW COLUMNS FROM batch_master LIKE 'brochure_file'"))
        if not result.fetchone():
            print("Adding brochure_file column to batch_master table...")
            conn.execute(text("ALTER TABLE batch_master ADD COLUMN brochure_file VARCHAR(255) AFTER registration_fee_structure"))
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column brochure_file already exists.")

if __name__ == "__main__":
    add_missing_column()
