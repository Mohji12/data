"""Create user_video_progress table for dashboard watch-time KPIs."""

from sqlalchemy import text

from app.db import engine


DDL = """
CREATE TABLE IF NOT EXISTS user_video_progress (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    video_id INT NOT NULL,
    watched_seconds INT NOT NULL DEFAULT 0,
    last_position_seconds DOUBLE NULL,
    updated_at DATETIME NULL,
    created_at DATETIME NULL,
    UNIQUE KEY uq_user_video_progress (user_id, video_id),
    KEY ix_user_video_progress_user (user_id),
    KEY ix_user_video_progress_video (video_id)
)
"""


def add_user_video_progress_table() -> None:
    with engine.connect() as conn:
        print("Checking for user_video_progress table...")
        result = conn.execute(text("SHOW TABLES LIKE 'user_video_progress'"))
        if result.fetchone():
            print("Table user_video_progress already exists.")
            return
        print("Creating user_video_progress table...")
        conn.execute(text(DDL))
        conn.commit()
        print("Table created successfully.")


if __name__ == "__main__":
    add_user_video_progress_table()
