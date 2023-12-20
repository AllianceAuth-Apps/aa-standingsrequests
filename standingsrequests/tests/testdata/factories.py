from typing import Generic, TypeVar

import factory
import factory.fuzzy

from eveuniverse.models import EveEntity

from app_utils.testdata_factories import UserMainFactory

from standingsrequests.models import (
    AbstractStandingsRequest,
    Contact,
    ContactSet,
    StandingRequest,
    StandingRevocation,
)

from .entity_type_ids import CHARACTER_TYPE_ID, CORPORATION_TYPE_ID

T = TypeVar("T")


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class RequestorUserMainFactory(UserMainFactory):
    main_character__scopes = ContactSet.required_esi_scope()
    permissions__ = ["standingsrequests.request_standings"]


class ManagerUserMainFactory(UserMainFactory):
    main_character__scopes = ContactSet.required_esi_scope()
    permissions__ = ["standingsrequests.affect_standings"]


class ContactSetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[ContactSet]
):
    class Meta:
        model = ContactSet

    name = factory.faker.Faker("city")


class ContactFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Contact]
):
    class Meta:
        model = Contact

    contact_set = factory.SubFactory(ContactSetFactory)
    standing = factory.fuzzy.FuzzyFloat(-10, 10)

    @factory.lazy_attribute
    def eve_entity(obj):
        entity = (
            EveEntity.objects.filter(category=EveEntity.CATEGORY_CHARACTER)
            .order_by("?")
            .first()
        )
        return entity


class AbstractStandingsRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AbstractStandingsRequest
        exclude = ("contact_entity",)

    user = factory.SubFactory(RequestorUserMainFactory)

    @factory.lazy_attribute
    def contact_entity(obj):
        if obj.contact_id:
            try:
                return EveEntity.objects.get(id=obj.contact_id)
            except EveEntity.DoesNotExist:
                return None

        return (
            EveEntity.objects.filter(category=EveEntity.CATEGORY_CHARACTER)
            .order_by("?")
            .first()
        )

    @factory.lazy_attribute
    def contact_id(obj):
        return obj.contact_entity.id

    @factory.lazy_attribute
    def contact_type_id(obj):
        if not obj.contact_entity:
            return None

        return (
            CORPORATION_TYPE_ID
            if obj.contact_entity.is_corporation
            else CHARACTER_TYPE_ID
        )


class StandingRequestFactory(
    AbstractStandingsRequestFactory, metaclass=BaseMetaFactory[StandingRequest]
):
    class Meta:
        model = StandingRequest


class StandingRevocationFactory(
    AbstractStandingsRequestFactory, metaclass=BaseMetaFactory[StandingRevocation]
):
    class Meta:
        model = StandingRevocation

    reason = StandingRevocation.Reason.OWNER_REQUEST
