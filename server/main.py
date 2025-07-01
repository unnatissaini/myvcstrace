from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from server.routes import auth, repositories 
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from server.routes import ui
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from server.routes import commits

class AuthHeaderFromCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "authorization" not in request.headers:
            auth_cookie = request.cookies.get("Authorization")
            if auth_cookie:
                request.headers.__dict__["_list"].append(
                    (b"authorization", auth_cookie.encode())
                )
        response = await call_next(request)
        return response



app = FastAPI(title="MyVCS ")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="mysecretkey")
app.include_router(auth.router, prefix="", tags=["Authentication"])
app.include_router(repositories.router, prefix="", tags=["Repositories"])
app.include_router(ui.router)
app.add_middleware(AuthHeaderFromCookieMiddleware)
app.include_router(commits.router)


