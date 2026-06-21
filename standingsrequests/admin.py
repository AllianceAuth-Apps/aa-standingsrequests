from typing import Optional

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveEntity

from standingsrequests.models import (
    AbstractStandingsRequest,
    Contact,
    ContactLabel,
    ContactSet,
    RequestLogEntry,
    StandingRequest,
    StandingRevocation,
)


class AbstractStandingsRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "_contact_type_str",
        "_contact_name",
        "_user",
        "request_date",
        "action_by",
        "action_date",
        "is_effective",
        "effective_date",
    )
    list_filter = ("is_effective",)
    list_select_related = True
    ordering = ("-id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display
    def _contact_name(self, obj: AbstractStandingsRequest):
        return EveEntity.objects.resolve_name(obj.contact_id)

    @admin.display(description="contact type")
    def _contact_type_str(self, obj: AbstractStandingsRequest):
        if obj.is_character:
            return "Character"

        if obj.is_corporation:
            return "Corporation"

        return "(undefined)"

    def _user(self, obj: AbstractStandingsRequest):
        try:
            return obj.user
        except AttributeError:
            return None


@admin.register(StandingRequest)
class StandingsRequestAdmin(AbstractStandingsRequestAdmin):
    pass


@admin.register(StandingRevocation)
class StandingsRevocationAdmin(AbstractStandingsRequestAdmin):
    pass


@admin.register(RequestLogEntry)
class RequestLogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "request_type",
        "_requested_for",
        "_requested_by",
        "requested_at",
        "_reason",
        "action",
        "_action_by",
    )
    list_display_links = None
    list_filter = (
        "request_type",
        ("action_by", admin.RelatedOnlyFieldListFilter),
        ("requested_by", admin.RelatedOnlyFieldListFilter),
        "created_at",
        "reason",
    )
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "action_by__character",
            "action_by__corporation",
            "requested_by__character",
            "requested_by__corporation",
            "requested_for__character",
            "requested_for__corporation",
        )

    def has_change_permission(self, *args, **kwargs):
        return False

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs) -> bool:
        return False

    @admin.display(ordering="action_by")
    def _action_by(self, obj: RequestLogEntry) -> str:
        return "SYSTEM" if obj.action_by is None else obj.action_by.html()

    @admin.display(ordering="requested_by")
    def _requested_by(self, obj: RequestLogEntry) -> str:
        return obj.requested_by.html()

    @admin.display(ordering="requested_for")
    def _requested_for(self, obj: RequestLogEntry) -> str:
        return obj.requested_for.html()

    @admin.display(ordering="reason")
    def _reason(self, obj: RequestLogEntry) -> Optional[str]:
        reason_obj = StandingRequest.Reason(obj.reason)
        return None if reason_obj is StandingRequest.Reason.NONE else reason_obj.label


class ContactCategoryFilter(admin.SimpleListFilter):
    title = _("category")
    parameter_name = "category"

    def lookups(self, request, model_admin):
        categories = sorted(
            set(
                model_admin.get_queryset(request).values_list(
                    "eve_entity__category", flat=True
                )
            )
        )
        result = [(o, o) for o in categories]
        return result

    def queryset(self, request, queryset):
        v = self.value()
        if not v:
            return queryset.all()

        return queryset.filter(eve_entity__category=v)


class ContactLabelFilter(admin.SimpleListFilter):
    title = _("label")
    parameter_name = "label"

    def lookups(self, request, model_admin):
        cs = ContactSet.objects.latest()
        if not cs:
            return []

        labels = ContactLabel.objects.filter(contact_set=cs).order_by("name")
        result = [(o.label_id, o.name) for o in labels]
        return result

    def queryset(self, request, queryset):
        v = self.value()
        if not v:
            return queryset.all()

        return queryset.filter(labels__label_id=v)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        "_name",
        "_category",
        "standing",
        "_labels",
    )
    list_filter = [ContactCategoryFilter, "standing", ContactLabelFilter]
    ordering = ("eve_entity__name",)
    exclude = ["contact_set"]

    @admin.display(ordering="eve_entity__name")
    def _name(self, obj):
        return obj.eve_entity.name

    @admin.display(ordering="eve_entity__category")
    def _category(self, obj):
        return obj.eve_entity.category

    def _labels(self, obj):
        qs = obj.labels.all()
        return ", ".join([obj.name for obj in qs])

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        cs = ContactSet.objects.latest()
        if not cs:
            return Contact.objects.none()

        return (
            qs.filter(contact_set=cs)
            .select_related("eve_entity")
            .prefetch_related("labels")
        )

    def has_change_permission(self, *args, **kwargs):
        return False

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_delete_permission(self, *args, **kwargs) -> bool:
        return False
