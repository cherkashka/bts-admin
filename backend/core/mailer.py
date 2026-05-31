import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.core.config import settings
from backend.core.logging import logger

BRAND = "BTS Admin"

async def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
        msg["To"]      = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_LOGIN,
            password=settings.SMTP_KEY,
            start_tls=True,
        )
        logger.info(f"📧 Email отправлен на {to}: {subject}")
        return True
    except Exception as exc:
        logger.error(f"❌ Ошибка отправки email на {to}: {exc}")
        return False


def _email_shell(*, title: str, heading: str, intro: str, full_name: str,
                 username: str, password: str, login_url: str,
                 button_label: str, password_label: str, note: str) -> str:
    """Общий каркас письма — белая тема, тил-акцент BTS Admin.

    Вёрстка на таблицах с инлайн-стилями для совместимости с почтовыми
    клиентами (Gmail, Outlook, Apple Mail).
    """
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

        <!-- Шапка с брендом -->
        <tr>
          <td align="center" style="padding-bottom:20px;">
            <table role="presentation" cellpadding="0" cellspacing="0">
              <tr>
                <td style="vertical-align:middle;padding-right:10px;">
                  <div style="width:34px;height:34px;background:#008080;border-radius:9px;
                              text-align:center;line-height:34px;color:#ffffff;
                              font-size:17px;font-weight:700;">B</div>
                </td>
                <td style="vertical-align:middle;">
                  <span style="font-size:19px;font-weight:700;color:#0f766e;letter-spacing:-0.3px;">{BRAND}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Белая карточка -->
        <tr>
          <td style="background:#ffffff;border-radius:16px;border:1px solid #e5e7eb;
                     box-shadow:0 1px 3px rgba(16,24,40,0.06),0 1px 2px rgba(16,24,40,0.04);
                     padding:40px 40px 36px;">

            <!-- Тил-акцент сверху -->
            <div style="width:44px;height:4px;background:#008080;border-radius:2px;margin-bottom:24px;"></div>

            <h1 style="margin:0 0 10px;font-size:21px;line-height:1.3;color:#111827;font-weight:700;">{heading}</h1>
            <p style="margin:0 0 28px;color:#6b7280;font-size:15px;line-height:1.6;">{intro}</p>

            <!-- Реквизиты -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f9fafb;border:1px solid #eceef1;border-radius:12px;
                          padding:8px 22px;margin-bottom:28px;">
              <tr>
                <td style="padding:12px 0;">
                  <span style="color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:0.4px;display:block;margin-bottom:4px;">Сотрудник</span>
                  <span style="color:#111827;font-size:15px;font-weight:600;">{full_name}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:12px 0;border-top:1px solid #eceef1;">
                  <span style="color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:0.4px;display:block;margin-bottom:4px;">Логин</span>
                  <span style="color:#111827;font-size:15px;font-weight:600;font-family:'SF Mono',Menlo,Consolas,monospace;">{username}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:12px 0;border-top:1px solid #eceef1;">
                  <span style="color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:0.4px;display:block;margin-bottom:4px;">{password_label}</span>
                  <span style="color:#008080;font-size:17px;font-weight:700;font-family:'SF Mono',Menlo,Consolas,monospace;letter-spacing:0.5px;">{password}</span>
                </td>
              </tr>
            </table>

            <!-- Кнопка -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td align="center">
                  <a href="{login_url}"
                     style="display:inline-block;padding:14px 40px;background:#008080;
                            color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;
                            border-radius:10px;letter-spacing:0.2px;">
                    {button_label}
                  </a>
                </td>
              </tr>
            </table>

            <!-- Примечание -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;">
              <tr>
                <td style="padding:14px 18px;color:#92400e;font-size:13px;line-height:1.6;">
                  {note}
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Подвал -->
        <tr>
          <td align="center" style="padding-top:22px;">
            <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
              Письмо сформировано автоматически системой {BRAND}.<br>
              Если вы его не ожидали — просто проигнорируйте.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_invite_html(full_name: str, username: str, password: str, login_url: str) -> str:
    return _email_shell(
        title=f"Добро пожаловать в {BRAND}",
        heading="Добро пожаловать!",
        intro=f"Для вас создан аккаунт в системе <strong>{BRAND}</strong>. "
              f"Используйте данные ниже для первого входа.",
        full_name=full_name, username=username, password=password, login_url=login_url,
        button_label="Войти в систему",
        password_label="Временный пароль",
        note="<strong>При первом входе потребуется сменить пароль.</strong> "
             "Временный пароль действует только до первой смены — задайте свой и "
             "сохраните его в надёжном месте.",
    )


def build_invite_text(full_name: str, username: str, password: str, login_url: str) -> str:
    return (
        f"Добро пожаловать, {full_name}!\n\n"
        f"Для вас создан аккаунт в системе {BRAND}.\n\n"
        f"Логин: {username}\n"
        f"Временный пароль: {password}\n\n"
        f"Войти: {login_url}\n\n"
        "При первом входе потребуется сменить пароль.\n"
    )


def build_reset_html(full_name: str, username: str, password: str, login_url: str) -> str:
    return _email_shell(
        title=f"Сброс пароля — {BRAND}",
        heading="Пароль сброшен",
        intro=f"Администратор сбросил пароль для вашего аккаунта в <strong>{BRAND}</strong>. "
              f"Войдите с новым временным паролем ниже.",
        full_name=full_name, username=username, password=password, login_url=login_url,
        button_label="Войти в систему",
        password_label="Новый временный пароль",
        note="<strong>При входе потребуется задать новый пароль.</strong> "
             "Если вы не запрашивали сброс — сообщите администратору.",
    )


def build_reset_text(full_name: str, username: str, password: str, login_url: str) -> str:
    return (
        f"Здравствуйте, {full_name}!\n\n"
        f"Администратор сбросил пароль для вашего аккаунта в {BRAND}.\n\n"
        f"Логин: {username}\n"
        f"Новый временный пароль: {password}\n\n"
        f"Войти: {login_url}\n\n"
        "При входе потребуется задать новый пароль.\n"
    )
