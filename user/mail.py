from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError
from django.core.mail import EmailMessage, get_connection

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

# def send_mail_from_user(subject, html, to_email, user=None):
#     if user and user.EMAIL_HOST_USER and user.EMAIL_HOST_PASSWORD:
#         conn = get_connection(
#             host=user.EMAIL_HOST or "smtp.gmail.com",
#             port=user.EMAIL_PORT or 587,
#             username=user.EMAIL_HOST_USER,
#             password=user.EMAIL_HOST_PASSWORD,
#             use_tls=getattr(user, "EMAIL_USE_TLS", True)
#         )
#         from_email = user.EMAIL_HOST_USER
#     else:
#         conn = get_connection()
#         from_email = settings.EMAIL_HOST_USER

#     EmailMessage(subject, html, from_email, [to_email], connection=conn).send()

# def get_smtp_user_for_user(user):
#     for location in user.locations.all():
#         smtp_user = location.assigned_superadmins.filter(user_type=1, EMAIL_HOST_USER__isnull=False, EMAIL_HOST_PASSWORD__isnull=False).first()
#         if smtp_user:
#             return smtp_user
#     return None


# class MailUtils:

#     @staticmethod
#     def _get_connection_from_user(smtp_user):
#         if smtp_user and smtp_user.EMAIL_HOST_USER and smtp_user.EMAIL_HOST_PASSWORD:
#             return get_connection(
#                 host=getattr(smtp_user, 'EMAIL_HOST', 'smtp.gmail.com'),
#                 port=getattr(smtp_user, 'EMAIL_PORT', 587),
#                 username=smtp_user.EMAIL_HOST_USER,
#                 password=smtp_user.EMAIL_HOST_PASSWORD,
#                 use_tls=getattr(smtp_user, 'EMAIL_USE_TLS', True)
#             ), smtp_user.EMAIL_HOST_USER
#         else:
#             return get_connection(), settings.EMAIL_HOST_USER

#     @staticmethod
#     def send_verification_email(user):
#         smtp_user = get_smtp_user_for_user(user)
#         connection, from_email = MailUtils._get_connection_from_user(smtp_user)

#         verification_link = f"{settings.BACKEND_URL}/verify-email/{user.uuid}/"
#         subject = "Verify Your Email - Arise Court"
#         html_message = render_to_string("email_verification_template/email.html", {
#             'user': user,
#             'verification_link': verification_link,
#         })

#         email = EmailMessage(subject, html_message, from_email, [user.email], connection=connection)
#         email.content_subtype = "html"
#         email.send()

#     @staticmethod
#     def send_password_reset_email(user):
#         smtp_user = get_smtp_user_for_user(user)
#         connection, from_email = MailUtils._get_connection_from_user(smtp_user)

#         uid = urlsafe_base64_encode(force_bytes(user.id))
#         token = PasswordResetTokenGenerator().make_token(user)
#         reset_link = f"{settings.BACKEND_URL}/reset-password/{uid}/{token}/"

#         subject = "Password Reset Email - Arise Court"
#         html_message = render_to_string("email_verification_template/password_reset_mail.html", {
#             'user': user,
#             'otp': user.verified_otp,
#             'reset_link': reset_link,
#         })

#         email = EmailMessage(subject, html_message, from_email, [user.email], connection=connection)
#         email.content_subtype = "html"
#         email.send()

#     @staticmethod
#     def booking_confirmation_mail(user, booking):
#         smtp_user = get_smtp_user_for_user(user)
#         connection, from_email = MailUtils._get_connection_from_user(smtp_user)

#         subject = "Booking Confirmation Email - Arise Court"
#         html_message = render_to_string("email_verification_template/booking_confirmation.html", {
#             'user': user,
#             'booking': booking
#         })

#         email = EmailMessage(subject, html_message, from_email, [user.email], connection=connection)
#         email.content_subtype = "html"
#         email.send()