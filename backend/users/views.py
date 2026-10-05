import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db.models import Count, F, Max, Q, Sum
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from flights.models import Flight
from .serializers import (
    ChangePasswordSerializer, DeleteAccountSerializer, PasswordResetConfirmSerializer, ProfileSerializer, UserSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class AuthThrottle(AnonRateThrottle):
    scope = 'auth'


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        logger.info("Registered user %s", user.pk)
        return Response({**tokens_for(user), 'user': serializer.data}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({**tokens_for(user), 'username': user.username, 'email': user.email})


class GoogleLoginView(APIView):
    """Exchange a Google ID token (from NextAuth's Google provider) for AirFleet JWTs."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            return Response({'error': 'Google sign-in is not configured'}, status=503)
        token = request.data.get('id_token')
        if not token:
            return Response({'error': 'id_token is required'}, status=400)

        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            claims = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=401)
        if not claims.get('email') or not claims.get('email_verified'):
            return Response({'error': 'Your Google account email is not verified'}, status=401)

        email = claims['email']
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:140] or 'pilot'
            username, n = base, 1
            while User.objects.filter(username__iexact=username).exists():
                n += 1
                username = f'{base}{n}'
            user = User.objects.create_user(
                username=username, email=email,
                first_name=claims.get('given_name', '')[:150], last_name=claims.get('family_name', '')[:150],
            )
            user.set_unusable_password()
            user.save()
        if not user.is_active:
            return Response({'error': 'This account is disabled'}, status=403)
        return Response({**tokens_for(user), 'username': user.username, 'email': user.email})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request):
        """Erase the account: profile, flights, aircraft (cascaded) and uploaded flight photos."""
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        for flight in Flight.objects.filter(user=user).exclude(photo__isnull=True).exclude(photo=''):
            try:
                flight.photo.delete(save=False)
            except Exception:
                logger.exception("Could not delete photo of flight %s", flight.pk)
        user_id = user.pk
        user.delete()
        logger.info("Deleted user %s", user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({**tokens_for(request.user), 'detail': 'Password updated.'})


class PasswordResetRequestView(APIView):
    """Email a reset link. Always answers the same way so it can't be used to probe for accounts."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
            try:
                send_mail(
                    subject='Reset your AirFleet password',
                    message=(
                        f"Hi {user.username},\n\n"
                        f"Someone asked to reset the password for your AirFleet logbook. "
                        f"Follow this link to choose a new one:\n\n{link}\n\n"
                        f"If it wasn't you, you can ignore this email; your password won't change."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                )
            except Exception:
                logger.exception("Could not send password reset email to user %s", user.pk)
        return Response({'detail': "If that email has an account, we've sent a reset link to it."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data['uid'])))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, data['token']):
            return Response({'error': 'This reset link is invalid or has expired.'}, status=400)
        try:
            validate_password(data['password'], user)
        except DjangoValidationError as e:
            return Response({'password': list(e.messages)}, status=400)
        user.set_password(data['password'])
        user.save()
        return Response({'detail': 'Password reset. You can log in now.'})


RANKING_PERIODS = {'all', 'year', 'month'}


class RankingsView(APIView):
    """Top 10 pilots by flights, time, distance, longest single flight and airports visited.

    ?period=month|year limits everything to the current calendar month or year.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        period = request.query_params.get('period', 'all')
        if period not in RANKING_PERIODS:
            period = 'all'
        now = timezone.now()
        in_period = Q()
        if period == 'year':
            in_period = Q(flights__departure_time__year=now.year)
        elif period == 'month':
            in_period = Q(flights__departure_time__year=now.year, flights__departure_time__month=now.month)

        users = User.objects.filter(is_active=True).annotate(
            total_flights=Count('flights', filter=in_period),
            total_time=Sum('flights__total_time', filter=in_period),
            total_distance=Sum('flights__distance', filter=in_period),
            longest_flight=Max('flights__total_time', filter=in_period),
        ).filter(total_flights__gt=0)

        def row(user, **extra):
            return {'username': user.username, 'is_public': user.is_public, **extra}

        flights = Flight.objects.filter(user__is_active=True)
        if period != 'all':
            flights = flights.filter(**{k.removeprefix('flights__'): v for k, v in in_period.children})
        visited = {}
        for user_id, dep, arr in flights.values_list('user_id', 'departure_airport', 'arrival_airport'):
            visited.setdefault(user_id, set()).update((dep, arr))
        public = dict(User.objects.filter(pk__in=visited).values_list('pk', 'is_public'))
        names = dict(User.objects.filter(pk__in=visited).values_list('pk', 'username'))
        airports_ranking = sorted(visited.items(), key=lambda kv: (-len(kv[1]), names[kv[0]]))[:10]

        return Response({
            'period': period,
            'flights': [row(u, total_flights=u.total_flights) for u in users.order_by('-total_flights', 'username')[:10]],
            'time': [
                row(u, total_time=str(u.total_time or timedelta(0)))
                for u in users.order_by(F('total_time').desc(nulls_last=True), 'username')[:10]
            ],
            'distance': [
                row(u, total_distance=u.total_distance or 0)
                for u in users.order_by(F('total_distance').desc(nulls_last=True), 'username')[:10]
            ],
            'longest': [
                row(u, longest_flight=str(u.longest_flight or timedelta(0)))
                for u in users.order_by(F('longest_flight').desc(nulls_last=True), 'username')[:10]
            ],
            'airports': [
                {'username': names[pk], 'is_public': public[pk], 'airports_visited': len(codes)}
                for pk, codes in airports_ranking
            ],
        })
