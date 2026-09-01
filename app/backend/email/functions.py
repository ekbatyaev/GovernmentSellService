import os
import re
import asyncio
from app.settings import settings, logger
from exchangelib import (Credentials, Account, FileAttachment,
                         Configuration, Message, DELEGATE, HTMLBody)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

async def send_email(to_email, subject, body, attachments = None):
    if not to_email or not _EMAIL_RE.match(to_email):
        logger.error(f"Пропускаю отправку — некорректный email: {to_email!r}")
        return

    try:
        creds = Credentials(settings.smtp_user, settings.smtp_password)
        config = Configuration(server=settings.smtp_server, credentials=creds)

        # Подключаемся к аккаунту
        account = Account(
            primary_smtp_address=settings.smtp_email,
            config=config,
            autodiscover=False,
            access_type=DELEGATE
        )

        # Создание и отправка
        msg = Message(
            account=account,
            subject=subject,
            body=HTMLBody(body),
            to_recipients=[to_email]
        )

        if attachments:
            for file_path in attachments:
                with open(file_path, 'rb') as f:
                    content = f.read()

                attachment = FileAttachment(
                    name=os.path.basename(file_path),
                    content=content
                )
                msg.attach(attachment)

        msg.send()
        logger.info(f"Письмо успешно отправлено через EWS на {to_email}")

    except Exception as e:
        logger.error(f"Ошибка EWS: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(send_email(settings.smtp_test_email, "Тест EWS", "Привет! Это письмо отправлено через Exchange Web Services."))
