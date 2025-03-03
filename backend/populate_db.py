#!/usr/bin/env python
"""
Database population script for AirFleet

This script populates the database with initial data.
Usage:
    python populate_db.py <DATABASE_PUBLIC_URL>
"""
import os
import sys
import django
from django.db import connection

def main():
    if len(sys.argv) < 2:
        print("Usage: python populate_db.py <DATABASE_PUBLIC_URL>")
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
    
    # Import models
    from users.models import CustomUser
    from django.contrib.auth.hashers import make_password
    
    # Create a superuser if none exists
    print("Creating superuser if needed...")
    if not CustomUser.objects.filter(username='admin').exists():
        admin_user = CustomUser.objects.create(
            username='admin',
            email='admin@example.com',
            password=make_password('adminpassword'),
            is_staff=True,
            is_superuser=True
        )
        print(f"Created superuser: {admin_user.username}")
    else:
        print("Superuser already exists")
    
    # Create some test users
    print("\nCreating test users if needed...")
    test_users = [
        {'username': 'testuser1', 'email': 'user1@example.com', 'password': 'password123'},
        {'username': 'testuser2', 'email': 'user2@example.com', 'password': 'password123'},
        {'username': 'testuser3', 'email': 'user3@example.com', 'password': 'password123'},
    ]
    
    for user_data in test_users:
        if not CustomUser.objects.filter(username=user_data['username']).exists():
            user = CustomUser.objects.create(
                username=user_data['username'],
                email=user_data['email'],
                password=make_password(user_data['password'])
            )
            print(f"Created test user: {user.username}")
        else:
            print(f"User {user_data['username']} already exists")
    
    # Verify users were created
    print("\nVerifying users...")
    all_users = CustomUser.objects.all()
    print(f"Total users in database: {all_users.count()}")
    for user in all_users:
        print(f"  - {user.username} ({user.email})")
    
    print("\nDatabase population completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 