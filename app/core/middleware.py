from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def register_middleware(app: FastAPI) -> None:
    """
    Configures and registers middleware for the application.
    """
    
    # Define allowed origins
    # In production, this should ideally be strict (e.g., specific Netlify domains).
    origins = [
        "http://localhost:5173",  # Vite Local Development
        "http://localhost:4173",  # Vite Local Preview
        "http://localhost:8080",  # Alternative Local Port
        "*"                       # Allow all origins (Simplifies development/staging)
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )