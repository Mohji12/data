from sqlalchemy import text
from app.db import engine

def add_video_file_column():
    with engine.connect() as conn:
        print("Checking for video_file column in batch_master table...")
        result = conn.execute(text("SHOW COLUMNS FROM batch_master LIKE 'video_file'"))
        if not result.fetchone():
            print("Adding video_file column to batch_master table...")
            conn.execute(text("ALTER TABLE batch_master ADD COLUMN video_file VARCHAR(255) AFTER video_url"))
            conn.commit()
            print("Video_file column added successfully.")
        else:
            print("Column video_file already exists.")

if __name__ == "__main__":
    add_video_file_column()
