from app.db import SessionLocal
from app.models import User

def check_duplicates(email):
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email == email).all()
        print(f"Found {len(users)} users with email {email}:")
        for u in users:
            print(f"ID={u.id}, Approve={u.approve}, Payment={u.payment_status}, Verify={u.verify}")
    finally:
        db.close()

if __name__ == "__main__":
    check_duplicates("1Agarwalrevi@gmail.com")
