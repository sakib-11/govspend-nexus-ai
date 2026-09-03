import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import asyncio

class EmailNotifier:
    """Email notification client"""
    
    def __init__(self, config):
        self.config = config
        self.smtp_host = config.email_smtp_host
        self.smtp_port = config.email_smtp_port
        self.sender = config.email_sender
    
    async def send(
        self, 
        subject: str, 
        body: str, 
        recipients: List[str]
    ) -> bool:
        """Send email notification"""
        
        try:
            # Run in thread pool to avoid blocking
            return await asyncio.to_thread(
                self._send_sync,
                subject,
                body,
                recipients
            )
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    def _send_sync(
        self, 
        subject: str, 
        body: str, 
        recipients: List[str]
    ) -> bool:
        """Synchronous email send"""
        
        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.send_message(msg)
        
        return True