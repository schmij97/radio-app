# PostgreSQL setup for Render deployment
# Add this to your requirements.txt:
# psycopg2-binary==2.9.7

import os
import psycopg2
from urllib.parse import urlparse

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')  # Render provides this automatically

def get_db_connection_pg():
    """Get database connection - PostgreSQL for production, SQLite for development"""
    if DATABASE_URL:
        # Production: Use PostgreSQL
        return psycopg2.connect(DATABASE_URL)
    else:
        # Development: Use SQLite
        return sqlite3.connect(DATABASE_FILE)

def init_database_pg():
    """Initialize database with PostgreSQL support"""
    try:
        if DATABASE_URL:
            # PostgreSQL setup
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # Create table with PostgreSQL syntax
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS radio_ids (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    radio_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_default BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Check if we need to populate default data
            cursor.execute('SELECT COUNT(*) FROM radio_ids')
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Insert default radios
                default_radios = get_default_radios()
                
                for name, radio_id in default_radios:
                    is_default = radio_id != "CUSTOM"
                    cursor.execute('''
                        INSERT INTO radio_ids (name, radio_id, is_default) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (radio_id) DO NOTHING
                    ''', (name, radio_id, is_default))
                
                conn.commit()
                print(f"✅ PostgreSQL initialized with {len(default_radios)} default radio IDs")
            
            cursor.close()
            conn.close()
            
        else:
            # Fallback to SQLite for development
            init_database()
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        # Fallback to SQLite
        init_database()

def load_radio_ids_pg():
    """Load radio IDs with PostgreSQL support"""
    try:
        if DATABASE_URL:
            # PostgreSQL query
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT name, radio_id 
                FROM radio_ids 
                ORDER BY 
                    CASE WHEN radio_id = 'CUSTOM' THEN 0 ELSE 1 END,
                    name
            ''')
            
            radios = cursor.fetchall()
            cursor.close()
            conn.close()
            
            print(f"📊 Loaded {len(radios)} radios from PostgreSQL")
            return radios
            
        else:
            # Fallback to SQLite
            return hybrid_load_radio_ids()
            
    except Exception as e:
        print(f"❌ PostgreSQL load error: {e}")
        # Fallback to hybrid method
        return hybrid_load_radio_ids()

def add_radio_to_db_pg(name, radio_id):
    """Add radio with PostgreSQL support"""
    try:
        if DATABASE_URL:
            # PostgreSQL insert
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # Check for duplicates
            cursor.execute('SELECT name FROM radio_ids WHERE radio_id = %s', (radio_id,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.close()
                conn.close()
                raise ValueError(f"Radio ID '{radio_id}' already exists for '{existing[0]}'")
            
            # Insert new radio
            cursor.execute('''
                INSERT INTO radio_ids (name, radio_id, is_default) 
                VALUES (%s, %s, %s)
            ''', (name, radio_id, False))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Added to PostgreSQL: {name} - {radio_id}")
            return True
            
        else:
            # Fallback to hybrid method
            return hybrid_add_radio(name, radio_id)
            
    except Exception as e:
        print(f"❌ PostgreSQL add error: {e}")
        # Fallback to hybrid method
        return hybrid_add_radio(name, radio_id)

def delete_radio_from_db_pg(radio_id):
    """Delete radio with PostgreSQL support"""
    if radio_id == "CUSTOM":
        raise ValueError("Cannot delete the Custom Entry")
    
    try:
        if DATABASE_URL:
            # PostgreSQL delete
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute('SELECT name FROM radio_ids WHERE radio_id = %s', (radio_id,))
            existing = cursor.fetchone()
            
            if not existing:
                cursor.close()
                conn.close()
                raise ValueError(f"Radio ID '{radio_id}' not found")
            
            # Delete radio
            cursor.execute('DELETE FROM radio_ids WHERE radio_id = %s', (radio_id,))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            print(f"🗑️ Deleted from PostgreSQL: {existing[0]} - {radio_id}")
            return True
            
        else:
            # Fallback to hybrid method
            return hybrid_delete_radio(radio_id)
            
    except Exception as e:
        print(f"❌ PostgreSQL delete error: {e}")
        # Fallback to hybrid method
        return hybrid_delete_radio(radio_id)

# Update your main functions to use PostgreSQL versions:

def initialize_app_pg():
    """Initialize app with PostgreSQL support"""
    try:
        init_database_pg()
        
        # Get stats
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM radio_ids')
            total = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM radio_ids WHERE is_default = true')
            defaults = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            print(f"📊 PostgreSQL Database Stats:")
            print(f"   Total: {total}")
            print(f"   Default: {defaults}")
            print(f"   User Added: {total - defaults}")
        else:
            print("📊 Using SQLite fallback")
            
    except Exception as e:
        print(f"❌ App initialization error: {e}")

# Replace your existing functions in main.py with these PostgreSQL versions:
# load_radio_ids = load_radio_ids_pg
# add_radio_to_db = add_radio_to_db_pg  
# delete_radio_from_db = delete_radio_from_db_pg
# initialize_app = initialize_app_pg
