from sqlalchemy import text
from app.db import engine

def add_missing_columns():
    with engine.connect() as conn:
        print("Checking for new columns in batch_master table...")
        
        # Add description column
        result = conn.execute(text("SHOW COLUMNS FROM batch_master LIKE 'description'"))
        if not result.fetchone():
            print("Adding description column to batch_master table...")
            conn.execute(text("ALTER TABLE batch_master ADD COLUMN description TEXT AFTER registration_fee_structure"))
            conn.commit()
            print("Description column added successfully.")
        else:
            print("Column description already exists.")

        # Add video_url column
        result = conn.execute(text("SHOW COLUMNS FROM batch_master LIKE 'video_url'"))
        if not result.fetchone():
            print("Adding video_url column to batch_master table...")
            conn.execute(text("ALTER TABLE batch_master ADD COLUMN video_url VARCHAR(255) AFTER description"))
            conn.commit()
            print("Video_url column added successfully.")
        else:
            print("Column video_url already exists.")

if __name__ == "__main__":
    add_missing_columns()
