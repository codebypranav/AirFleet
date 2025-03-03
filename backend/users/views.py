from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer
from django.db.models import Sum, Count
from flights.models import Flight
import logging

logger = logging.getLogger(__name__)

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Log the incoming request data
            logger.info(f"Register attempt with data: {request.data}")
            
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': serializer.data
                }, status=status.HTTP_201_CREATED)
            
            # Log validation errors
            logger.error(f"Validation error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            # Log any unexpected errors
            logger.exception(f"Error in register view: {str(e)}")
            return Response({
                'error': 'An unexpected error occurred',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'username': user.username,
                'email': user.email
            })
        else:
            return Response(
                {'error': 'Invalid credentials'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

class RankingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        User = get_user_model()
        
        # Get rankings by total flights
        flights_ranking = User.objects.annotate(
            total_flights=Count('flights')
        ).order_by('-total_flights')[:10]

        # Get rankings by total time
        time_ranking = User.objects.annotate(
            total_time=Sum('flights__total_time')
        ).order_by('-total_time')[:10]

        # Get rankings by total distance
        distance_ranking = User.objects.annotate(
            total_distance=Sum('flights__distance')
        ).order_by('-total_distance')[:10]

        # Format the response
        response = {
            'flights': [
                {
                    'username': user.username,
                    'total_flights': user.total_flights
                } for user in flights_ranking
            ],
            'time': [
                {
                    'username': user.username,
                    'total_time': str(user.total_time) if user.total_time else '0:00:00'
                } for user in time_ranking
            ],
            'distance': [
                {
                    'username': user.username,
                    'total_distance': user.total_distance or 0
                } for user in distance_ranking
            ]
        }

        return Response(response) 