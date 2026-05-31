import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.core.config import settings
from backend.core.logging import logger

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

def build_invite_html(full_name: str, username: str, password: str, login_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Добро пожаловать в IT Admin System</title>
</head>
<body style="margin:0;padding:0;background:#e8ecef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#e8ecef;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

        <!-- Логотип / заголовок -->
        <tr>
          <td align="center" style="padding-bottom:24px;">
            <!-- LOGO_PLACEHOLDER -->
            <h1 style="margin:0;font-size:22px;font-weight:700;color:#4a5568;letter-spacing:-0.5px;">IT Admin System</h1>
          </td>
        </tr>

        <!-- Карточка -->
        <tr>
          <td style="background:#e8ecef;border-radius:20px;
                     box-shadow:8px 8px 16px #c8cdd2,-8px -8px 16px #ffffff;
                     padding:36px 40px;">

            <h2 style="margin:0 0 8px;font-size:20px;color:#2d3748;">Добро пожаловать!</h2>
            <p style="margin:0 0 28px;color:#718096;font-size:15px;">
              Ваш аккаунт в <strong>IT Admin System</strong> создан. Используйте данные ниже для первого входа.
            </p>

            <!-- Реквизиты -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#e8ecef;border-radius:14px;
                          box-shadow:inset 4px 4px 8px #c8cdd2,inset -4px -4px 8px #ffffff;
                          padding:20px 24px;margin-bottom:28px;">
              <tr>
                <td style="padding:6px 0;">
                  <span style="color:#718096;font-size:13px;display:block;margin-bottom:2px;">ФИО</span>
                  <span style="color:#2d3748;font-size:15px;font-weight:600;">{full_name}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:6px 0;border-top:1px solid #d0d5db;">
                  <span style="color:#718096;font-size:13px;display:block;margin-bottom:2px;">Логин</span>
                  <span style="color:#2d3748;font-size:15px;font-weight:600;font-family:monospace;">{username}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:6px 0;border-top:1px solid #d0d5db;">
                  <span style="color:#718096;font-size:13px;display:block;margin-bottom:2px;">Временный пароль</span>
                  <span style="color:#2d3748;font-size:15px;font-weight:600;font-family:monospace;">{password}</span>
                </td>
              </tr>
            </table>

            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td align="center">
                  <a href="{login_url}"
                     style="display:inline-block;padding:14px 36px;
                            background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                            color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;
                            border-radius:12px;letter-spacing:0.3px;">
                    Войти в систему
                  </a>
                </td>
              </tr>
            </table>

            <!-- Инструкция -->
            <p style="margin:0;padding:16px 20px;background:#fffbeb;border-radius:10px;
                      border-left:4px solid #f59e0b;color:#78350f;font-size:13px;line-height:1.6;">
              ⚠️ При первом входе вас попросят <strong>сменить пароль</strong>. Временный пароль
              действителен только для одного входа. Сохраните новый пароль в надёжном месте.
            </p>

          </td>
        </tr>

        <!-- Подвал -->
        <tr>
          <td align="center" style="padding-top:24px;">
            <p style="margin:0;color:#a0aec0;font-size:12px;">
              Это письмо сформировано автоматически. Если вы его не ожидали — проигнорируйте.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

def build_invite_text(full_name: str, username: str, password: str, login_url: str) -> str:
    return (
        f"Добро пожаловать, {full_name}!\n\n"
        f"Ваш аккаунт в IT Admin System создан.\n\n"
        f"Логин: {username}\n"
        f"Временный пароль: {password}\n\n"
        f"Войти: {login_url}\n\n"
        "При первом входе потребуется сменить пароль.\n"
    )
