from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db.models import Count, Exists, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .models import Comment, Flight, Like, Notification, blocked_with

MAX_COMMENT = 500
RETENTION = timedelta(days=90)


def flight_for(viewer, pk):
    return get_object_or_404(Flight.objects.open_to(viewer), pk=pk)


def visible_comments(viewer):
    return Comment.objects.exclude(blocked_with(viewer, 'author')).exclude(blocked_with(viewer, 'parent__author'))


def with_counts(viewer, flights):
    comments = (
        visible_comments(viewer).filter(flight=OuterRef('pk'), author__isnull=False)
        .order_by().values('flight').annotate(n=Count('pk')).values('n')
    )
    return flights.annotate(
        like_count=Count('likes', filter=Q(likes__comment=None)),
        liked=Exists(Like.objects.filter(flight=OuterRef('pk'), comment=None, user=viewer)),
        comment_count=Coalesce(Subquery(comments, output_field=IntegerField()), Value(0)),
    )


def _with_likes(viewer, comments):
    return comments.select_related('author', 'flight').annotate(
        like_count=Count('likes'), liked=Exists(Like.objects.filter(comment=OuterRef('pk'), user=viewer)),
    )


def thread(viewer, flight):
    replies = Prefetch('replies', _with_likes(viewer, visible_comments(viewer)))
    tops = _with_likes(viewer, visible_comments(viewer).filter(flight=flight, parent=None)).prefetch_related(replies)
    return [c for c in tops if c.author_id or c.replies.all()]


def _clean(body):
    body = body.strip() if isinstance(body, str) else ''
    if not body:
        raise ValidationError({'body': ['Write something first.']})
    if len(body) > MAX_COMMENT:
        raise ValidationError({'body': [f'Keep it to {MAX_COMMENT} characters.']})
    return body


def comment(viewer, flight, body, parent_id=None):
    body = _clean(body)
    parent = None
    if parent_id is not None:
        if type(parent_id) is not int:
            raise ValidationError({'parent': ['Reply to a comment by its id.']})
        parent = get_object_or_404(visible_comments(viewer), pk=parent_id, flight=flight)
        parent = parent.parent or parent
    created = Comment.objects.create(flight=flight, author=viewer, parent=parent, body=body)
    _notify(created, viewer, [flight.user, parent and parent.author])
    return created


def edit(viewer, pk, body):
    target = get_object_or_404(visible_comments(viewer), pk=pk, author=viewer)
    flight_for(viewer, target.flight_id)
    target.body, target.edited = _clean(body), True
    target.save(update_fields=['body', 'edited'])
    return target


def delete(viewer, pk):
    target = get_object_or_404(Comment.objects.select_related('flight'), pk=pk, author__isnull=False)
    if target.flight.user_id != viewer.pk and not (
        target.author_id == viewer.pk
        and visible_comments(viewer).filter(pk=target.pk).exists()
        and Flight.objects.open_to(viewer).filter(pk=target.flight_id).exists()
    ):
        raise NotFound()
    _remove(target)


@transaction.atomic
def _remove(target):
    if target.replies.exists():
        target.likes.all().delete()
        Notification.objects.filter(Q(comment=target) | Q(comment__parent=target, recipient_id=target.author_id)).delete()
        Comment.objects.filter(pk=target.pk).update(author=None, body='', edited=False)
        return
    parent = target.parent
    target.delete()
    if parent and parent.author_id is None and not parent.replies.exists():
        parent.delete()


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def forget(sender, instance, **kwargs):
    for written in instance.comments.order_by(F('parent').asc(nulls_last=True)):
        _remove(written)


def comment_for_like(viewer, pk):
    target = get_object_or_404(visible_comments(viewer), pk=pk, author__isnull=False)
    return flight_for(viewer, target.flight_id), target


def set_like(viewer, flight, on, target=None):
    if on:
        like, created = Like.objects.get_or_create(user=viewer, flight=flight, comment=target)
        if created:
            _notify(like, viewer, [target.author if target else flight.user])
    else:
        Like.objects.filter(user=viewer, flight=flight, comment=target).delete()
    return {'liked': on, 'like_count': Like.objects.filter(flight=flight, comment=target).count()}


def _notify(cause, actor, recipients):
    ids = {r.pk for r in recipients if r and r.pk != actor.pk and r.is_active}
    ids -= set(get_user_model().objects.filter(Q(pk__in=ids) & blocked_with(actor, 'pk')).values_list('pk', flat=True))
    field = type(cause).__name__.lower()
    Notification.objects.bulk_create([Notification(recipient_id=pk, **{field: cause}) for pk in ids], ignore_conflicts=True)


def notify_follow(follow):
    _notify(follow, follow.follower, [follow.pilot])


def notify_approved(follows):
    for follow in follows:
        _notify(follow, follow.pilot, [follow.follower])


def _visible_notifications(viewer):
    flights = Flight.objects.open_to(viewer).values('pk')
    return (
        viewer.notifications
        .filter(created_at__gte=timezone.now() - RETENTION)
        .filter(Q(follow__isnull=False) | Q(comment__flight__in=flights) | Q(like__flight__in=flights))
        .exclude(blocked_with(viewer, 'comment__author'))
        .exclude(blocked_with(viewer, 'comment__parent__author'))
        .exclude(blocked_with(viewer, 'like__user'))
        .exclude(blocked_with(viewer, 'like__comment__parent__author'))
    )


def notifications(viewer):
    viewer.notifications.filter(created_at__lt=timezone.now() - RETENTION).delete()
    shown = list(_visible_notifications(viewer).select_related(
        'follow__follower', 'follow__pilot', 'comment__author', 'comment__parent', 'comment__flight', 'like__user', 'like__flight',
    ))
    Notification.objects.filter(pk__in=[n.pk for n in shown if not n.read]).update(read=True)
    return shown


def unread_count(viewer):
    return _visible_notifications(viewer).filter(read=False).count()
