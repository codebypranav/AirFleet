from django.db.models import Count, Q
from rest_framework import serializers

from .models import Group, Membership

ACTIVE = Q(memberships__status='active', memberships__user__is_active=True)


def with_member_count(groups):
    return groups.annotate(member_count=Count('memberships', filter=ACTIVE))


class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Membership
        fields = ('id', 'username', 'role', 'status')

    def validate_status(self, value):
        if value != 'active':
            raise serializers.ValidationError("A request can only be approved; decline it instead.")
        return value


class GroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    my_membership = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ('slug', 'name', 'kind', 'is_official', 'description', 'member_count', 'my_membership')
        read_only_fields = ('slug', 'is_official')

    def mine(self, group):
        return self.context['mine'].get(group.pk)

    def get_my_membership(self, group):
        membership = self.mine(group)
        return membership and {'id': membership.pk, 'role': membership.role, 'status': membership.status}

    def validate_name(self, value):
        value = value.strip()
        taken = Group.objects.filter(name__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("A group with this name already exists.")
        return value

    def validate_kind(self, value):
        unchanged = self.instance and self.instance.kind == value
        if value == 'alliance' and not unchanged and not self.context['request'].user.is_staff:
            raise serializers.ValidationError("Alliances are set up by AirFleet staff.")
        return value

    def validate(self, attrs):
        group = self.instance
        if group and group.is_official and not self.context['request'].user.is_staff:
            if any(field in attrs and attrs[field] != getattr(group, field) for field in ('name', 'kind')):
                raise serializers.ValidationError("Contact AirFleet to rename an official group or change its kind.")
        return attrs


class GroupDetailSerializer(GroupSerializer):
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    private_count = serializers.SerializerMethodField()
    pending = serializers.SerializerMethodField()

    class Meta(GroupSerializer.Meta):
        fields = GroupSerializer.Meta.fields + ('parent', 'children', 'members', 'private_count', 'pending')

    def is_admin(self, group):
        membership = self.mine(group)
        return bool(membership and membership.role == 'admin')

    def active(self, group):
        return group.memberships.filter(status='active', user__is_active=True).select_related('user')

    def get_parent(self, group):
        return group.parent and {'slug': group.parent.slug, 'name': group.parent.name}

    def get_children(self, group):
        return list(with_member_count(group.children.all()).values('slug', 'name', 'member_count'))

    def get_members(self, group):
        members = self.active(group) if self.is_admin(group) else self.active(group).filter(user__is_public=True)
        return MembershipSerializer(members, many=True).data

    def get_private_count(self, group):
        return 0 if self.is_admin(group) else self.active(group).filter(user__is_public=False).count()

    def get_pending(self, group):
        if not self.is_admin(group):
            return []
        return MembershipSerializer(group.memberships.filter(status='pending').select_related('user'), many=True).data
