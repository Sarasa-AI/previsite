import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.auth.security import get_password_hash


def create_default_patient():
    db = SessionLocal()
    try:
        existing_patient = db.query(User).filter(User.full_name == "Test Patient").first()
        if existing_patient:
            print("Patient user already exists")
            return

        patient = User(
            email="test_patient@patient.local",
            full_name="Test Patient",
            hashed_password=get_password_hash("test12345"),
            role=UserRole.PATIENT,
            is_active=True
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)
        print(f"Patient user created successfully: {patient.full_name}")
    except Exception as e:
        print(f"Error creating patient: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_default_patient()
