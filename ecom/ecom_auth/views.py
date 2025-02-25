from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth.models import User
from django.views.generic import View
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str, DjangoUnicodeDecodeError
from .utils import TokenGenerator, generate_token
from django.core.mail import send_mail, EmailMultiAlternatives, BadHeaderError, EmailMessage
from django.core import mail
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import threading


class EmailThread(threading.Thread):
    def __init__(self, email_message):
        self.email_message = email_message
        threading.Thread.__init__(self)

    def run(self):
        self.email_message.send()


def signup(request):
    if request.method == "POST":
        username = request.POST['email']  
        password = request.POST['password']
        confirm_password = request.POST['confirmpassword']

        if password != confirm_password:
            messages.warning(request, "Passwords do not match!")
            return render(request, 'auth/signup.html')  

        try:
            if User.objects.get(username=username):
                messages.warning(request, "Email is already taken.")
                return render(request, 'auth/signup.html')
        except User.DoesNotExist:
            pass

        user = User.objects.create_user(username=username, email=username, password=password)
        user.is_active = False
        user.save()

        current_site = get_current_site(request)
        email_subject = "Activate Your Account"
        message = render_to_string('auth/activate.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': generate_token.make_token(user)
        })

        email_message = EmailMessage(
            email_subject, 
            message, 
            settings.EMAIL_HOST_USER,
            [username]
        )

        EmailThread(email_message).start()
        messages.info(request, "Activate Your Account by clicking the link in your email.")
        return redirect('/ecom_auth/login')

    return render(request, 'auth/signup.html')


class ActivateAccountView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, DjangoUnicodeDecodeError):
            user = None

        if user is not None and generate_token.check_token(user, token):
            user.is_active = True
            user.save()
            messages.info(request, "Account Activation Successful")
            return redirect('/ecom_auth/login')
        
        return render(request, 'auth/activatefail.html')


def handlelogin(request):
    if request.method == "POST":
        email = request.POST['email']  
        password = request.POST['password']
        
        # Print for debugging
        print(f"Attempting login with email: {email}")
        
        try:
            # First get user by email to ensure they exist
            user = User.objects.get(username=email)
            # Try to authenticate
            myuser = authenticate(username=email, password=password)
            
            if myuser is not None:
                login(request, myuser)
                messages.success(request, "Login Successful")
                return redirect("/")
            else:
                # Print for debugging
                print(f"Authentication failed for user: {email}")
                messages.error(request, "Invalid Credentials")
        except User.DoesNotExist:
            messages.error(request, "User does not exist")
        except Exception as e:
            # Print for debugging
            print(f"Login error: {str(e)}")
            messages.error(request, "Login failed")
            
        return redirect('/ecom_auth/login')
        
    return render(request, 'auth/login.html')


def handlelogout(request):
    logout(request)
    messages.success(request, "Logout Successful")
    return redirect('/ecom_auth/login')


class RequestResetEmailView(View):
    def get(self, request):
        return render(request, 'auth/request-reset-email.html')
    
    def post(self, request):
        email = request.POST['email']
        try:
            # Get first user with this email
            user = User.objects.filter(username=email).first()
            if user:
                current_site = get_current_site(request)
                email_subject = '[Reset Your Password]'
                message = render_to_string('auth/reset-user-password.html', {
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': PasswordResetTokenGenerator().make_token(user)
                })

                email_message = EmailMessage(
                    email_subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [email]
                )
                EmailThread(email_message).start()

                messages.info(request, "We have sent you an email with instructions on how to reset your password")
            else:
                messages.warning(request, "No account found with that email")
                
        except Exception as e:
            print(f"Password reset error: {str(e)}")  # Debug print
            messages.error(request, "Something went wrong. Please try again.")
        
        return render(request, 'auth/request-reset-email.html')


class SetNewPasswordView(View):
    def get(self, request, uidb64, token):
        context = {
            'uidb64': uidb64,
            'token': token
        }
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=user_id)

            if not PasswordResetTokenGenerator().check_token(user, token):
                messages.warning(request, "Password reset link is invalid")
                return redirect('/ecom_auth/request-reset-email')
            
        except (DjangoUnicodeDecodeError, User.DoesNotExist):
            messages.error(request, "Invalid reset link")
            return redirect('/ecom_auth/request-reset-email')

        return render(request, 'auth/set-new-password.html', context)
    
    def post(self, request, uidb64, token):
        context = {
            'uidb64': uidb64,
            'token': token
        }
        
        password = request.POST['password']
        confirm_password = request.POST['confirmpassword']

        if password != confirm_password:
            messages.warning(request, "Passwords do not match")
            return render(request, 'auth/set-new-password.html', context)
        
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=user_id)
            
            if not PasswordResetTokenGenerator().check_token(user, token):
                messages.warning(request, "Reset link is invalid")
                return redirect('/ecom_auth/request-reset-email')
            
            # Debug prints
            print(f"Resetting password for user: {user.username}")
            
            # Set the new password
            user.set_password(password)
            user.is_active = True
            user.save()
            
            # Try to authenticate with new password
            test_auth = authenticate(username=user.username, password=password)
            print(f"Test authentication after reset: {'Success' if test_auth else 'Failed'}")
            
            messages.success(request, "Password reset successful! You can now login with your new password.")
            return redirect('/ecom_auth/login')
        
        except Exception as e:
            print(f"Password set error: {str(e)}")  # Debug print
            messages.error(request, "Something went wrong")
            return render(request, 'auth/set-new-password.html', context)