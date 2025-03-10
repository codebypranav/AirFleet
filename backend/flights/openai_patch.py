"""
OpenAI Client Monkey Patch

This module provides a patch for the OpenAI client to prevent proxy-related issues.
"""
import logging
import inspect
import importlib
import os
import sys

logger = logging.getLogger(__name__)

def apply_openai_patches():
    """
    Apply patches to the OpenAI module to prevent proxy-related errors.
    
    This function monkey patches the OpenAI.AsyncClient.__init__ and OpenAI.Client.__init__
    methods to filter out unsupported parameters like 'proxies'.
    """
    try:
        import openai
        import openai._client
        
        logger.info("Applying OpenAI client patches to fix proxies issue")
        
        # Save original __init__ methods
        original_async_init = openai.AsyncClient.__init__
        original_sync_init = openai.Client.__init__
        
        # Create patched init methods
        def patched_async_init(self, *args, **kwargs):
            # Remove 'proxies' from kwargs if present
            if 'proxies' in kwargs:
                logger.info("Removing unsupported 'proxies' parameter from AsyncClient.__init__")
                kwargs.pop('proxies')
            return original_async_init(self, *args, **kwargs)
        
        def patched_sync_init(self, *args, **kwargs):
            # Remove 'proxies' from kwargs if present
            if 'proxies' in kwargs:
                logger.info("Removing unsupported 'proxies' parameter from Client.__init__")
                kwargs.pop('proxies')
            return original_sync_init(self, *args, **kwargs)
        
        # Apply patches
        openai.AsyncClient.__init__ = patched_async_init
        openai.Client.__init__ = patched_sync_init
        
        logger.info("Successfully applied OpenAI client patches")
        return True
    except Exception as e:
        logger.error(f"Failed to apply OpenAI patches: {str(e)}")
        return False


def clean_openai_environment():
    """
    Clean environment variables that might affect OpenAI client's proxy behavior.
    """
    import os
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    
    cleared = []
    for var in proxy_vars:
        if var in os.environ:
            logger.info(f"Clearing proxy environment variable: {var}")
            cleared.append(var)
            del os.environ[var]
    
    if cleared:
        logger.info(f"Cleared proxy environment variables: {', '.join(cleared)}")
    else:
        logger.info("No proxy environment variables found to clear")
    
    return cleared


def create_safe_openai_client(api_key=None):
    """
    Create an OpenAI client safely, handling the proxies issue.
    
    Args:
        api_key: The OpenAI API key to use. If None, will use the default from environment.
        
    Returns:
        An instance of openai.OpenAI client that will work without proxy issues
    """
    # Clean environment variables first
    clean_openai_environment()
    
    try:
        # We'll create our own clean OpenAI client bypassing the problematic initialization
        logger.info("Creating a fresh OpenAI client with minimal parameters")
        
        # Import directly from the openai module using a different import style
        # to avoid any potential issues
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import openai
        
        # Force a reload of the module
        importlib.reload(openai)
        
        # Create a minimal, clean client with just the API key
        if api_key:
            # Use the most direct method
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
        else:
            # Fall back to default API key
            from openai import OpenAI
            client = OpenAI()
            
        logger.info("Successfully created clean OpenAI client")
        return client
    except Exception as e:
        logger.error(f"Error creating OpenAI client: {str(e)}")
        # Last resort approach - direct import and minimal parameters
        try:
            logger.info("Attempting last resort OpenAI client creation")
            # Direct import
            from openai import OpenAI
            
            # Create the client with just an API key
            if api_key:
                client = OpenAI(api_key=api_key)
            else:
                client = OpenAI()
                
            logger.info("Last resort client creation succeeded")
            return client
        except Exception as e2:
            logger.error(f"Even last resort OpenAI client creation failed: {str(e2)}")
            raise RuntimeError(f"Failed to create OpenAI client: {str(e)} and then {str(e2)}") 