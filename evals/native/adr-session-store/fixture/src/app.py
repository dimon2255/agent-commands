"""shop-api entry point."""

from fastapi import Cookie, FastAPI, HTTPException
from session import get_session

app = FastAPI(title="shop-api")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/me")
def me(shop_sid: str | None = Cookie(default=None)) -> dict:
    session = get_session(shop_sid or "")
    if session is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return {"user_id": session.user_id, "roles": session.roles}
