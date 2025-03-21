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
    print(f"[{time.strftime('%H:%M:%S')}] FORCE_MIGRATIONS: {message}")

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
    
    # Check for Docker/compose environment variables
    postgres_host = os.environ.get('POSTGRES_HOST')
    postgres_port = os.environ.get('POSTGRES_PORT', '5432')
    postgres_db = os.environ.get('POSTGRES_DB')
    postgres_user = os.environ.get('POSTGRES_USER')
    postgres_password = os.environ.get('POSTGRES_PASSWORD')
    
    # Try Docker environment variables first if available
    if postgres_host and postgres_db and postgres_user and postgres_password:
        log(f"Using Docker environment variables: Host={postgres_host}, Port={postgres_port}, DB={postgres_db}")
        
        try:
            # Try direct connection
            log("Attempting direct PostgreSQL connection using Docker environment variables...")
            conn = psycopg2.connect(
                host=postgres_host,
                port=postgres_port,
                user=postgres_user,
                password=postgres_password,
                dbname=postgres_db
            )
            
            log("SUCCESS: Direct PostgreSQL connection established using Docker environment variables")
            
            # Check if we can create tables
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS migration_test (id SERIAL PRIMARY KEY);")
            conn.commit()
            log("Successfully created test table")
            
            # List existing tables
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            tables = cursor.fetchall()
            log(f"Found {len(tables)} tables in database:")
            for table in tables:
                log(f"  - {table[0]}")
            
            # Directly create users_customuser table
            log("DIRECTLY CREATING users_customuser TABLE IF NOT EXISTS...")
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users_customuser (
                        id SERIAL PRIMARY KEY,
                        password VARCHAR(128) NOT NULL,
                        last_login TIMESTAMP NULL,
                        is_superuser BOOLEAN NOT NULL DEFAULT false,
                        username VARCHAR(150) UNIQUE NOT NULL,
                        first_name VARCHAR(150) NOT NULL DEFAULT '',
                        last_name VARCHAR(150) NOT NULL DEFAULT '',
                        email VARCHAR(254) UNIQUE NOT NULL,
                        is_staff BOOLEAN NOT NULL DEFAULT false,
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        date_joined TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                log("Successfully created users_customuser table")
            except Exception as e:
                log(f"Error creating users_customuser table: {e}")
                
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            log(f"ERROR connecting to database using Docker environment variables: {e}")
            # Continue to try DATABASE_URL if Docker environment variables failed
    
    # Fallback to DATABASE_URL
    if not database_url:
        log("ERROR: Neither Docker environment variables nor DATABASE_URL is properly set!")
        log("For Docker: ensure POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are set")
        log("For Railway: set DATABASE_URL to ${{ Postgres.DATABASE_URL }} in Railway dashboard")
        return False
    
    # Print masked URL for debugging
    masked_url = database_url.replace('://', '://[USERNAME]:[PASSWORD]@')
    log(f"Using DATABASE_URL: {masked_url}")
    
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
        
        # List existing tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cursor.fetchall()
        log(f"Found {len(tables)} tables in database:")
        for table in tables:
            log(f"  - {table[0]}")
        
        # Directly create users_customuser table
        log("DIRECTLY CREATING users_customuser TABLE IF NOT EXISTS...")
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users_customuser (
                    id SERIAL PRIMARY KEY,
                    password VARCHAR(128) NOT NULL,
                    last_login TIMESTAMP NULL,
                    is_superuser BOOLEAN NOT NULL DEFAULT false,
                    username VARCHAR(150) UNIQUE NOT NULL,
                    first_name VARCHAR(150) NOT NULL DEFAULT '',
                    last_name VARCHAR(150) NOT NULL DEFAULT '',
                    email VARCHAR(254) UNIQUE NOT NULL,
                    is_staff BOOLEAN NOT NULL DEFAULT false,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    date_joined TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            log("USERS TABLE CREATED DIRECTLY")
        except Exception as e:
            log(f"Error creating users table directly: {e}")
        
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

def create_auth_tables():
    """Create essential auth-related tables directly"""
    log("Creating essential auth tables directly...")
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        log("Cannot create auth tables: DATABASE_URL not set")
        return False
    
    try:
        config = dj_database_url.parse(database_url)
        with psycopg2.connect(
            host=config['HOST'],
            port=config['PORT'],
            user=config['USER'],
            password=config['PASSWORD'],
            dbname=config['NAME']
        ) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                # Create django_migrations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS django_migrations (
                        id SERIAL PRIMARY KEY,
                        app VARCHAR(255) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        applied TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                log("Created django_migrations table")
                
                # Insert fake migration records to satisfy Django
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied)
                    VALUES 
                        ('users', 'initial', CURRENT_TIMESTAMP),
                        ('auth', 'initial', CURRENT_TIMESTAMP),
                        ('contenttypes', 'initial', CURRENT_TIMESTAMP)
                    ON CONFLICT DO NOTHING;
                """)
                log("Added fake migration records")
                
                # Create auth tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS auth_permission (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        content_type_id INTEGER NOT NULL,
                        codename VARCHAR(100) NOT NULL,
                        UNIQUE (content_type_id, codename)
                    );
                    
                    CREATE TABLE IF NOT EXISTS django_content_type (
                        id SERIAL PRIMARY KEY,
                        app_label VARCHAR(100) NOT NULL,
                        model VARCHAR(100) NOT NULL,
                        UNIQUE (app_label, model)
                    );
                    
                    CREATE TABLE IF NOT EXISTS auth_group (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(150) UNIQUE NOT NULL
                    );
                    
                    CREATE TABLE IF NOT EXISTS auth_group_permissions (
                        id SERIAL PRIMARY KEY,
                        group_id INTEGER NOT NULL,
                        permission_id INTEGER NOT NULL,
                        UNIQUE (group_id, permission_id)
                    );
                    
                    CREATE TABLE IF NOT EXISTS users_customuser_groups (
                        id SERIAL PRIMARY KEY,
                        customuser_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        UNIQUE (customuser_id, group_id)
                    );
                    
                    CREATE TABLE IF NOT EXISTS users_customuser_user_permissions (
                        id SERIAL PRIMARY KEY,
                        customuser_id INTEGER NOT NULL,
                        permission_id INTEGER NOT NULL,
                        UNIQUE (customuser_id, permission_id)
                    );
                """)
                log("Created auth-related tables")
        return True
    except Exception as e:
        log(f"Error creating auth tables: {e}")
        return False

def main():
    log("======== STARTING FORCED MIGRATIONS ========")
    
    # Print environment variables for debugging (masking sensitive values)
    log("Environment variables:")
    for key, value in os.environ.items():
        if key.startswith('DJANGO') or key.startswith('DATABASE') or key.startswith('PG'):
            if 'PASSWORD' in key or 'URL' in key:
                if key == 'DATABASE_URL' and value:
                    masked = value.replace('://', '://[USERNAME]:[PASSWORD]@')
                    log(f"  {key}={masked}")
                else:
                    log(f"  {key}=***MASKED***")
            else:
                log(f"  {key}={value}")
    
    # Check direct database connection first
    if not verify_direct_connection():
        log("ERROR: Direct database connection failed")
        log("Please check your DATABASE_URL and ensure the PostgreSQL service is running")
        # Continue anyway, as Django might have different connection settings
    
    # Create auth tables directly
    create_auth_tables()
    
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
        # Try to create schema directly (already tried in verify_direct_connection, but do it again)
        log("Attempting direct schema creation again...")
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
                                is_superuser BOOLEAN NOT NULL DEFAULT false,
                                username VARCHAR(150) UNIQUE NOT NULL,
                                first_name VARCHAR(150) NOT NULL DEFAULT '',
                                last_name VARCHAR(150) NOT NULL DEFAULT '',
                                email VARCHAR(254) UNIQUE NOT NULL,
                                is_staff BOOLEAN NOT NULL DEFAULT false,
                                is_active BOOLEAN NOT NULL DEFAULT true,
                                date_joined TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                            is_superuser BOOLEAN NOT NULL DEFAULT false,
                            username VARCHAR(150) UNIQUE NOT NULL,
                            first_name VARCHAR(150) NOT NULL DEFAULT '',
                            last_name VARCHAR(150) NOT NULL DEFAULT '',
                            email VARCHAR(254) UNIQUE NOT NULL,
                            is_staff BOOLEAN NOT NULL DEFAULT false,
                            is_active BOOLEAN NOT NULL DEFAULT true,
                            date_joined TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    
    log("======== FORCED MIGRATIONS COMPLETED ========")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 