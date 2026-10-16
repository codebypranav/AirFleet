from django.contrib import admin

from .models import Group, Membership


class NeedsAdminFilter(admin.SimpleListFilter):
    title = 'admin'
    parameter_name = 'admin'

    def lookups(self, request, model_admin):
        return [('none', 'Needs an admin')]

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.exclude(kind='alliance').exclude(memberships__role='admin')
        return queryset


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'is_official', 'parent', 'created_by', 'created_at')
    list_filter = ('kind', 'is_official', NeedsAdminFilter)
    search_fields = ('name', 'slug')
    raw_id_fields = ('created_by', 'parent')
    readonly_fields = ('slug',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('group', 'user', 'role', 'status', 'created_at')
    list_filter = ('role', 'status')
    search_fields = ('group__name', 'user__username')
    raw_id_fields = ('user', 'group')
