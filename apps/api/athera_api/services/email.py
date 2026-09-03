"""إرسال البريد | The outbound email boundary.

**حدٌّ مُعلَن، لا مكتبة SMTP منثورة في المسارات.** والغرض واحد اليوم:
رسالة استعادة كلمة المرور. لكن الحدّ يُرسم مرّة، فلا يُعاد اختراعه لكل
رسالة قادمة — ولا يعرف المسارُ اسمَ مزوّدٍ ولا مفتاحًا.

**والافتراض `none`، ويفشل صراحةً.** فمزوّدٌ غير مضبوط يعني أن الرسالة لا
تُرسَل — ويجب أن يُقال ذلك بصوتٍ عالٍ لا أن يُبتلع. وأسوأ ما يمكن هنا
«نجاحٌ» صامت يترك الباحث ينتظر رسالةً لن تصل.

**ولا مسار تطوير يعمل في الإنتاج.** كتابةُ الرابط في السجل تُسهّل التطوير
وتُسرّب الاستعادة في الإنتاج — فمن قرأ السجل أعاد ضبط كلمة أي حساب. فهو
مرفوضٌ صراحةً حين `app_env == "production"`، ويفشل الإقلاع لا الرسالة.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Protocol

from ..config import get_settings

logger = logging.getLogger("athera.email")

#: ما يُقبل في `EMAIL_PROVIDER`.
PROVIDERS: Final = ("none", "console", "smtp")


@dataclass(frozen=True, slots=True)
class Message:
    """رسالةٌ واحدة — **بلا أي سرٍّ في تمثيلها النصّي**.

    و`__repr__` مُعطَّل عمدًا: تمثيلُ الكائن يظهر في آثار الاستثناءات
    وسجلات التصحيح، ورسالةُ الاستعادة تحمل رابطًا فيه الرمز. فلا يُطبع.
    """

    to: str
    subject: str
    body: str

    def __repr__(self) -> str:  # pragma: no cover - حارس تسريب
        return f"<Message to={self.to!r} subject={self.subject!r} body=[redacted]>"


class EmailProvider(Protocol):
    def send(self, message: Message) -> None: ...


class UnconfiguredProvider:
    """لا مزوّد — **فيُرفع الفشل ولا يُبتلع**."""

    def send(self, message: Message) -> None:
        raise EmailNotConfigured(
            "no email provider is configured; set EMAIL_PROVIDER and its credentials"
        )


class ConsoleProvider:
    """للتطوير المحلي وحده — يكتب **العنوان والموضوع فقط**.

    ولا يكتب الجسم: الجسم يحمل رابط الاستعادة. والمطوّر يقرأ الرمز من
    قاعدته المحلية إن احتاجه، لا من سجلٍّ قد يُشحن.
    """

    def send(self, message: Message) -> None:
        logger.info("email(dev) to=%s subject=%s body=[redacted]",
                    message.to, message.subject)


class SmtpProvider:
    """SMTP حقيقي. الاعتماد من البيئة، ولا يُكتب في شيفرة ولا سجل."""

    def __init__(self, host: str, port: int, username: str, password: str,
                 sender: str, use_tls: bool) -> None:
        self._host, self._port = host, port
        self._username, self._password = username, password
        self._sender, self._use_tls = sender, use_tls

    def send(self, message: Message) -> None:
        import smtplib
        from email.message import EmailMessage

        payload = EmailMessage()
        payload["From"] = self._sender
        payload["To"] = message.to
        payload["Subject"] = message.subject
        payload.set_content(message.body)

        with smtplib.SMTP(self._host, self._port, timeout=20) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(payload)


class EmailNotConfigured(RuntimeError):
    """يُرفع حين يُطلب إرسالٌ ولا مزوّد — ولا يُبتلع في مسار الاستعادة."""


def provider() -> EmailProvider:
    settings = get_settings()
    name = (settings.email_provider or "none").strip().lower()

    if name == "console":
        # **ولا يعمل في الإنتاج.** مسارُ تطويرٍ يصل الإنتاج بالسهو هو
        # بالضبط ما يجعل الاستعادة قابلة للسرقة من سجلّ.
        if settings.app_env == "production":
            raise EmailNotConfigured(
                "EMAIL_PROVIDER=console is a development path and is refused in production"
            )
        return ConsoleProvider()

    if name == "smtp":
        missing = [
            key for key, value in (
                ("EMAIL_SMTP_HOST", settings.email_smtp_host),
                ("EMAIL_SENDER", settings.email_sender),
            ) if not value
        ]
        if missing:
            raise EmailNotConfigured(
                "EMAIL_PROVIDER=smtp but these are unset: " + ", ".join(missing)
            )
        return SmtpProvider(
            host=settings.email_smtp_host,
            port=settings.email_smtp_port,
            username=settings.email_smtp_username,
            password=settings.email_smtp_password,
            sender=settings.email_sender,
            use_tls=settings.email_smtp_use_tls,
        )

    return UnconfiguredProvider()


def is_configured() -> bool:
    """هل يستطيع هذا النشر أن يرسل بريدًا فعلًا؟"""
    try:
        return not isinstance(provider(), UnconfiguredProvider)
    except EmailNotConfigured:
        return False


def send(message: Message) -> None:
    provider().send(message)


__all__ = ["EmailNotConfigured", "Message", "PROVIDERS", "is_configured",
           "provider", "send"]
