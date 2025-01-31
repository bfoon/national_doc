from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from .models import Token, TokenLog, UserRisk
from django.utils.timezone import now
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
import json
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.paginator import Paginator



@login_required
def token_management_view(request):
    """
    Renders the token management page with dashboard statistics and transaction history.
    """
    # Get basic data
    logs = TokenLog.objects.all().order_by('-created_at')
    users = User.objects.all()

    # Pagination
    paginator = Paginator(logs, 10)  # Show 10 logs per page
    page_number = request.GET.get('page')
    token_logs = paginator.get_page(page_number)

    # Calculate dashboard statistics
    total_tokens = Token.objects.count()
    used_tokens = Token.objects.filter(is_used=True).count()
    pending_tokens = Token.objects.filter(is_used=False).count()
    total_amount = Token.objects.aggregate(
        total=Sum('amount'))['total'] or 0

    # Get chart data for the last 6 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    # Monthly token generation data
    monthly_tokens = Token.objects.filter(
        created_at__range=(start_date, end_date)
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id'),
        amount=Sum('amount')
    ).order_by('month')

    # Prepare chart data
    chart_labels = []
    chart_tokens = []
    chart_amounts = []

    for entry in monthly_tokens:
        chart_labels.append(entry['month'].strftime('%b %Y'))
        chart_tokens.append(entry['count'])
        chart_amounts.append(float(entry['amount']) if entry['amount'] else 0)

    context = {
        "users": users,
        "token_logs": token_logs,  # This is now paginated
        # Dashboard stats
        "total_tokens": total_tokens,
        "used_tokens": used_tokens,
        "pending_tokens": pending_tokens,
        "total_amount": total_amount,
        # Chart data
        "chart_labels": json.dumps(chart_labels),
        "chart_tokens": json.dumps(chart_tokens),
        "chart_amounts": json.dumps(chart_amounts)
    }

    return render(request, "finance/token_management.html", context)

@login_required
def generate_token(request):
    """
    Generates a token for a selected user and an amount.
    """
    if request.method == "POST":
        user_id = request.POST.get("user")
        amount = request.POST.get("amount")

        if not user_id or not amount:
            return JsonResponse({"error": "User and amount are required."}, status=400)

        user = User.objects.get(id=user_id)
        token = Token.objects.create(user=user, amount=amount)

        return JsonResponse({"success": True, "token": token.token, "amount": token.amount})

    return JsonResponse({"error": "Invalid request method."}, status=405)

@csrf_exempt
def verify_token(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        token_value = data.get("token")
        ip_address = get_client_ip(request)

        if not token_value:
            return JsonResponse({"error": "Token is required"}, status=400)

        try:
            with transaction.atomic():
                token = Token.objects.select_for_update().get(token=token_value, is_used=False)

                # Mark the token as verified and create a log
                TokenLog.objects.create(token=token, ip_address=ip_address, activity="Token verified")
                return JsonResponse({"success": True, "token": token.token, "amount": token.amount})

        except Token.DoesNotExist:
            # Log failed attempt
            risk, created = UserRisk.objects.get_or_create(user=request.user)
            risk.increment_failed_attempts()

            if risk.is_risky:
                return JsonResponse({"error": "Account is marked as risky due to multiple failed attempts."}, status=403)

            TokenLog.objects.create(token=None, ip_address=ip_address, activity=f"Failed attempt with token {token_value}")
            return JsonResponse({"error": "Invalid or already used token."}, status=404)

    return HttpResponseForbidden("Invalid request method.")

@csrf_exempt
def complete_service(request, token_id):
    token = get_object_or_404(Token, id=token_id, is_used=False)
    token.mark_as_used()
    TokenLog.objects.create(token=token, ip_address=get_client_ip(request), activity="Service completed")
    return JsonResponse({"success": True, "message": "Service completed and token marked as used."})

def get_client_ip(request):
    """Helper function to get the client's IP address."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
