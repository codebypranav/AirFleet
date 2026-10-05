import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from flights.models import Flight
from flights.views import FlightPagination
from .models import InstructorLink, Signature, attestation, flight_snapshot, snapshot_hash
from .serializers import (
    InstructorLinkSerializer, InviteSerializer, SignatureSerializer, SignSerializer, StudentFlightSerializer,
    display_name, latest_signature,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class InviteThrottle(UserRateThrottle):
    scope = 'invite'


def dual_flights(student):
    """The flights an instructor can see and sign: those with dual instruction received."""
    return (
        Flight.objects.filter(user=student, dual_received_time__gt=timedelta(0))
        .select_related('aircraft', 'user').prefetch_related('signatures')
    )


def needs_signature(flight):
    signature = latest_signature(flight)
    return signature is None or not signature.is_valid(flight)


def my_links(user):
    return InstructorLink.objects.filter(Q(student=user) | Q(instructor=user)).select_related('student', 'instructor')


def notify_invitee(link):
    invitee, inviter = link.invitee, link.invited_by
    role = 'instructor' if invitee == link.instructor else 'student'
    try:
        send_mail(
            subject=f"{display_name(inviter)} invited you on AirFleet",
            message=(
                f"Hi {invitee.username},\n\n"
                f"{display_name(inviter)} ({inviter.username}) asked to add you as their {role} on AirFleet. "
                f"Accept or decline here:\n\n{settings.FRONTEND_URL.rstrip('/')}/instruction\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitee.email],
        )
    except Exception:
        logger.exception("Could not send instructor invitation email for link %s", link.pk)


class LinksView(APIView):
    """GET: my students and instructors, including open invitations. POST: invite someone."""
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        return [InviteThrottle()] if self.request.method == 'POST' else []

    def get(self, request):
        result = list(my_links(request.user).exclude(status=InstructorLink.ENDED))
        for link in result:
            if link.instructor_id == request.user.pk and link.status == InstructorLink.ACTIVE:
                link.unsigned_flights = sum(needs_signature(f) for f in dual_flights(link.student))
        return Response(InstructorLinkSerializer(result, many=True, context={'request': request}).data)

    def post(self, request):
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        who = serializer.validated_data['invitee'].strip()
        other = User.objects.filter(Q(username__iexact=who) | Q(email__iexact=who), is_active=True).first()
        if other is None:
            return Response({'invitee': ["No AirFleet pilot has that username or email."]}, status=400)
        if other == request.user:
            return Response({'invitee': ["You can't invite yourself."]}, status=400)

        if serializer.validated_data['invitee_role'] == 'instructor':
            student, instructor = request.user, other
        else:
            student, instructor = other, request.user
        if not instructor.instructor_certificate_number:
            message = (
                f"{other.username} hasn't added an instructor certificate to their profile yet." if instructor == other
                else "Add your instructor certificate on your profile before inviting students."
            )
            return Response({'invitee': [message]}, status=400)

        try:
            with transaction.atomic():
                link = InstructorLink.objects.create(student=student, instructor=instructor, invited_by=request.user)
        except IntegrityError:
            return Response({'invitee': [f"You already have a link or invitation with {other.username}."]}, status=400)
        notify_invitee(link)
        return Response(InstructorLinkSerializer(link, context={'request': request}).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_link(request, pk):
    link = get_object_or_404(my_links(request.user), pk=pk, status=InstructorLink.PENDING)
    if link.invited_by_id == request.user.pk:
        return Response({'error': "Waiting for the other pilot to accept."}, status=400)
    link.status = InstructorLink.ACTIVE
    link.accepted_at = timezone.now()
    link.save(update_fields=['status', 'accepted_at'])
    return Response(InstructorLinkSerializer(link, context={'request': request}).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def end_link(request, pk):
    """Decline or withdraw an invitation, or end the link. Signatures already given stay."""
    link = get_object_or_404(my_links(request.user).exclude(status=InstructorLink.ENDED), pk=pk)
    link.status = InstructorLink.ENDED
    link.ended_at = timezone.now()
    link.save(update_fields=['status', 'ended_at'])
    return Response(status=status.HTTP_204_NO_CONTENT)


def student_of(request, pk):
    link = get_object_or_404(InstructorLink, pk=pk, instructor=request.user, status=InstructorLink.ACTIVE)
    return link.student


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_flights(request, pk):
    """A student's dual flights for their instructor. ?unsigned=true for those still to sign."""
    flights = dual_flights(student_of(request, pk))
    if request.query_params.get('unsigned') == 'true':
        flights = [f for f in flights if needs_signature(f)]
    paginator = FlightPagination()
    page = paginator.paginate_queryset(flights, request)
    return paginator.get_paginated_response(StudentFlightSerializer(page, many=True, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sign_flight(request, pk):
    """Sign a student's dual flight. Records the entry as it stands and the instructor's certificate."""
    instructor = request.user
    students = InstructorLink.objects.filter(instructor=instructor, status=InstructorLink.ACTIVE).values('student')
    flight = get_object_or_404(Flight.objects.select_related('user'), pk=pk, user__in=students)

    serializer = SignSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    if not flight.dual_received_time:
        return Response({'error': "Only flights with dual instruction received can be signed."}, status=400)
    if not instructor.instructor_certificate_number:
        return Response({'error': "Add your instructor certificate number on your profile first."}, status=400)
    expires = instructor.instructor_certificate_expires
    if expires and expires < max(timezone.now().date(), flight.departure_time.date()):
        return Response({'error': f"Your instructor certificate on file expired on {expires:%Y-%m-%d}."}, status=400)

    with transaction.atomic():
        # Lock the flight so a concurrent edit can't slip between the snapshot and the save.
        flight = Flight.objects.select_for_update().select_related('user').get(pk=flight.pk)
        current = flight.signatures.first()
        if current and current.is_valid(flight):
            return Response({'error': f"Already signed by {current.instructor_name}."}, status=409)
        snapshot = flight_snapshot(flight)
        signature = Signature.objects.create(
            flight=flight,
            instructor=instructor,
            instructor_name=display_name(instructor),
            certificate_number=instructor.instructor_certificate_number,
            certificate_expires=expires,
            statement=attestation(flight, instructor),
            remarks=serializer.validated_data.get('remarks', ''),
            flight_snapshot=snapshot,
            flight_hash=snapshot_hash(snapshot),
        )
    logger.info("Instructor %s signed flight %s", instructor.pk, flight.pk)
    return Response(SignatureSerializer(signature).data, status=201)
