from django import template
from django.utils import timezone
from django.utils.translation import get_language
from .notifications_messages import NOTIFICATION_MESSAGES
from django.utils.translation import gettext as _

register = template.Library()

STATUS_TRANSLATIONS = {
    "open":        _("Открыта"),
    "in_progress": _("В работе"),
    "resolved":    _("Решена"),
    "closed":      _("Закрыта"),
}

@register.filter
def smart_timesince(value):
    if not value:
        return ""

    now = timezone.now()
    diff = now - value

    seconds = diff.total_seconds()

    # Словари склонений
    intervals = (
        ('жыл', 31536000),  # 60 * 60 * 24 * 365
        ('ай', 2592000),  # 60 * 60 * 24 * 30
        ('апта', 604800),  # 60 * 60 * 24 * 7
        ('күн', 86400),  # 60 * 60 * 24
        ('сағат', 3600),  # 60 * 60
        ('минут', 60),
    )

    current_lang = get_language()

    # Если выбран казахский
    if current_lang == 'kk':
        for name, count in intervals:
            value_int = int(seconds // count)
            if value_int >= 1:
                return f"{value_int} {name} бұрын"
        return "жаңа ғана"

    # Если выбран русский
    if current_lang == 'ru':
        # Для русского используем стандартный фильтр, он обычно работает адекватно
        from django.utils.timesince import timesince
        return f"{timesince(value).split(',')[0]} назад"

    # По умолчанию (английский)
    from django.utils.timesince import timesince
    return f"{timesince(value).split(',')[0]} ago"

@register.filter
def translate_notification(notif):
    if notif.message_key and notif.message_key in NOTIFICATION_MESSAGES:
        template_str = NOTIFICATION_MESSAGES[notif.message_key]
        params = dict(notif.message_params)

        # Переводим статус если он есть в параметрах
        if "status" in params:
            params["status"] = STATUS_TRANSLATIONS.get(params["status"], params["status"])

        return str(template_str) % params if params else str(template_str)

    return notif.message  # fallback для старых записей