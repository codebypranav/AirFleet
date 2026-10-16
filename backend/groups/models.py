from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.text import slugify


class Group(models.Model):
    KIND_CHOICES = [
        ('airline', 'Airline'), ('operator', 'Operator'), ('school', 'Flight school'),
        ('alliance', 'Alliance'), ('community', 'Community'),
    ]

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, editable=False)
    description = models.TextField(blank=True, max_length=2000)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='community')
    is_official = models.BooleanField(default=False)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children',
        limit_choices_to={'kind': 'alliance'},
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_official', 'name']
        constraints = [models.UniqueConstraint(Lower('name'), name='unique_group_name_ci')]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:80] or 'group'
            self.slug, n = base, 2
            while Group.objects.filter(slug=self.slug).exists():
                self.slug, n = f'{base}-{n}', n + 1
        super().save(*args, **kwargs)


class Membership(models.Model):
    ROLE_CHOICES = [('admin', 'Admin'), ('member', 'Member')]
    STATUS_CHOICES = [('active', 'Active'), ('pending', 'Pending')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=6, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'group'], name='one_membership_per_group'),
            models.CheckConstraint(condition=~Q(role='admin', status='pending'), name='admins_are_active'),
        ]


@receiver(post_delete, sender=Membership)
def keep_an_admin(sender, instance, **kwargs):
    members = Membership.objects.filter(group_id=instance.group_id)
    if instance.role != 'admin' or members.filter(role='admin').exists():
        return
    successor = members.filter(status='active', user__is_active=True).first()
    if successor:
        successor.role = 'admin'
        successor.save(update_fields=['role'])
