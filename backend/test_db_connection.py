#!/usr/bin/env python
"""
Simple script to test direct PostgreSQL connection without Django
"""
import os
import sys
import psycopg2
import dj_database_url

def main():
    # Get the DATABASE_URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set!")
        return 1
    
    print(f"Using DATABASE_URL: {database_url.replace('://', '://[USERNAME]:[PASSWORD]@')}")
    
    # Parse the DATABASE_URL
    config = dj_database_url.parse(database_url)
    
    # Print connection details (without password)
    safe_config = {k: v for k, v in config.items() if k != 'PASSWORD'}
    print(f"Connection parameters: {safe_config}")
    
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
        
        # Check if the database is empty
        cursor = conn.cursor()
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
        tables = cursor.fetchall()
        
        if not tables:
            print("Database appears to be empty (no tables found)")
        else:
            print(f"Found {len(tables)} tables in the database:")
            for table in tables:
                print(f"- {table[0]}")
        
        # Close connection
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL database: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 