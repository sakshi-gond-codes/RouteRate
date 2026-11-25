from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import ActivityLog

from .forms import LoginForm, StyledPasswordChangeForm, UserForm
from .models import User
from .permissions import admin_required


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        ActivityLog.record(self.request.user, "login", "Signed in")
        return response


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
        return redirect("core:dashboard")
    return render(request, "core/form_page.html", {
        "form": form, "title": "Change password", "submit_label": "Update password",
        "cancel_url": "core:dashboard",
    })


@admin_required
def user_list(request):
    users = User.objects.annotate(deck_count=Count("uploaded_decks")).order_by("role", "first_name")
    return render(request, "accounts/user_list.html", {"users": users, "roles": User.Role})


@admin_required
def user_create(request):
    form = UserForm(request.POST or None, current_user=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        ActivityLog.record(request.user, "user", f"Created user {user.username} ({user.get_role_display()})")
        messages.success(request, f"User {user.username} created.")
        return redirect("accounts:user_list")
    return render(request, "core/form_page.html", {
        "form": form, "title": "Add user", "submit_label": "Create user", "cancel_url": "accounts:user_list",
    })


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user, current_user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.record(request.user, "user", f"Updated user {user.username}")
        messages.success(request, f"User {user.username} updated.")
        return redirect("accounts:user_list")
    return render(request, "core/form_page.html", {
        "form": form, "title": f"Edit user: {user.username}", "submit_label": "Save changes",
        "cancel_url": "accounts:user_list",
    })
