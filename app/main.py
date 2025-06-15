from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import Dict, Any
import json
from datetime import datetime, timezone

from app.database import create_db_and_tables
from app.api import auth, location, emergency
# from app.config import settings
from app.core.geofencing import is_within_oau_campus

# Lifespan manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # await create_db_and_tables()
    # print("Database tables created")
    print("Application starting up")
    yield
    # Shutdown
    print("Application shutting down")

app = FastAPI(
    title="OAU Campus Bike Visibility API",
    description="Real-time location visibility for campus bike transportation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(location.router, prefix="/api/location", tags=["Location"])
app.include_router(emergency.router, prefix="/api/emergency", tags=["Emergency"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"WebSocket disconnected: {session_id}")
    
    async def broadcast_location_update(self, data: dict[str, Any]):
        disconnected = []
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(data, default=str))
            except Exception as e:
                print(f"Error broadcasting to {session_id}: {e}")
                disconnected.append(session_id)
        
        # Clean up disconnected clients
        for session_id in disconnected:
            self.disconnect(session_id)
    
    async def send_to_session(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(
                    json.dumps(data, default=str)
                )
            except Exception as e:
                print(f"Error sending to {session_id}: {e}")
                self.disconnect(session_id)

manager = ConnectionManager()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(json.dumps({
                "type": "heartbeat",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error for {session_id}: {e}")
        manager.disconnect(session_id)

@app.get("/")
async def root():
    return {
        "message": "OAU Campus Bike Visibility API",
        "status": "active",
        "campus": "Obafemi Awolowo University",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_connections": len(manager.active_connections)
    }

# Make manager available to other modules
app.state.websocket_manager = manager