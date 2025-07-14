from starlette.middleware.sessions import SessionMiddleware
from server.routes import auth, repositories , ui , commits, superadmin
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

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


class SuperAdminProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/superadmin") or request.url.path.startswith("/api/superadmin"):
            if not request.session.get("superadmin_authenticated"):
                return RedirectResponse(url="/superadmin-login", status_code=303)
        return await call_next(request)

app = FastAPI(title="MyVCS ")
app.add_middleware(SessionMiddleware, secret_key="mysecretkey")
app.add_middleware(AuthHeaderFromCookieMiddleware)


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="", tags=["Authentication"])
app.include_router(repositories.router, prefix="", tags=["Repositories"])
app.include_router(ui.router)

app.include_router(commits.router)
app.include_router(superadmin.router)


