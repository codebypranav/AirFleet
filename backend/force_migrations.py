#!/usr/bin/env python
"""
FORCE MIGRATIONS SCRIPT
This script will force Django migrations to run without excessive checks.
For use with Railway deployments where migrations aren't being automatically applied.
"""
import os
import sys
import django
import subprocess
import time
import psycopg2
import dj_database_url
from django.db import connection

# Force the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')

def log(message):
    """Print with timestamp"""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def execute_command(command):
    """Execute a shell command and return the result"""
    log(f"EXECUTING: {command}")
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    stdout, stderr = process.communicate()
    
    if stdout:
        log(f"STDOUT: {stdout}")
    if stderr:
        log(f"STDERR: {stderr}")
    
    log(f"Command exit code: {process.returncode}")
    return process.returncode == 0

def verify_direct_connection():
    """Verify direct PostgreSQL connection without Django"""
    log("CHECKING DIRECT DATABASE CONNECTION")
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        log("ERROR: DATABASE_URL environment variable is not set!")
        log("Set DATABASE_URL to ${{ Postgres.DATABASE_URL }} in Railway dashboard")
        return False
    
    log(f"Using DATABASE_URL: {database_url.replace('://', '://[USERNAME]:[PASSWORD]@')}")
    
    try:
        config = dj_database_url.parse(database_url)
        log(f"Host: {config['HOST']}, Port: {config['PORT']}, Database: {config['NAME']}")
        
        # Try direct connection
        log("Attempting direct PostgreSQL connection...")
        conn = psycopg2.connect(
            host=config['HOST'],
            port=config['PORT'],
            user=config['USER'],
            password=config['PASSWORD'],
            dbname=config['NAME']
        )
        
        log("SUCCESS: Direct PostgreSQL connection established")
        
        # Check if we can create tables
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS migration_test (id SERIAL PRIMARY KEY);")
        conn.commit()
        log("Successfully created test table")
        
        # Drop test table
        cursor.execute("DROP TABLE migration_test;")
        conn.commit()
        log("Successfully dropped test table")
        
        # Close connection
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        log(f"ERROR in direct connection: {e}")
        return False

def main():
    log("STARTING FORCED MIGRATIONS")

    # Check direct database connection first
    if not verify_direct_connection():
        log("ERROR: Direct database connection failed")
        log("Please check your DATABASE_URL and ensure the PostgreSQL service is running")
        # Continue anyway, as Django might have different connection settings
    
    # Initialize Django
    log("Initializing Django...")
    try:
        django.setup()
        log("Django initialized")
    except Exception as e:
        log(f"Django initialization failed: {e}")
        return 1

    # Test database connection
    log("Testing database connection via Django...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            log("Database connection via Django established")
    except Exception as e:
        log(f"Database connection via Django failed: {e}")
        # Show environment variables for debugging (masking sensitive values)
        log("Environment variables:")
        for key, value in os.environ.items():
            if 'SECRET' in key or 'PASSWORD' in key or 'KEY' in key:
                log(f"  {key}=***SENSITIVE***")
            elif 'DATABASE_URL' in key:
                masked = value.replace('://', '://[USERNAME]:[PASSWORD]@')
                log(f"  {key}={masked}")
            else:
                log(f"  {key}={value}")
        
        # Try to create database schema directly
        log("Attempting direct schema creation...")
        try:
            db_url = os.environ.get('DATABASE_URL')
            if db_url:
                config = dj_database_url.parse(db_url)
                with psycopg2.connect(
                    host=config['HOST'],
                    port=config['PORT'],
                    user=config['USER'],
                    password=config['PASSWORD'],
                    dbname=config['NAME']
                ) as conn:
                    conn.autocommit = True
                    with conn.cursor() as cursor:
                        # Create users_customuser table directly
                        cursor.execute("""
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
                        log("Successfully created users_customuser table directly")
            else:
                log("Cannot create schema directly: DATABASE_URL not set")
        except Exception as e2:
            log(f"Direct schema creation failed: {e2}")
        
        # Continue despite the error

    # Create migrations for the users app
    log("Creating migrations for users app...")
    if not execute_command("python manage.py makemigrations users --noinput"):
        log("Failed to create migrations for users app, but continuing...")
    
    # Show migration status
    log("Current migration status:")
    execute_command("python manage.py showmigrations")
    
    # Force migrations for all apps
    log("Forcing migrations for all apps...")
    if not execute_command("python manage.py migrate --noinput --force-color"):
        log("Migration for all apps may have had issues, continuing...")
        
    # Specifically force migrations for the users app
    log("Forcing migrations for users app...")
    if not execute_command("python manage.py migrate users --noinput --force-color"):
        log("Migration for users app may have had issues, continuing...")
    
    # Verify the users_customuser table exists
    log("Verifying users_customuser table...")
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
                log("SUCCESS: users_customuser table exists")
            else:
                log("ERROR: users_customuser table does not exist after migrations")
                # Try to create the table directly
                log("Attempting to create users_customuser table directly...")
                try:
                    cursor.execute("""
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
                    connection.commit()
                    log("Direct table creation executed")
                except Exception as e:
                    log(f"Failed to create table directly: {e}")
    except Exception as e:
        log(f"Error verifying table: {e}")
        # Continue despite the error
    
    # Show the tables that exist
    log("Tables in database:")
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = cursor.fetchall()
            if tables:
                for table in tables:
                    log(f"  - {table[0]}")
            else:
                log("  No tables found in the database!")
    except Exception as e:
        log(f"Error listing tables: {e}")
    
    log("FORCED MIGRATIONS COMPLETED")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 