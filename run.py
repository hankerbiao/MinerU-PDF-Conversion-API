import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MinerU PDF Conversion API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "app:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload,
        workers=args.workers
    ) 