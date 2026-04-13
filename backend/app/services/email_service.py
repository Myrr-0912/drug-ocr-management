"""邮件服务：使用 aiosmtplib 异步发送邮件（阿里云 SMTP）。

SMTP 配置通过 .env 注入，支持 SSL（端口 465）和 STARTTLS（端口 587）。
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_body: str) -> None:
    """发送 HTML 邮件

    Args:
        to: 收件人邮箱
        subject: 邮件主题
        html_body: HTML 格式正文
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP 未配置，跳过发送邮件至 %s", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_ssl,
        )
        logger.info("邮件发送成功：%s → %s", subject, to)
    except Exception as exc:
        logger.error("邮件发送失败：%s → %s，原因：%s", subject, to, exc)
        raise


def _reset_password_html(username: str, reset_url: str, expire_minutes: int = 15) -> str:
    """生成重置密码邮件 HTML 模板"""
    return f"""
<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
        <!-- 头部 -->
        <tr>
          <td style="background:#1d4ed8;padding:32px 40px;text-align:center;">
            <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;letter-spacing:0.5px;">
              药品智能管理系统
            </h1>
          </td>
        </tr>
        <!-- 正文 -->
        <tr>
          <td style="padding:40px;">
            <p style="margin:0 0 16px;color:#374151;font-size:15px;line-height:1.6;">
              你好，<strong>{username}</strong>，
            </p>
            <p style="margin:0 0 24px;color:#374151;font-size:15px;line-height:1.6;">
              我们收到了你的密码重置请求。点击下方按钮设置新密码，链接 <strong>{expire_minutes} 分钟</strong>内有效。
            </p>
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr><td align="center" style="padding:8px 0 32px;">
                <a href="{reset_url}"
                   style="display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;
                          padding:14px 40px;border-radius:8px;font-size:15px;font-weight:600;
                          letter-spacing:0.3px;">
                  重置密码
                </a>
              </td></tr>
            </table>
            <p style="margin:0 0 8px;color:#6b7280;font-size:13px;line-height:1.6;">
              如果按钮无法点击，请复制以下链接到浏览器：
            </p>
            <p style="margin:0 0 24px;word-break:break-all;color:#3b82f6;font-size:13px;line-height:1.6;">
              {reset_url}
            </p>
            <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
              如果你没有发起此请求，请忽略本邮件，账号不会受到任何影响。
            </p>
          </td>
        </tr>
        <!-- 底部 -->
        <tr>
          <td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #f3f4f6;
                     text-align:center;color:#9ca3af;font-size:12px;">
            © 2026 药品智能管理系统 · 此邮件由系统自动发送，请勿直接回复
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


async def send_reset_password_email(to: str, username: str, token: str) -> None:
    """发送重置密码邮件"""
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"
    subject = "【药品管理系统】重置密码"
    html = _reset_password_html(username, reset_url)
    await send_email(to, subject, html)
