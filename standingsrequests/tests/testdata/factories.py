import urllib.parse
from typing import Generic, TypeVar

import factory
import factory.fuzzy

# import datetime as dt
# from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveEntityFactionFactory,
)

from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory

from standingsrequests.core.contact_types import ContactTypeId
from standingsrequests.helpers.evecorporation import EveCorporation
from standingsrequests.models import (
    AbstractStandingsRequest,
    CharacterAffiliation,
    Contact,
    ContactSet,
    StandingRequest,
    StandingRevocation,
)

T = TypeVar("T")
_BASE_URL = "https://esi.evetech.net/"


def make_esi_url(path: str) -> str:
    if path.startswith("/"):
        raise ValueError("path can not start with a slash")
    if path.endswith("/"):
        raise ValueError("path can not end with a slash")

    url = urllib.parse.urljoin(_BASE_URL, "latest/" + path + "/")
    return url


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class EveCorporationFactory(factory.Factory, metaclass=BaseMetaFactory[EveCorporation]):
    class Meta:
        model = EveCorporation

    corporation_id = factory.Sequence(lambda n: 98_900_001 + n)
    corporation_name = factory.LazyAttribute(
        lambda o: f"corporation_{o.corporation_id}"
    )
    corporation_ticker = factory.LazyAttribute(
        lambda obj: obj.corporation_name[:4].upper()
    )
    member_count = factory.fuzzy.FuzzyInteger(10, 1000)
    ceo_id = factory.fuzzy.FuzzyInteger(90_800_001, 90_900_001)


class UserMainRequestorFactory(UserMainFactory):
    permissions__ = [
        "standingsrequests.request_standings",
    ]


class UserMainApproverFactory(UserMainFactory):
    permissions__ = [
        "standingsrequests.affect_standings",
        "standingsrequests.view",
    ]


class CharacterAffiliationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CharacterAffiliation]
):
    class Meta:
        model = CharacterAffiliation

    class Params:
        is_eve_character = factory.Trait(
            eve_character=factory.SubFactory(
                EveCharacterFactory, corporation__create_alliance=True
            ),
            alliance=factory.LazyAttribute(
                lambda o: EveEntityCharacterFactory(
                    id=o.eve_character.alliance_id, name=o.eve_character.alliance_name
                )
            ),
            character=factory.LazyAttribute(
                lambda o: EveEntityCharacterFactory(
                    id=o.eve_character.character_id, name=o.eve_character.character_name
                )
            ),
            corporation=factory.LazyAttribute(
                lambda o: EveEntityCharacterFactory(
                    id=o.eve_character.corporation_id,
                    name=o.eve_character.corporation_name,
                )
            ),
            faction=None,
        )

    alliance = factory.SubFactory(EveEntityAllianceFactory)
    character = factory.SubFactory(EveEntityCharacterFactory)
    corporation = factory.SubFactory(EveEntityCorporationFactory)
    faction = factory.SubFactory(EveEntityFactionFactory)


class ContactSetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[ContactSet]
):
    class Meta:
        model = ContactSet

    name = factory.Sequence(lambda o: f"ContactSet #{o + 1}")


class ContactCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Contact]
):
    class Meta:
        model = Contact

    contact_set = factory.SubFactory(ContactSetFactory)
    eve_entity = factory.SubFactory(EveEntityCharacterFactory)
    standing = factory.fuzzy.FuzzyFloat(-10, 10)
    is_watched = False


class StandingRequestCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[StandingRequest]
):
    class Meta:
        model = StandingRequest

    action_by = None
    action_date = None
    contact_id = factory.fuzzy.FuzzyInteger(90_800_001, 90_900_001)
    contact_type_id = factory.LazyFunction(ContactTypeId.character_id)
    effective_date = None
    is_effective = False
    reason = AbstractStandingsRequest.Reason.NONE
    user = factory.SubFactory(UserMainRequestorFactory)


class StandingRevocationCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[StandingRevocation]
):
    class Meta:
        model = StandingRevocation

    action_by = None
    action_date = None
    contact_id = factory.fuzzy.FuzzyInteger(90_800_001, 90_900_001)
    contact_type_id = factory.LazyFunction(ContactTypeId.character_id)
    effective_date = None
    is_effective = False
    reason = AbstractStandingsRequest.Reason.NONE
    user = factory.SubFactory(UserMainRequestorFactory)
