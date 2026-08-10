"""Turns away state-changing requests from foreign web pages.

The service listens on loopback, but a browser sits on the same machine:
any web page a user happens to have open may fire requests at
``http://127.0.0.1``. Reading answers is already blocked by the browser's
same-origin rules — but a fire-and-forget POST to an endpoint that needs
no body (stop the model server, open a folder) would still go through.

The browser marks every cross-site request with an ``Origin`` header it
does not let pages forge. So the rule is plain: a state-changing request
that carries an Origin must carry one matching the host it talks to.
Requests without an Origin (the service's own provider calls, curl,
native code) pass — they are not browsers, and a browser is the only
thing this guard is about.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Methods that change state. GET/HEAD/OPTIONS stay open — their answers
# are protected by the browser itself, and blocking them would break
# nothing an attacker cares about but plenty a user does.
SCHREIBENDE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class Herkunftswaechter(BaseHTTPMiddleware):
    """Rejects writes whose Origin names a different site than the host."""

    async def dispatch(self, request: Request, call_next):
        if request.method in SCHREIBENDE:
            herkunft = request.headers.get("origin")
            if herkunft and herkunft.lower() != "null":
                wirt = request.headers.get("host", "")
                if urlsplit(herkunft).netloc.lower() != wirt.lower():
                    return JSONResponse(
                        {"detail": "cross-origin write rejected"}, status_code=403
                    )
        return await call_next(request)
