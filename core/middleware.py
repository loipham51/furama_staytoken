import re
from urllib.parse import urlencode  # <-- dùng urlencode thay urlquote
from django.shortcuts import redirect
from django.http import JsonResponse

class RequireLoginMiddleware:
    """
    Buộc đăng nhập cho các trang người dùng, trừ allowlist.
    Dựa trên session request.session['user_id'].
    JSON/API -> trả 401, còn lại -> redirect kèm ?next=...
    """

    ALLOWLIST = [
        r"^/$",
        r"^/auth/",
        r"^/admin/",
        r"^/adv1/",
        r"^/static/",
        r"^/media/",
        r"^/healthz$",
        r"^/claim/",
        r"^/qr/",
        r"^/pos/api",
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.allow_patterns = [re.compile(p) for p in self.ALLOWLIST]

    def __call__(self, request):
        path = request.path or "/"

        # allowlist
        for pat in self.allow_patterns:
            if pat.match(path):
                return self.get_response(request)

        # đã đăng nhập?
        if request.session.get("user_id"):
            return self.get_response(request)

        # chưa đăng nhập
        wants_json = (
            request.headers.get("Accept", "").lower().startswith("application/json")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or path.startswith("/api/")
            or request.GET.get("format") == "json"
        )
        if wants_json:
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

        # redirect kèm next (dùng urlencode an toàn)
        next_param = request.get_full_path()  # giữ nguyên query hiện tại nếu có
        query = urlencode({"next": next_param})
        return redirect(f"/auth/start?{query}")
