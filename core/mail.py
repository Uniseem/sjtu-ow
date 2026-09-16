"""Email backends used until M1 wires SMTP from SiteSettings."""

import logging

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("sjtu_ow.mail")


class DiscardLogEmailBackend(BaseEmailBackend):
    """Drop messages and log that they were discarded."""

    def send_messages(self, email_messages):
        messages = list(email_messages)
        for message in messages:
            logger.warning(
                "邮件被丢弃（当前为占位后端，M1 再接 SMTP）：to=%s subject=%s",
                message.to,
                message.subject,
            )
        return 0
