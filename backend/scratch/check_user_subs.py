from app.db import SessionLocal
from app.models import User, UserSubscription

def check_user_subscriptions(email):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User ID: {user.id}, Email: {user.email}")
            subs = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).all()
            print(f"Found {len(subs)} subscriptions:")
            for s in subs:
                print(f"  Batch: {s.batch_slug}, Status: {s.status}, Start: {s.start_at}, End: {s.end_at}")
        else:
            print(f"User {email} not found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_user_subscriptions("1Agarwalrevi@gmail.com")
