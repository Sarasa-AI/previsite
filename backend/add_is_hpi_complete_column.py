from app.db.database import engine, SessionLocal
from sqlalchemy import text

def add_is_hpi_complete_column():
    db = SessionLocal()
    try:
        conn = db.connection()
        
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'summaries' AND column_name = 'is_hpi_complete'
        """))
        
        if not result.fetchone():
            print("Adding is_hpi_complete column to summaries table")
            conn.execute(text("ALTER TABLE summaries ADD COLUMN is_hpi_complete BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Column added successfully")
        else:
            print("is_hpi_complete column already exists")
            
    except Exception as e:
        print(f"Error adding column: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_is_hpi_complete_column()
