from django.contrib import admin

from .models import InstructorLink, Signature


@admin.register(InstructorLink)
class InstructorLinkAdmin(admin.ModelAdmin):
    list_display = ('student', 'instructor', 'status', 'created_at', 'accepted_at')
    list_filter = ('status',)
    search_fields = ('student__username', 'instructor__username')
    raw_id_fields = ('student', 'instructor', 'invited_by')


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ('flight', 'instructor_name', 'certificate_number', 'signed_at')
    search_fields = ('instructor_name', 'certificate_number', 'flight__user__username')
    raw_id_fields = ('flight', 'instructor')
    # A signature records what was signed; editing it here would defeat the point.
    readonly_fields = [f.name for f in Signature._meta.fields]
