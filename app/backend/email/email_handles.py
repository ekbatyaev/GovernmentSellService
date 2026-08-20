import os
from dotenv import load_dotenv
from exchangelib import (Credentials, Account, FileAttachment,
                         Configuration, Message, DELEGATE, HTMLBody)

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_TEST_EMAIL = os.getenv("SMTP_TEST_EMAIL")

def send_email(to_email, subject, body, attachments = None):
    try:
        creds = Credentials(SMTP_USER, SMTP_PASSWORD)
        config = Configuration(server=SMTP_SERVER, credentials=creds)

        # Подключаемся к аккаунту
        account = Account(
            primary_smtp_address=SMTP_EMAIL,
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
        print(f"Письмо успешно отправлено через EWS на {to_email}")

    except Exception as e:
        raise f"Ошибка EWS: {e}"


if __name__ == "__main__":
    send_email(SMTP_TEST_EMAIL, "Тест EWS", "Привет! Это письмо отправлено через Exchange Web Services.")
