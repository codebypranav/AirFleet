from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, ValidationError

from .models import Block, Follow


def pilot_named(viewer, username, blockable=False):
    pilot = get_user_model().objects.filter(username__iexact=username.strip(), is_active=True).exclude(pk=viewer.pk).first()
    blocked = Block.objects.filter(Q(blocker=pilot, blocked=viewer) | Q(blocker=viewer, blocked=pilot)).exists()
    if pilot is None or (blocked and not blockable):
        raise ValidationError({'username': [f"No AirFleet pilot is called {username.strip()}."]})
    return pilot


def follow(viewer, username):
    pilot = pilot_named(viewer, username)
    status = Follow.APPROVED if pilot.is_public else Follow.PENDING
    return Follow.objects.get_or_create(follower=viewer, pilot=pilot, defaults={'status': status})[0]


def unfollow(viewer, username):
    Follow.objects.filter(follower=viewer, pilot__username__iexact=username).delete()


def approve(pilot, username):
    if not Follow.objects.filter(pilot=pilot, follower__username__iexact=username).update(status=Follow.APPROVED):
        raise NotFound(f"{username} hasn't asked to follow you.")


def remove(pilot, username):
    Follow.objects.filter(pilot=pilot, follower__username__iexact=username).delete()


@transaction.atomic
def block(viewer, username):
    pilot = pilot_named(viewer, username, blockable=True)
    Block.objects.get_or_create(blocker=viewer, blocked=pilot)
    Follow.objects.filter(Q(follower=viewer, pilot=pilot) | Q(follower=pilot, pilot=viewer)).delete()


def unblock(viewer, username):
    Block.objects.filter(blocker=viewer, blocked__username__iexact=username).delete()


def approve_waiting(pilot):
    if pilot.is_public:
        pilot.followers.filter(status=Follow.PENDING).update(status=Follow.APPROVED)


def follower_counts(usernames):
    approved = Follow.objects.filter(status=Follow.APPROVED, follower__is_active=True, pilot__username__in=usernames)
    return dict(approved.order_by().values('pilot__username').annotate(n=Count('pk')).values_list('pilot__username', 'n'))
