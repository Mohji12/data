from app.db import SessionLocal
from app.models import User

def check_stuck_users():
    db = SessionLocal()
    try:
        # Users who are approved but not verified
        stuck = db.query(User).filter(User.approve == "1", User.verify != "Yes").all()
        print(f"Found {len(stuck)} users approved but not verified:")
        for u in stuck[:10]:
            print(f"ID={u.id}, Email={u.email}, Verify={u.verify}")
    finally:
        db.close()

if __name__ == "__main__":
    check_stuck_users()
