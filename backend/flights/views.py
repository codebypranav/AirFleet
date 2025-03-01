from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Flight
from .serializers import FlightSerializer
from rest_framework.permissions import IsAuthenticated
from django.http import Http404
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
import openai

logger = logging.getLogger(__name__)

class FlightListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        flights = Flight.objects.filter(user=request.user)
        serializer = FlightSerializer(flights, many=True)
        return Response(serializer.data)

    def post(self, request):
        logger.info(f"Received flight data: {request.data}")
        
        serializer = FlightSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.error(f"Validation errors: {serializer.errors}")
        return Response(
            {
                'status': 'error',
                'errors': serializer.errors,
                'message': 'Invalid flight data'
            }, 
            status=status.HTTP_400_BAD_REQUEST
        )

class FlightDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Flight.objects.get(pk=pk, user=user)
        except Flight.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        flight = self.get_object(pk, request.user)
        serializer = FlightSerializer(flight)
        return Response(serializer.data)

    def put(self, request, pk):
        flight = self.get_object(pk, request.user)
        serializer = FlightSerializer(flight, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        flight = self.get_object(pk, request.user)
        flight.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_narrative(request):
    """Generate a narrative for a flight using ChatGPT."""
    try:
        # Extract flight data from request
        flight_data = request.data
        
        # Create a prompt for ChatGPT
        prompt = f"""
        Generate a concise, engaging narrative about this flight:
        - Departure: {flight_data['departure_airport']} at {flight_data['departure_time']}
        - Arrival: {flight_data['arrival_airport']} at {flight_data['arrival_time']}
        - Duration: {flight_data['total_time']}
        - Distance: {flight_data['distance']} nautical miles
        - Aircraft: {flight_data['registration_number']}
        - Conditions: {flight_data['aircraft_condition']}
        - Weather: {flight_data.get('weather_conditions', 'Unknown')}
        
        Create a human-friendly story that captures the highlights and any challenges of this flight.
        Keep it concise (3-4 sentences) but informative and engaging.
        """
        
        # Call the OpenAI API
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # or "gpt-4" for better quality
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates engaging flight narratives based on flight data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.7,
        )
        
        # Extract the narrative from the response
        narrative = response.choices[0].message.content.strip()
        
        # Return the narrative
        return Response({"narrative": narrative})
    
    except Exception as e:
        return Response({"error": str(e)}, status=500)
