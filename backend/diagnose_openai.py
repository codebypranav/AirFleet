#!/usr/bin/env python
"""
Diagnose OpenAI API integration for AirFleet

This script can be run to diagnose OpenAI API issues.
Usage:
    python diagnose_openai.py
"""
import os
import sys
import importlib
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("openai_diagnose")

def check_openai_setup():
    """Check OpenAI setup and configuration."""
    logger.info("Checking OpenAI setup...")
    
    # Check if OpenAI is installed
    try:
        import openai
        logger.info(f"OpenAI package is installed, version: {openai.__version__}")
    except ImportError:
        logger.error("OpenAI package is not installed!")
        return False
    
    # Check for proxy settings in environment
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    for var in proxy_vars:
        if var in os.environ:
            logger.warning(f"Found proxy setting: {var}={os.environ[var]}")
    
    # Check if the new client can be created
    try:
        client = openai.OpenAI(api_key="dummy_key_for_testing")
        logger.info("Successfully created OpenAI client instance")
    except Exception as e:
        logger.error(f"Failed to create OpenAI client: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    
    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if api_key:
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***masked***"
        logger.info(f"OPENAI_API_KEY is set: {masked_key}")
    else:
        logger.warning("OPENAI_API_KEY environment variable is not set")
    
    # Output all environment variables that might affect OpenAI
    logger.info("Environment variables that might affect OpenAI:")
    for key, value in os.environ.items():
        if any(x in key.lower() for x in ['proxy', 'openai', 'api', 'http', 'https']):
            masked_value = value
            if 'key' in key.lower() and value:
                masked_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***masked***"
            logger.info(f"  {key}={masked_value}")
    
    return True

def main():
    """Main function."""
    logger.info("Starting OpenAI diagnostics...")
    
    success = check_openai_setup()
    
    if success:
        logger.info("OpenAI setup checks completed successfully")
    else:
        logger.error("OpenAI setup checks failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 