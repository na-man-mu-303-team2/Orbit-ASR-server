from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .models import CreateSessionResponse, HealthResponse, WebRtcAnswer, WebRtcOffer
from .session import SessionManager


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    manager = SessionManager(resolved_settings)
    app = FastAPI(title="Orbit Realtime Gateway", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.sessions = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="realtime-gateway",
            nimClient=resolved_settings.nim_client,  # type: ignore[arg-type]
        )

    @app.post("/api/realtime/sessions", response_model=CreateSessionResponse)
    async def create_session() -> CreateSessionResponse:
        session = manager.create_session()
        return CreateSessionResponse(
            sessionId=session.session_id,
            status="created",
            eventsUrl=f"/api/realtime/sessions/{session.session_id}/events",
        )

    @app.post("/api/realtime/sessions/{session_id}/offer", response_model=WebRtcAnswer)
    async def handle_offer(session_id: str, offer: WebRtcOffer) -> WebRtcAnswer:
        session = manager.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND"}})
        return await session.handle_offer(offer.sdp, offer.type)

    @app.websocket("/api/realtime/sessions/{session_id}/events")
    async def session_events(websocket: WebSocket, session_id: str) -> None:
        session = manager.get_session(session_id)
        if session is None:
            await websocket.close(code=4404)
            return

        await session.register_websocket(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await session.unregister_websocket(websocket)

    return app


app = create_app()
