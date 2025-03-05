#!/usr/bin/env python
"""
Railway-specific OpenAI diagnostics

This script is designed to run on Railway to help diagnose OpenAI client issues.
"""
import os
import sys
import logging
import json
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("railway_diagnose")

def run_diagnostics():
    """Run Railway-specific diagnostics."""
    results = {
        "environment": {},
        "openai_version": None,
        "openai_client_creation": {
            "success": False,
            "error": None
        },
        "proxy_variables": []
    }
    
    # Check environment
    logger.info("Checking environment...")
    is_railway = "RAILWAY" in os.environ or "RAILWAY_ENVIRONMENT" in os.environ
    results["environment"]["is_railway"] = is_railway
    
    # Check system
    results["environment"]["system"] = sys.platform
    results["environment"]["python_version"] = sys.version
    
    # Check OpenAI version
    try:
        import openai
        version = openai.__version__
        logger.info(f"OpenAI version: {version}")
        results["openai_version"] = version
    except ImportError:
        logger.error("OpenAI package not installed")
        results["openai_version"] = "Not installed"
    except Exception as e:
        logger.error(f"Error checking OpenAI version: {str(e)}")
        results["openai_version"] = f"Error: {str(e)}"
    
    # Check proxy environment variables
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    for var in proxy_vars:
        if var in os.environ:
            logger.info(f"Found proxy variable: {var}={os.environ[var]}")
            results["proxy_variables"].append({
                "name": var,
                "value": os.environ[var]
            })
    
    # Try to create OpenAI client
    if results["openai_version"] not in ["Not installed", None]:
        try:
            # Approach 1: Direct minimal initialization
            logger.info("Attempting direct minimal initialization...")
            from openai import OpenAI
            client = OpenAI(api_key="sk-dummy-key-for-testing")
            logger.info("Direct initialization succeeded")
            results["openai_client_creation"]["success"] = True
        except Exception as e1:
            logger.error(f"Direct initialization failed: {str(e1)}")
            results["openai_client_creation"]["error"] = str(e1)
            
            # Approach 2: Try after clearing proxy variables
            try:
                logger.info("Clearing proxy variables and trying again...")
                for var in proxy_vars:
                    if var in os.environ:
                        del os.environ[var]
                
                import importlib
                importlib.reload(openai)
                
                client = OpenAI(api_key="sk-dummy-key-for-testing")
                logger.info("Initialization after clearing proxies succeeded")
                results["openai_client_creation"]["success"] = True
                results["openai_client_creation"]["method"] = "After clearing proxies"
            except Exception as e2:
                logger.error(f"Second approach failed: {str(e2)}")
                results["openai_client_creation"]["second_error"] = str(e2)
    
    # Check the openai base client module
    try:
        import openai._base_client
        import inspect
        
        # Get the init signature of BaseClient
        base_client_sig = inspect.signature(openai._base_client.BaseClient.__init__)
        logger.info(f"BaseClient.__init__ signature: {base_client_sig}")
        results["base_client_signature"] = str(base_client_sig)
        
        # Get the parameters
        params = list(base_client_sig.parameters.keys())
        logger.info(f"BaseClient.__init__ parameters: {params}")
        results["base_client_parameters"] = params
        
        # Check if proxies is a parameter
        has_proxies = 'proxies' in params
        logger.info(f"BaseClient has 'proxies' parameter: {has_proxies}")
        results["base_client_has_proxies"] = has_proxies
        
    except Exception as e:
        logger.error(f"Error inspecting BaseClient: {str(e)}")
        results["base_client_inspection_error"] = str(e)
    
    # Output results as JSON
    logger.info("Diagnostics complete")
    print("\n\nDIAGNOSTICS RESULTS:")
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    try:
        print("Starting Railway OpenAI diagnostics...")
        results = run_diagnostics()
        print("Diagnostics completed successfully")
        
        # Also write to a file for persistent access
        with open("railway_openai_diagnostics.json", "w") as f:
            json.dump(results, f, indent=2)
            
    except Exception as e:
        print(f"Error running diagnostics: {str(e)}")
        traceback.print_exc()
        sys.exit(1) 