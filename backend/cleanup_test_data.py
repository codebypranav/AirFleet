#!/usr/bin/env python
"""
Test Data Cleanup Script for AirFleet

This script removes test data that is created during initial setup and migration.
It should be run during deployment after migrations but before the app is fully operational.

Usage:
    python cleanup_test_data.py
    
Environment variables:
    DATABASE_URL: The URL of the database to connect to
"""
import os
import sys
import django
import logging
from django.db import connection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cleanup-test-data")

def main():
    # Check if we're in production mode
    is_production = os.environ.get('ENVIRONMENT') == 'production'
    
    # Get the database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set!")
        return 1
    
    # Set environment variables for Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')
    
    # Initialize Django
    logger.info("Initializing Django...")
    django.setup()
    
    # Import models
    from users.models import CustomUser
    from flights.models import Flight
    
    # List of test usernames to remove
    test_usernames = ['testuser1', 'testuser2', 'testuser3']
    
    # In production, also remove the admin user
    if is_production:
        test_usernames.append('admin')
    
    logger.info(f"Running in {'PRODUCTION' if is_production else 'DEVELOPMENT'} mode")
    logger.info(f"Will remove these test users: {', '.join(test_usernames)}")
    
    # Count users before cleanup
    total_users_before = CustomUser.objects.count()
    logger.info(f"Total users before cleanup: {total_users_before}")
    
    # Delete test users and their associated data
    for username in test_usernames:
        try:
            user = CustomUser.objects.filter(username=username).first()
            if user:
                # Get count of flights associated with this user
                flight_count = Flight.objects.filter(user=user).count()
                
                # Delete the user (this will cascade delete their flights due to the ForeignKey relationship)
                user.delete()
                
                logger.info(f"Deleted test user '{username}' and {flight_count} associated flights")
            else:
                logger.info(f"Test user '{username}' not found - skipping")
        except Exception as e:
            logger.error(f"Error deleting test user '{username}': {e}")
    
    # Count users after cleanup
    total_users_after = CustomUser.objects.count()
    logger.info(f"Total users after cleanup: {total_users_after}")
    logger.info(f"Removed {total_users_before - total_users_after} test users")
    
    logger.info("Test data cleanup completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 