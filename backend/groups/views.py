from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Group, Membership
from .serializers import GroupDetailSerializer, GroupSerializer, MembershipSerializer, with_member_count

CREATE_LIMIT = 5


def context(request):
    return {'request': request, 'mine': {m.group_id: m for m in Membership.objects.filter(user=request.user)}}


def detail(request, slug, code=status.HTTP_200_OK):
    group = get_object_or_404(with_member_count(Group.objects.select_related('parent')), slug=slug)
    return Response(GroupDetailSerializer(group, context=context(request)).data, status=code)


def is_admin(user, group):
    return group.memberships.filter(user=user, role='admin').exists()


def last_admin(membership):
    return membership.role == 'admin' and not membership.group.memberships.filter(role='admin').exclude(pk=membership.pk).exists()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def groups(request):
    if request.method == 'GET':
        found = with_member_count(Group.objects.all())
        if q := request.query_params.get('q', '').strip():
            found = found.filter(name__icontains=q)
        if request.query_params.get('mine') == '1':
            found = found.filter(memberships__user=request.user)
        else:
            found = found[:50]
        return Response(GroupSerializer(found, many=True, context=context(request)).data)

    serializer = GroupSerializer(data=request.data, context=context(request))
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if Group.objects.filter(created_by=request.user).count() >= CREATE_LIMIT:
            return Response({'error': f"You can create up to {CREATE_LIMIT} groups."}, status=400)
        group = serializer.save(created_by=request.user)
        if group.kind != 'alliance':
            Membership.objects.create(user=request.user, group=group, role='admin')
    return detail(request, group.slug, status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def group(request, slug):
    if request.method == 'GET':
        return detail(request, slug)

    group = get_object_or_404(Group, slug=slug)
    admin = is_admin(request.user, group)
    if request.method == 'DELETE':
        if not (request.user.is_staff or (admin and not group.is_official)):
            message = "Only AirFleet staff can delete an official group." if admin else "Only the group's admins can delete it."
            return Response({'error': message}, status=403)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if not admin:
        return Response({'error': "Only the group's admins can edit it."}, status=403)
    serializer = GroupSerializer(group, data=request.data, partial=True, context=context(request))
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return detail(request, slug)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members(request, slug):
    group = get_object_or_404(Group, slug=slug)
    if group.kind == 'alliance':
        return Response({'error': "Alliances are joined through their member airlines."}, status=400)
    membership, created = Membership.objects.get_or_create(
        user=request.user, group=group, defaults={'status': 'pending' if group.is_official else 'active'},
    )
    return Response(MembershipSerializer(membership).data, status=201 if created else 200)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def member(request, slug, pk):
    group = get_object_or_404(Group.objects.select_for_update(), slug=slug)
    membership = get_object_or_404(group.memberships.select_related('user', 'group'), pk=pk)
    admin = is_admin(request.user, group)

    if request.method == 'DELETE':
        own = membership.user_id == request.user.pk
        if not (own or (admin and membership.role != 'admin')):
            message = "Admins can't remove other admins." if admin else "Only the group's admins can remove members."
            return Response({'error': message}, status=403)
        if last_admin(membership):
            return Response({'error': "Make another member an admin first, or delete the group."}, status=400)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if not admin:
        return Response({'error': "Only the group's admins can manage members."}, status=403)
    serializer = MembershipSerializer(membership, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    changes = serializer.validated_data
    if 'role' in changes and changes.get('status', membership.status) != 'active':
        return Response({'error': "Approve the request before changing the role."}, status=400)
    if changes.get('role') == 'member' and last_admin(membership):
        return Response({'error': "A group needs at least one admin."}, status=400)
    serializer.save()
    return Response(serializer.data)
