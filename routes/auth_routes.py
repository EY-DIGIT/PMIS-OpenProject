"""
Auth routes - delegates to existing api/auth.py for now.
"""

try:
    from ..api.auth import router
except ImportError:
    from api.auth import router

# Re-export the existing router
