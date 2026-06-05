import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.auth.security import get_password_hash


def create_default_doctor():
    db = SessionLocal()
    try:
        existing_doctor = db.query(User).filter(User.email == "Amsh@doctor.com").first()
        if existing_doctor:
            print("Doctor user already exists")
            return

        doctor = User(
            email="Amsh@doctor.com",
            full_name="Dr. Amsh",
            hashed_password=get_password_hash("1234"),
            role=UserRole.DOCTOR,
            is_active=True
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        print(f"Doctor user created successfully: {doctor.email}")
    except Exception as e:
        print(f"Error creating doctor: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_default_doctor()
