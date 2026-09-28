"""Gmail IMAP reader + SMTP sender using only Python stdlib."""
from __future__ import annotations

import email
import email.utils
import imaplib
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("email_client")

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Senders to skip — automated emails, newsletters, system mail
SKIP_SENDER_PATTERNS = (
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "notifications@",
    "newsletter",
    "unsubscribe",
    "auto-confirm",
    "support-noreply",
    "github.com",
    "vercel.com",
    "render.com",
)


@dataclass
class InboundEmail:
    uid: str
    from_addr: str
    reply_to: str
    subject: str
    body: str


class GmailClient:
    def __init__(self, address: str, app_password: str) -> None:
        self.address = address
        # App passwords may have spaces (e.g. "abcd efgh ijkl mnop") — strip them
        self.password = app_password.replace(" ", "")

    # ── Read ──────────────────────────────────────────────────────────────────

    def fetch_unread(self) -> list[InboundEmail]:
        """Return all UNSEEN emails from the INBOX and mark them as Seen."""
        results: list[InboundEmail] = []

        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(self.address, self.password)
            imap.select("INBOX")

            _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()

            if not uids:
                return results

            for uid in uids:
                _, msg_data = imap.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                reply_to  = email.utils.parseaddr(
                    msg.get("Reply-To", msg.get("From", ""))
                )[1]
                subject = msg.get("Subject", "(no subject)")

                # Skip automated / system emails
                from_lower = from_addr.lower()
                if from_lower == self.address.lower():
                    log.info("⏭ Skipping self-sent email: %s", subject)
                    continue
                if any(p in from_lower for p in SKIP_SENDER_PATTERNS):
                    log.info("⏭ Skipping automated sender (%s): %s", from_addr, subject)
                    continue

                # Extract plain-text body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(
                                "utf-8", errors="replace"
                            )
                            break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="replace")

                results.append(
                    InboundEmail(
                        uid=uid.decode(),
                        from_addr=from_addr,
                        reply_to=reply_to or from_addr,
                        subject=subject,
                        body=body.strip(),
                    )
                )

            # Mark all fetched emails as Seen
            for uid in uids:
                imap.store(uid, "+FLAGS", "\\Seen")

        log.info("📬 Fetched %d unread email(s)", len(results))
        return results

    # ── Send ──────────────────────────────────────────────────────────────────

    def send_reply(self, to: str, subject: str, body: str) -> None:
        """Send a plain-text reply via Gmail SMTP (STARTTLS)."""
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"AgentShield Support <{self.address}>"
        msg["To"]      = to
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self.address, self.password)
            smtp.sendmail(self.address, to, msg.as_string())

        log.info("📧 Reply sent to %s", to)
