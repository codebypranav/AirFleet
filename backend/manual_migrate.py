#!/usr/bin/env python
"""
Manual migration script for AirFleet

This script can be run locally to apply migrations to the Railway database.
Usage:
    python manual_migrate.py <DATABASE_PUBLIC_URL>
"""
import os
import sys
import django
import subprocess
from django.db import connection

def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_migrate.py <DATABASE_PUBLIC_URL>")
        return 1
    
    # Get the database URL from command line
    database_url = sys.argv[1]
    
    # Set environment variables
    os.environ['DATABASE_URL'] = database_url
    os.environ['DJANGO_SETTINGS_MODULE'] = 'AirFleet_api.settings'
    
    print(f"Using database URL: {database_url.replace('://', '://[USERNAME]:[PASSWORD]@')}")
    
    # Initialize Django
    print("Initializing Django...")
    django.setup()
    
    # Test database connection
    print("Testing database connection...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return 1
    
    # Run migrations
    print("\nRunning makemigrations...")
    subprocess.run(["python3", "manage.py", "makemigrations"])
    
    print("\nRunning migrations...")
    subprocess.run(["python3", "manage.py", "migrate"])
    
    print("\nRunning migrations for users app specifically...")
    subprocess.run(["python3", "manage.py", "migrate", "users"])
    
    # Verify users_customuser table exists
    print("\nVerifying users_customuser table...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users_customuser'
                );
            """)
            table_exists = cursor.fetchone()[0]
            if table_exists:
                print("SUCCESS: users_customuser table exists")
            else:
                print("ERROR: users_customuser table does not exist")
                return 1
            
            # List all tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = cursor.fetchall()
            print("\nTables in database:")
            for table in tables:
                print(f"  - {table[0]}")
    except Exception as e:
        print(f"Error verifying table: {e}")
        return 1
    
    print("\nMigrations completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 