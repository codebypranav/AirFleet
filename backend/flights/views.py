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
import inspect
from .openai_patch import create_safe_openai_client
from .direct_openai import create_direct_client

logger = logging.getLogger(__name__)

# Apply our OpenAI patches early
try:
    from .openai_patch import apply_openai_patches, clean_openai_environment
    # First clean environment
    clean_openai_environment()
    # Then apply patches
    apply_openai_patches()
    logger.info("Applied OpenAI patches at module level")
except Exception as e:
    logger.error(f"Failed to apply OpenAI patches: {e}")

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
        
        # Call the OpenAI API with proper error handling
        logger.info("Initializing OpenAI client")
        
        # Try approaches in order of preference:
        
        # 1. Try direct API access first (most reliable approach)
        try:
            logger.info("Attempting to use direct OpenAI client")
            from .direct_openai import create_direct_client
            client = create_direct_client(api_key=settings.OPENAI_API_KEY)
            
            logger.info("Sending request to OpenAI API via direct client")
            response = client.chat.create(
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
        except Exception as e1:
            logger.error(f"Direct client approach failed: {str(e1)}")
            
            # 2. Try our safe client creator
            try:
                logger.info("Attempting to create OpenAI client with safe_client_creator")
                from .openai_patch import create_safe_openai_client
                client = create_safe_openai_client(api_key=settings.OPENAI_API_KEY)
                
                logger.info("Sending request to OpenAI API")
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
            except Exception as e2:
                logger.error(f"Safe client approach failed: {str(e2)}")
                
                # 3. Direct import approach
                try:
                    logger.info("Attempting direct import approach")
                    # Import the module directly
                    from openai import OpenAI
                    # Create client with minimal parameters
                    client = OpenAI(api_key=settings.OPENAI_API_KEY)
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that creates engaging flight narratives based on flight data."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=250,
                        temperature=0.7,
                    )
                    narrative = response.choices[0].message.content.strip()
                    return Response({"narrative": narrative})
                except Exception as e3:
                    logger.error(f"Direct import approach failed: {str(e3)}")
                    
                    # 4. Last resort - no proxy approach
                    try:
                        logger.info("Attempting no-proxy approach")
                        import os
                        import importlib
                        
                        # Clear all proxy variables
                        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                                     'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
                        for var in proxy_vars:
                            if var in os.environ:
                                del os.environ[var]
                        
                        # Reload openai module
                        import openai
                        importlib.reload(openai)
                        
                        # Create client with absolute minimal approach
                        from openai import OpenAI
                        client = OpenAI(api_key=settings.OPENAI_API_KEY)
                        
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant that creates engaging flight narratives based on flight data."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=250,
                            temperature=0.7,
                        )
                        narrative = response.choices[0].message.content.strip()
                        return Response({"narrative": narrative})
                    except Exception as e4:
                        logger.error(f"All approaches failed. Errors: 1) {str(e1)}, 2) {str(e2)}, 3) {str(e3)}, 4) {str(e4)}")
                        return Response({"error": "Failed to generate narrative after multiple attempts"}, status=500)
    
    except Exception as e:
        logger.error(f"Error in generate_narrative: {str(e)}")
        return Response({"error": str(e)}, status=500)
