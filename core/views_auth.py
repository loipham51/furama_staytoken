import datetime
import hashlib
import logging
import secrets
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import connection
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .forms import OTPStartForm
from .models import AppUser

OTP_TTL_MINUTES = 10
OTP_LENGTH = 6
OTP_WINDOW_SECONDS = getattr(settings, "ST_OTP_WINDOW_SECONDS", 300)
OTP_LIMIT_EMAIL = getattr(settings, "ST_OTP_LIMIT_PER_EMAIL", 5)
OTP_LIMIT_IP = getattr(settings, "ST_OTP_LIMIT_PER_IP", 15)

logger = logging.getLogger(__name__)


def _create_otp(email: str, purpose: str = "login"):
    code = f"{secrets.randbelow(10**OTP_LENGTH):06d}"
    expires = timezone.now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)
    otp_id = uuid.uuid4()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO otp_login (id, email, phone, code, purpose, attempts, max_attempts, expires_at, created_at)
            VALUES (%s, %s, NULL, %s, %s, 0, 5, %s, NOW())
            """,
            [str(otp_id), email, code, purpose, expires],
        )
    return code, expires


def _rate_key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"otp:{kind}:{digest}"


def _increment_counter(key: str) -> int:
    if OTP_WINDOW_SECONDS <= 0:
        return 1
    cache.add(key, 0, OTP_WINDOW_SECONDS)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, OTP_WINDOW_SECONDS)
        return 1


def _otp_request_allowed(email: str, ip: str) -> bool:
    exceeded = False
    if email:
        if _increment_counter(_rate_key("email", email)) > OTP_LIMIT_EMAIL:
            exceeded = True
    if ip:
        if _increment_counter(_rate_key("ip", ip)) > OTP_LIMIT_IP:
            exceeded = True
    return not exceeded


def _send_email_code(to_email: str, code: str) -> None:
    subject = "Ma dang nhap Furama StayToken"
    body = (
        f"Ma OTP cua ban la: {code}\n"
        f"Ma het han sau {OTP_TTL_MINUTES} phut."
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)


def _safe_next_url(request, candidate: str | None) -> str | None:
    if not candidate:
        return None
    if url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return None


@require_http_methods(["GET", "POST"])
def auth_start(request):
    if request.method == "GET":
        form = OTPStartForm(initial={"next": request.GET.get("next")})
        return render(request, "auth_start.html", {"form": form})

    form = OTPStartForm(request.POST)
    if not form.is_valid():
        return render(request, "auth_start.html", {"form": form}, status=400)

    email = form.cleaned_data["email"].strip().lower()
    client_ip = request.META.get("REMOTE_ADDR") or ""
    safe_next = _safe_next_url(request, form.cleaned_data.get("next"))

    if not _otp_request_allowed(email, client_ip):
        context = {
            "form": form,
            "error": "Bạn yêu cầu mã quá nhanh. Vui lòng thử lại sau ít phút.",
        }
        return render(request, "auth_start.html", context, status=429)

    code, _ = _create_otp(email=email, purpose="login")
    try:
        _send_email_code(email, code)
    except Exception as exc:  # pragma: no cover - depends on email backend
        logger.exception("Failed to send OTP to %s", email)
        context = {
            "form": form,
            "error": "Không thể gửi email OTP vào lúc này. Vui lòng thử lại sau.",
        }
        return render(request, "auth_start.html", context, status=500)

    message = f"Đã gửi mã OTP tới {email}."
    return render(
        request,
        "auth_verify.html",
        {"email": email, "message": message, "next": safe_next},
    )


@require_http_methods(["POST"])
def auth_verify(request):
    code = (request.POST.get("code") or "").strip()
    email = (request.POST.get("email") or "").strip().lower() or None
    safe_next = _safe_next_url(request, request.POST.get("next"))

    base_context = {"email": email, "next": safe_next}
    if not code or not email:
        context = {**base_context, "error": "Thiếu thông tin. Vui lòng thử lại."}
        return render(request, "auth_verify.html", context, status=400)

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, code, attempts, max_attempts, expires_at, used_at
            FROM otp_login
            WHERE purpose='login' AND email=%s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [email],
        )
        row = cur.fetchone()

    if not row:
        context = {**base_context, "error": "Không tìm thấy mã OTP. Hãy gửi mã mới."}
        return render(request, "auth_verify.html", context, status=404)

    otp_id, db_code, attempts, max_attempts, expires_at, used_at = row

    if used_at:
        context = {**base_context, "error": "Mã đã sử dụng. Hãy yêu cầu mã mới."}
        return render(request, "auth_verify.html", context, status=400)
    if timezone.now() > expires_at:
        context = {**base_context, "error": "Mã đã hết hạn. Gửi lại mã mới."}
        return render(request, "auth_verify.html", context, status=400)
    if attempts >= max_attempts:
        context = {**base_context, "error": "Nhập sai quá số lần. Gửi lại mã mới."}
        return render(request, "auth_verify.html", context, status=400)
    if code != db_code:
        with connection.cursor() as cur:
            cur.execute("UPDATE otp_login SET attempts = attempts + 1 WHERE id=%s", [otp_id])
        context = {**base_context, "error": "Mã không đúng."}
        return render(request, "auth_verify.html", context, status=400)

    with connection.cursor() as cur:
        cur.execute("UPDATE otp_login SET used_at = NOW() WHERE id=%s", [otp_id])

    try:
        user = AppUser.objects.get(email=email)
    except AppUser.DoesNotExist:
        new_id = uuid.uuid4()
        display_name = f"Khach Furama {get_random_string(4)}"
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_user (id, email, phone, full_name, is_active, created_at, updated_at)
                VALUES (%s, %s, NULL, %s, TRUE, NOW(), NOW())
                """,
                [str(new_id), email, display_name],
            )
        user = AppUser.objects.get(id=new_id)

    request.session["user_id"] = str(user.id)
    request.session.set_expiry(60 * 30)
    return redirect(safe_next or reverse("me"))


def logout(request):
    request.session.flush()
    return redirect("/")
