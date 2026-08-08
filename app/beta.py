"""The beta latch.

During the beta, strangers sit at the terminal. The UI puts a mask over
prompts, tools and agents — that is the visible half. This here is the
effective one: without it anyone could walk past the mask with `curl`.

Why this is serious: `PUT /api/v1/tools/config` accepts arbitrary `command`
and `args` values. The validation in `app/tools/registry.py` only checks data
types ("is it a string?"), not contents — and after saving, the registry
starts the registered programs. That is remote code execution as the
service's user, not merely a changed setting.

A middleware instead of dependencies on every route: one place instead of
six, and a new write-access route cannot accidentally stay open, because
blocking here happens by path and method, not per function.

To undo: `features.beta_lock: false` in config.yaml.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# (Method, path). If the path ends in "/", it counts as a prefix — otherwise
# exact. `POST /api/v1/jobs` is deliberately listed as an EXACT path:
# `/jobs/{id}/cancel` starts the same way, and anyone may cancel a running job.
GESPERRT = (
    ("PUT",    "/api/v1/tools/config"),
    ("PUT",    "/api/v1/system-prompt"),
    ("PUT",    "/api/v1/images/config"),
    ("PUT",    "/api/v1/agents/"),
    ("DELETE", "/api/v1/agents/"),
    ("POST",   "/api/v1/jobs"),
    ("DELETE", "/api/v1/jobs/"),
    # The browser sign-in connects third-party services to the owner's
    # accounts — not for strangers' hands. The GET callback stays open: without a state
    # previously created via POST, it exchanges nothing.
    ("POST",   "/api/v1/tools/oauth/start"),
    ("DELETE", "/api/v1/tools/oauth/"),
    ("PUT",    "/api/v1/tools/servers/"),
    ("DELETE", "/api/v1/tools/servers/"),
    # The folder dialog opens a real window on the owner's machine and grants
    # the model access to a folder. Strangers at the terminal have no business
    # popping up Finder — the path field stays open to them, and what it sets
    # is checked before it is stored.
    ("POST",   "/api/v1/filesystem/choose-folder"),
)

# English, because it is the same line that also appears in the UI.
GRUND = "Only available in the full version."


def ist_gesperrt(verfahren: str, weg: str) -> bool:
    for v, muster in GESPERRT:
        if verfahren != v:
            continue
        if muster.endswith("/"):
            if weg.startswith(muster):
                return True
        elif weg.rstrip("/") == muster:
            return True
    return False


class BetaRiegel(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if ist_gesperrt(request.method, request.url.path):
            return JSONResponse({"detail": GRUND}, status_code=403)
        return await call_next(request)
