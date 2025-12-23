from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def register_middleware(app: FastAPI) -> None:
    """
    Configures and registers application-level middleware.
    
    Currently handles Cross-Origin Resource Sharing (CORS) to define 
    which external domains are permitted to interact with the API.
    """
    
    # List of origins permitted to make cross-site HTTP requests.
    # Note: Using "*" (wildcard) allows all origins, which is standard for 
    # public APIs or early-stage development but should be restricted in 
    # high-security production environments.
    origins = [
        "http://localhost:5173",  # Standard Vite development port
        "http://localhost:4173",  # Vite preview port
        "http://localhost:8080",  # Legacy/Alternative local port
        "*"                       # Open access for development/staging flexibility
    ]

    app.add_middleware(
        CORSMiddleware,
        # Permitted origins for browser-based security headers
        allow_origins=origins,
        # Allows cookies and authentication headers to be included in cross-origin requests
        allow_credentials=True,
        # Permitted HTTP methods (GET, POST, PUT, DELETE, etc.)
        allow_methods=["*"],
        # Permitted HTTP headers (Content-Type, Authorization, etc.)
        allow_headers=["*"],
    )