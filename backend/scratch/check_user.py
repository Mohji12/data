from app.db import SessionLocal
from app.models import User

def check_user(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User found: ID={user.id}, Email={user.email}, Approve={user.approve}, Payment={user.payment_status}, DocStatus={user.document_file_status}, Verify={user.verify}")
        else:
            print(f"User with email {email} not found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_user("1Agarwalrevi@gmail.com")
