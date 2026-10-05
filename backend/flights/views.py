import logging

from django.conf import settings
from django.http import Http404
from openai import OpenAI, OpenAIError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Flight
from .serializers import FlightSerializer

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
        Generate a concise, focused narrative about this flight:
        - Departure: {flight_data['departure_airport']} at {flight_data['departure_time']}
        - Arrival: {flight_data['arrival_airport']} at {flight_data['arrival_time']}
        - Duration: {flight_data['total_time']}
        - Distance: {flight_data['distance']} nautical miles
        - Aircraft: {flight_data['registration_number']}
        - Conditions: {flight_data['aircraft_condition']}
        - Weather: {flight_data.get('weather_conditions', 'Unknown')}
        
        Create a human-friendly summary that captures the highlights and any challenges of this flight.
        Keep it concise (2-3 sentences) but informative.
        """
        
        if not settings.OPENAI_API_KEY:
            return Response({"error": "OpenAI API key is not configured"}, status=503)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates engaging flight narratives based on flight data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.7,
            )
        except OpenAIError as e:
            logger.error(f"OpenAI request failed: {e}")
            return Response({"error": "Failed to generate narrative"}, status=502)

        narrative = response.choices[0].message.content.strip()
        return Response({"narrative": narrative})

    except Exception as e:
        logger.error(f"Error in generate_narrative: {str(e)}")
        return Response({"error": str(e)}, status=500)
