"""Server runner for both development and production"""
import uvicorn
import os

if __name__ == "__main__":
    # Get port from environment variable (for production) or default to 8000 (for dev)
    port = int(os.getenv("PORT", 8000))

    # Disable reload in production for stability
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=not is_production,
        log_level="info",
    )

