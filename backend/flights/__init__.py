"""
Flights app initialization
"""
import logging

logger = logging.getLogger(__name__)

# Apply OpenAI patches at module load time
try:
    from .openai_patch import apply_openai_patches
    apply_openai_patches()
    logger.info("Applied OpenAI patches during app initialization")
except Exception as e:
    logger.error(f"Failed to apply OpenAI patches during app initialization: {e}")
