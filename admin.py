from django.contrib import admin
from django.utils.html import format_html
from .models import RegisteredFace

@admin.register(RegisteredFace)
class RegisteredFaceAdmin(admin.ModelAdmin):
    list_display = ['photo_preview', 'name', 'registered_at', 'delete_button']
    list_display_links = ['name']
    readonly_fields = ['registered_at', 'photo_preview_large']
    search_fields = ['name']
    ordering = ['-registered_at']

    fieldsets = (
        ('Person Details', {
            'fields': ('name', 'image', 'photo_preview_large', 'registered_at')
        }),
    )

    def photo_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:48px;height:48px;'
                'object-fit:cover;border-radius:4px;border:1px solid #e5e7eb"/>',
                obj.image.url
            )
        return '—'
    photo_preview.short_description = 'Photo'

    def photo_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:200px;height:200px;'
                'object-fit:cover;border-radius:8px;border:1px solid #e5e7eb"/>',
                obj.image.url
            )
        return '—'
    photo_preview_large.short_description = 'Preview'

    def delete_button(self, obj):
        return format_html(
            '<a href="{}/delete/" style="'
            'background:#dc2626;color:#fff;padding:4px 12px;'
            'border-radius:4px;font-size:12px;font-weight:600;'
            'text-decoration:none;">Delete</a>',
            obj.pk
        )
    delete_button.short_description = 'Action'

    class Media:
        css = {
            'all': ('dashboard/css/admin_custom.css',)
        }