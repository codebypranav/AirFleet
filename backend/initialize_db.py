#!/usr/bin/env python
"""
Database initialization script for AirFleet

This script:
1. Connects to the database
2. Creates tables if they don't exist
3. Creates initial migrations if they don't exist
4. Applies all migrations
"""
import os
import sys
import subprocess
import django
from django.db import connection

def run_command(command):
    """Run a shell command and return its output"""
    print(f"Running: {command}")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return False
    else:
        print(f"Command succeeded with output: {result.stdout}")
        return True

def main():
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')
    django.setup()
    
    # Check database connection
    print("Checking database connection...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        return 1
    
    # Force create initial migrations
    print("\nCreating initial migrations...")
    if not run_command("python manage.py makemigrations"):
        print("Creating initial migrations failed, but continuing...")
    
    # Create migrations for users app specifically
    print("\nCreating migrations for users app...")
    if not run_command("python manage.py makemigrations users"):
        print("Creating users migrations failed, but continuing...")
    
    # Print migrations status before applying
    print("\nMigration status before applying:")
    run_command("python manage.py showmigrations")
    
    # Apply migrations
    print("\nApplying migrations...")
    if not run_command("python manage.py migrate"):
        print("Warning: Migrations failed")
    
    # Apply users migrations specifically
    print("\nApplying users migrations specifically...")
    if not run_command("python manage.py migrate users"):
        print("Warning: Users migrations failed")
    
    # Print migrations status after applying
    print("\nMigration status after applying:")
    run_command("python manage.py showmigrations")
    
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
                print("ERROR: users_customuser table DOES NOT exist")
                
                # Let's try a direct SQL approach if Django migrations failed
                print("\nAttempting direct SQL table creation...")
                try:
                    with connection.cursor() as create_cursor:
                        create_cursor.execute("""
                            CREATE TABLE IF NOT EXISTS users_customuser (
                                id SERIAL PRIMARY KEY,
                                password VARCHAR(128) NOT NULL,
                                last_login TIMESTAMP NULL,
                                is_superuser BOOLEAN NOT NULL,
                                username VARCHAR(150) UNIQUE NOT NULL,
                                first_name VARCHAR(150) NOT NULL,
                                last_name VARCHAR(150) NOT NULL,
                                email VARCHAR(254) UNIQUE NOT NULL,
                                is_staff BOOLEAN NOT NULL,
                                is_active BOOLEAN NOT NULL,
                                date_joined TIMESTAMP NOT NULL
                            );
                        """)
                        print("Direct SQL table creation executed")
                        
                        # Check if table now exists
                        create_cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'users_customuser'
                            );
                        """)
                        table_now_exists = create_cursor.fetchone()[0]
                        if table_now_exists:
                            print("SUCCESS: users_customuser table now exists via direct SQL")
                        else:
                            print("ERROR: users_customuser table STILL DOES NOT exist after direct SQL")
                except Exception as sql_error:
                    print(f"Direct SQL approach failed: {sql_error}")
    except Exception as e:
        print(f"Error verifying table: {e}")
        return 1
        
    print("\nDatabase initialization complete")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 