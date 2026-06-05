from app.db.database import Base, engine
from app.models import User, Session, Message, File, Summary

def init_db():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
