from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from .models import AppUser
from django.urls import reverse
from urllib.parse import urlencode

def login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get("user_id"):
            # Check if this is an API request expecting JSON
            wants_json = (
                'application/json' in request.headers.get('Accept', '') or 
                request.GET.get('format') == 'json' or
                request.content_type == 'application/json'
            )
            
            if wants_json:
                return JsonResponse({"error": "Authentication required"}, status=401)
            
            return redirect(f"/auth/start?next={request.get_full_path()}")
        return view_func(request, *args, **kwargs)
    return _wrapped

def get_current_user(request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    try:
        return AppUser.objects.get(id=uid)
    except AppUser.DoesNotExist:
        return None

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # Chỉ cho qua nếu user đăng nhập Django Admin và là staff/superuser
        if getattr(request, "user", None) and request.user.is_authenticated:
            if request.user.is_staff or request.user.is_superuser:
                return view_func(request, *args, **kwargs)

        # Chưa đăng nhập/không đủ quyền -> chuyển về /admin/login/?next=...
        login_url = reverse("admin:login")  # "/admin/login/"
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
    return _wrapped
