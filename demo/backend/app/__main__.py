import uvicorn

from app.core.config import load_settings

if __name__ == "__main__":
    cfg = load_settings()
    uvicorn.run(
        "app.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        workers=1,
        ws_max_size=cfg.server.websocket_max_message_bytes,
        access_log=False,
    )
