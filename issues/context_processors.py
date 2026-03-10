def notifications_processor(request):
    unread_count = 0
    if request.user.is_authenticated:
        unread_count = request.user.notifications.filter(is_read=False).count()
    return {'unread_notifications': unread_count}