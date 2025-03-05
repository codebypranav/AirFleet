#!/usr/bin/env python
"""
Debug OpenAI Client proxies issue for AirFleet

This script diagnoses the specific 'proxies' parameter issue.
"""
import os
import sys
import importlib
import logging
import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("openai_debug")

def inspect_openai_client_init():
    """Inspect the OpenAI client initialization process."""
    try:
        import openai
        logger.info(f"OpenAI version: {openai.__version__}")
        
        # Check for proxy settings in environment
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                      'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
        
        for var in proxy_vars:
            if var in os.environ:
                logger.info(f"Found proxy setting: {var}={os.environ[var]}")
                
        # Remove proxy environment variables
        for var in proxy_vars:
            if var in os.environ:
                logger.info(f"Removing environment variable: {var}")
                del os.environ[var]
        
        # Inspect OpenAI class and its base classes
        logger.info("Inspecting OpenAI client hierarchy:")
        mro = openai.OpenAI.__mro__
        for cls in mro:
            logger.info(f"Class in hierarchy: {cls.__module__}.{cls.__name__}")
            
        # Examine the __init__ methods and their parameters
        logger.info("\nExamining __init__ methods in the hierarchy:")
        for cls in mro:
            if '__init__' in cls.__dict__:
                init_method = cls.__dict__['__init__']
                sig = inspect.signature(init_method)
                logger.info(f"{cls.__module__}.{cls.__name__}.__init__ parameters: {sig}")
                
        # Try to trace where proxies might be coming from
        logger.info("\nExamining where proxies parameter might come from:")
        try:
            # First, get the constructor path
            client_code_path = inspect.getsourcefile(openai.OpenAI)
            logger.info(f"OpenAI client code location: {client_code_path}")
            
            # Now try initializing step by step to find where proxies is being added
            logger.info("Trying direct initialization:")
            try:
                minimal_client = openai.OpenAI(api_key="test_key")
                logger.info("Direct minimal initialization succeeded - no proxies added")
            except Exception as e:
                logger.error(f"Direct minimal initialization failed: {str(e)}")
                
                # Let's try to look at the HTTP client creation
                http_client_class = None
                for attr_name in dir(openai._base_client):
                    attr = getattr(openai._base_client, attr_name)
                    if isinstance(attr, type) and "httpx" in attr_name.lower():
                        http_client_class = attr
                        break
                
                if http_client_class:
                    logger.info(f"Found HTTP client class: {http_client_class.__name__}")
                    try:
                        # Try to see what happens in HTTP client initialization
                        sig = inspect.signature(http_client_class.__init__)
                        logger.info(f"HTTP client __init__ signature: {sig}")
                    except Exception as e:
                        logger.error(f"Failed to inspect HTTP client: {e}")
        except Exception as e:
            logger.error(f"Failed to trace proxies: {e}")
            
        # Try to initialize with workaround
        logger.info("\nAttempting to initialize with explicit removal of proxies:")
        try:
            # Create a deep copy to avoid changing the original
            import copy
            kwargs = {"api_key": "test_key"}
            
            # Manually remove proxies from kwargs if present
            if 'proxies' in kwargs:
                del kwargs['proxies']
                
            # Try to get the _base_client module
            client = openai.OpenAI(**kwargs)
            logger.info("Workaround initialization succeeded")
        except Exception as e:
            logger.error(f"Workaround initialization failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Overall inspection failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    inspect_openai_client_init() 