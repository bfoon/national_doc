from .models import Notification
def notifications_processor(request):
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
        notifications_count = notifications.count()
    else:
        notifications = []
        notifications_count = 0

    return {
        'notifications': notifications,
        'notifications_count': notifications_count,
    }