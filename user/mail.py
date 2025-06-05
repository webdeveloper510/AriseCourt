from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

class MailUtils:
    def send_verification_email(self, user):
            verification_link = f"http://localhost:8000/verify-email/{user.uuid}/"
            subject = "Verify Your Email - Arise Court"
            html_message = render_to_string("email_verification_template/email.html", {
                'user': user,
                'verification_link': verification_link,
                })

            send_mail(
                subject=subject,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
