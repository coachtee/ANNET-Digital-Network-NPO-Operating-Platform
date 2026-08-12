from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str

from apps.accounts.forms import RegisterForm
from apps.accounts.models import User
from apps.audit.services import log_action


def register(request):
    if request.user.is_authenticated:
        return redirect("organisations:workspace_home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.save()
            _send_verification_email(request, user)
            login(request, user)
            log_action("user.registered", actor=user, obj=user)
            messages.success(
                request,
                "Welcome. We've sent a verification link to your email — you can start setting up "
                "your organisation right away.",
            )
            return redirect("organisations:create")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def _send_verification_email(request, user):
    token = urlsafe_base64_encode(force_bytes(user.pk)) + "-" + str(user.email_verification_token)
    verify_url = request.build_absolute_uri(reverse("accounts:verify_email", args=[token]))
    subject = "Verify your email — Bohlale Impact"
    body = render_to_string("accounts/email/verify_email.txt", {"user": user, "verify_url": verify_url})
    send_mail(subject, body, None, [user.email], fail_silently=True)


def verify_email(request, token):
    try:
        uidb64, verification_token = token.split("-", 1)
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User, pk=uid, email_verification_token=verification_token)
    except (ValueError, TypeError):
        messages.error(request, "That verification link is invalid or has expired.")
        return redirect("sitepublic:home")

    user.email_verified = True
    user.save(update_fields=["email_verified"])
    messages.success(request, "Your email address has been verified.")
    if request.user.is_authenticated:
        return redirect("organisations:workspace_home")
    return redirect("accounts:login")


@login_required
def resend_verification(request):
    if not request.user.email_verified:
        _send_verification_email(request, request.user)
        messages.success(request, "Verification email sent.")
    return redirect("organisations:workspace_home")


@login_required
def post_login_redirect(request):
    # Kiosk devices never use the standard login form — they reach the
    # restricted check-in flow via a tokenised URL (see apps.attendance).
    # This flag exists purely as a hard-block if a kiosk-only account were
    # ever used to sign in through the normal form.
    if request.user.is_kiosk_only:
        from django.contrib.auth import logout
        logout(request)
        messages.error(request, "This account cannot access the standard platform login.")
        return redirect("sitepublic:home")
    if request.user.is_platform_admin or request.user.network_staff_roles.exists():
        return redirect("networks:dashboard")
    if request.user.active_memberships.exists():
        return redirect("organisations:workspace_home")
    return redirect("organisations:create")
