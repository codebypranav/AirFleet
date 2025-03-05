#!/usr/bin/env python
"""
Diagnostic script to check database connection and schema
"""
import os
import sys
import django
from django.db import connection
import dj_database_url

def main():
    # Print environment details
    print("ENVIRONMENT VARIABLES:")
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
    print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Not set')}")
    
    # Initialize Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')
    django.setup()
    
    # Get database config
    from django.conf import settings
    print("\nDATABASE CONFIG:")
    db_config = settings.DATABASES['default']
    # Don't print password
    safe_config = {k: v for k, v in db_config.items() if k != 'PASSWORD'}
    print(safe_config)
    
    # Test connection
    print("\nTESTING DATABASE CONNECTION:")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"Connection test result: {result}")
            
            # Check for users_customuser table
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users_customuser'
                );
            """)
            table_exists = cursor.fetchone()[0]
            print(f"users_customuser table exists: {table_exists}")
            
            if table_exists:
                # Count users
                cursor.execute("SELECT COUNT(*) FROM users_customuser")
                user_count = cursor.fetchone()[0]
                print(f"Number of users: {user_count}")
            # List all tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            print("\nEXISTING TABLES:")
            for table in tables:
                print(f"- {table}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    
    print("\nDiagnostic completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 