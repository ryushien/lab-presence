from django.contrib import admin, messages

from .models import Card, Device, Member, StatusLog


class CardInline(admin.TabularInline):
    model = Card
    extra = 0
    fields = ("label", "first_seen_at", "last_seen_at")
    readonly_fields = ("first_seen_at", "last_seen_at")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "grade", "status", "note", "status_updated_at", "is_active")
    list_filter = ("status", "grade", "is_active")
    list_editable = ("grade",)
    inlines = [CardInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    """未登録カードはここに出るので、持ち主を選んで保存する。"""

    list_display = ("__str__", "member", "label", "last_seen_at")
    list_filter = (("member", admin.EmptyFieldListFilter),)
    list_editable = ("member", "label")
    ordering = ("-last_seen_at",)


@admin.register(StatusLog)
class StatusLogAdmin(admin.ModelAdmin):
    list_display = ("member", "status", "source", "note", "created_at")
    list_filter = ("source", "status", "member")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "last_seen_at")
    actions = ["issue_new_key"]

    @admin.action(description="APIキーを（再）発行する")
    def issue_new_key(self, request, queryset):
        for device in queryset:
            raw = device.issue_key()
            messages.warning(request, f"{device.name}: {raw} （この画面でしか表示されません）")

    def save_model(self, request, obj, form, change):
        if not change:
            raw = obj.issue_key()
            messages.warning(request, f"{obj.name} のAPIキー: {raw} （この画面でしか表示されません）")
        else:
            super().save_model(request, obj, form, change)
