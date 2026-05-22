from app.db import SessionLocal
from app.models import User

def check_user(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User ID: {user.id}")
            print(f"Approve: {repr(user.approve)} (type: {type(user.approve)})")
            print(f"DocStatus: {repr(user.document_file_status)} (type: {type(user.document_file_status)})")
        else:
            print(f"User {email} not found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_user("1Agarwalrevi@gmail.com")
