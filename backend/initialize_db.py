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
import dj_database_url
import psycopg2

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

def check_postgres_service():
    """Check if PostgreSQL service is properly configured"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set!")
        print("SOLUTION: In Railway, import the PostgreSQL service variables to your backend service.")
        return False
    
    print(f"DATABASE_URL is set and appears to be: {database_url.replace('://', '://[USERNAME]:[PASSWORD]@')}")
    
    # Parse the DATABASE_URL
    try:
        config = dj_database_url.parse(database_url)
        # Print connection details (without password)
        safe_config = {k: v for k, v in config.items() if k != 'PASSWORD'}
        print(f"Connection parameters: {safe_config}")
    except Exception as e:
        print(f"ERROR: Invalid DATABASE_URL format: {e}")
        return False
    
    # Try to connect directly with psycopg2
    try:
        print("\nAttempting direct connection to PostgreSQL...")
        conn = psycopg2.connect(
            host=config['HOST'],
            port=config['PORT'],
            user=config['USER'],
            password=config['PASSWORD'],
            dbname=config['NAME']
        )
        
        print("SUCCESS: Connected to PostgreSQL database!")
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL database: {e}")
        print("SOLUTION: Check if your PostgreSQL service is running and properly linked.")
        return False

def main():
    # Check PostgreSQL service configuration
    print("\n=== Checking PostgreSQL Service Configuration ===")
    if not check_postgres_service():
        print("\nERROR: PostgreSQL service check failed. Cannot proceed with initialization.")
        print("SOLUTION: In Railway, make sure to:")
        print("1. Go to your backend service's Variables tab")
        print("2. Click 'Add Shared Variables' at the bottom")
        print("3. Select your PostgreSQL service to import all its variables")
        print("4. Redeploy your backend service")
        return 1
    
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')
    django.setup()
    
    # Check database connection
    print("\n=== Checking Django Database Connection ===")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Django database connection successful")
    except Exception as e:
        print(f"Django database connection failed: {e}")
        return 1
    
    # Force create initial migrations
    print("\n=== Creating Initial Migrations ===")
    if not run_command("python manage.py makemigrations"):
        print("Creating initial migrations failed, but continuing...")
    
    # Create migrations for users app specifically
    print("\n=== Creating Migrations for Users App ===")
    if not run_command("python manage.py makemigrations users"):
        print("Creating users migrations failed, but continuing...")
    
    # Print migrations status before applying
    print("\n=== Migration Status Before Applying ===")
    run_command("python manage.py showmigrations")
    
    # Apply migrations
    print("\n=== Applying Migrations ===")
    if not run_command("python manage.py migrate"):
        print("Warning: Migrations failed")
    
    # Apply users migrations specifically
    print("\n=== Applying Users Migrations Specifically ===")
    if not run_command("python manage.py migrate users"):
        print("Warning: Users migrations failed")
    
    # Print migrations status after applying
    print("\n=== Migration Status After Applying ===")
    run_command("python manage.py showmigrations")
    
    # Verify users_customuser table exists
    print("\n=== Verifying users_customuser Table ===")
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
                print("\n=== Attempting Direct SQL Table Creation ===")
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
        
    print("\n=== Database Initialization Complete ===")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 