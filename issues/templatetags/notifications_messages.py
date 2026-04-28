# issues/notification_messages.py
from django.utils.translation import gettext_lazy as _

NOTIFICATION_MESSAGES = {
    "notification.assigned":       _("Вам назначена заявка: %(title)s"),
    "notification.status_changed": _("Ваша заявка «%(title)s» изменила статус на «%(status)s»"),
    "notification.taken_to_work":  _("Вы взяли в работу заявку: %(title)s"),
}