from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
import httpx
import asyncio
import imaplib
import email
from email.header import decode_header
import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
API_KEY = os.getenv("API_KEY")  # simple API key for the backend

app = FastAPI(title="AI API + Email Dashboard (test-ai)")


def require_api_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 256


class GenerateResponse(BaseModel):
    text: str


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str
    from_email: Optional[EmailStr] = None


class EmailPreview(BaseModel):
    uid: str
    from_: str
    subject: str
    snippet: str
    date: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse, dependencies=[Depends(require_api_key)])
async def generate(req: GenerateRequest):
    if not AI_API_KEY:
        raise HTTPException(status_code=500, detail="AI_API_KEY not configured")
    # Example: call a hypothetical completion endpoint (replace with actual provider)
    headers = {"Authorization": f"Bearer {AI_API_KEY}"}
    payload = {"prompt": req.prompt, "max_tokens": req.max_tokens}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Replace URL with your AI provider endpoint
        r = await client.post("https://api.example-ai.com/v1/generate", json=payload, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="AI provider error")
        data = r.json()
        text = data.get("text") or data.get("choices", [{}])[0].get("text", "")
    return {"text": text}


@app.post("/send-email", dependencies=[Depends(require_api_key)])
async def send_email(req: SendEmailRequest):
    from_addr = req.from_email or SMTP_USER
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        raise HTTPException(status_code=500, detail="SMTP not configured")
    message = f"From: {from_addr}\r\nTo: {req.to}\r\nSubject: {req.subject}\r\n\r\n{req.body}"
    try:
        await aiosmtplib.send(message, hostname=SMTP_HOST, port=SMTP_PORT,
                             username=SMTP_USER, password=SMTP_PASS, start_tls=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP send error: {e}")
    return {"status": "sent"}


@app.get("/fetch-emails", response_model=List[EmailPreview], dependencies=[Depends(require_api_key)])
async def fetch_emails(limit: int = 10):
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        raise HTTPException(status_code=500, detail="IMAP not configured")
    # Use run_in_executor to avoid blocking the event loop with imaplib
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_emails_sync, limit)


def _decode_header_value(val):
    if not val:
        return ""
    parts = decode_header(val)
    out = ""
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out += chunk.decode(enc or "utf-8", errors="ignore")
        else:
            out += chunk
    return out


def _fetch_emails_sync(limit: int = 10):
    previews = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")
        typ, data = mail.search(None, "ALL")
        if typ != "OK":
            return previews
        uids = data[0].split()
        for uid in uids[-limit:][::-1]:
            typ, msg_data = mail.fetch(uid, "(RFC822)")
            if typ != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subj = _decode_header_value(msg.get("Subject"))
            from_ = _decode_header_value(msg.get("From"))
            date = msg.get("Date")
            snippet = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        snippet = part.get_payload(decode=True)[:200].decode(errors="ignore")
                        break
            else:
                snippet = msg.get_payload(decode=True)[:200].decode(errors="ignore")
            previews.append({"uid": uid.decode(), "from_": from_, "subject": subj, "snippet": snippet, "date": date})
        mail.logout()
    except Exception:
        pass
    return previews
