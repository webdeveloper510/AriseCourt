from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError

class MailUtils:
    @staticmethod
    def send_verification_email(user):
            verification_link = f"{settings.BACKEND_URL}/verify-email/{user.uuid}/"
            subject = "Verify Your Email - Arise Court"
            html_message = render_to_string("email_verification_template/email.html", {
                'user': user,
                'verification_link': verification_link,
                })

            send_mail(
                subject=subject,
                message= html_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

          
    def send_password_reset_email(user):
        uid = urlsafe_base64_encode(force_bytes(user.id))
        token = PasswordResetTokenGenerator().make_token(user)

        reset_link = f"{settings.BACKEND_URL}/reset-password/{uid}/{token}/"

        subject = "Password Reset Email - Arise Court"
        html_message = render_to_string("email_verification_template/password_reset_mail.html", {
            'user': user,
            'otp': user.verified_otp,
            'reset_link': reset_link,
        })

        send_mail(
            subject=subject,
            message=html_message,  
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )


    def booking_confirmation_mail(user, booking):
        subject = "Booking Confirmation Email - Arise Court"
        html_message = render_to_string("email_verification_template/booking_confirmation.html", {
            'user': user,
            'booking': booking
        })

        send_mail(
            subject=subject,
            message=html_message,  
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )