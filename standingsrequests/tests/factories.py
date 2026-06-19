import itertools
import urllib.parse
from typing import Generic, TypeVar

import factory
import factory.fuzzy

# import datetime as dt
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveEntityFactionFactory,
)

from allianceauth.authentication.models import State
from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory

from standingsrequests.core.contact_types import ContactTypeId
from standingsrequests.helpers.eve_corporation import EveCorporationHelper
from standingsrequests.models import (
    AbstractStandingsRequest,
    CharacterAffiliation,
    Contact,
    ContactSet,
    CorporationDetails,
    FrozenAlt,
    FrozenAuthUser,
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


class StateFactory(factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[State]):
    class Meta:
        model = State

    name = factory.LazyAttribute(lambda o: f"State #{o.priority}")
    priority = factory.Sequence(lambda n: n + 900)
    public = False

    @factory.post_generation
    def permissions(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.permissions.add(*extracted)

    @factory.post_generation
    def member_characters(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_characters.add(*extracted)

    @factory.post_generation
    def member_corporations(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_corporations.add(*extracted)

    @factory.post_generation
    def member_alliances(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_alliances.add(*extracted)

    @factory.post_generation
    def member_factions(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.member_factions.add(*extracted)


_eve_corporation_id_sequence = itertools.count(start=98_900_001)


class EveCorporationHelperFactory(
    factory.Factory, metaclass=BaseMetaFactory[EveCorporationHelper]
):

    class Meta:
        model = EveCorporationHelper

    class Params:
        corporation = None  # when set will copy attributes

    @factory.lazy_attribute
    def corporation_id(self):
        if not self.corporation:
            return next(_eve_corporation_id_sequence)
        return self.corporation.corporation_id

    @factory.lazy_attribute
    def corporation_name(self):
        if not self.corporation:
            return f"corporation_{self.corporation_id}"
        return self.corporation.corporation_name

    @factory.lazy_attribute
    def ticker(self):
        if not self.corporation:
            return self.corporation_name[:4].upper()
        return self.corporation.corporation_ticker

    @factory.lazy_attribute
    def member_count(self):
        if not self.corporation:
            return factory.fuzzy.FuzzyInteger(10, 1000).fuzz()
        return self.corporation.member_count

    @factory.lazy_attribute
    def ceo_id(self):
        if not self.corporation:
            return factory.fuzzy.FuzzyInteger(90_800_001, 90_900_001).fuzz()
        return self.corporation.ceo_id


class UserMainRequestorFactory(UserMainFactory):
    permissions__ = [
        "standingsrequests.request_standings",
    ]


class UserMainApproverFactory(UserMainFactory):
    permissions__ = [
        "standingsrequests.affect_standings",
        "standingsrequests.request_standings",
        "standingsrequests.view",
    ]


class UserMainOwnerFactory(UserMainFactory):
    main_character__scopes = [
        "esi-alliances.read_contacts.v1",
        "esi-corporations.read_contacts.v1",
    ]
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


class CorporationDetailsFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[CorporationDetails]
):
    class Meta:
        model = CorporationDetails

    class Params:
        eve_corporation = None

    faction = None

    @factory.lazy_attribute
    def corporation(self):
        if not self.eve_corporation:
            return EveEntityCorporationFactory()
        return EveEntityCorporationFactory(
            id=self.eve_corporation.corporation_id,
            name=self.eve_corporation.corporation_name,
        )

    @factory.lazy_attribute
    def alliance(self):
        if not self.eve_corporation:
            return EveEntityAllianceFactory()
        if not self.eve_corporation.alliance:
            return None
        return EveEntityAllianceFactory(
            id=self.eve_corporation.alliance.id,
            name=self.eve_corporation.alliance.alliance_name,
        )

    @factory.lazy_attribute
    def ceo(self):
        if not self.eve_corporation or not self.eve_corporation.ceo_id:
            return EveEntityCharacterFactory()
        return EveEntityCharacterFactory(id=self.eve_corporation.ceo_id)

    @factory.lazy_attribute
    def member_count(self):
        if not self.eve_corporation:
            return factory.fuzzy.FuzzyInteger(10, 1000).fuzz()
        return self.eve_corporation.member_count

    @factory.lazy_attribute
    def ticker(self):
        if not self.eve_corporation:
            return self.corporation.name[:4].upper()
        return self.eve_corporation.corporation_ticker


class ContactSetFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[ContactSet]
):
    class Meta:
        model = ContactSet

    name = factory.Sequence(lambda o: f"ContactSet #{o + 1}")

    @factory.post_generation
    def contacts(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        for _ in range(extracted):
            ContactCharacterFactory(contact_set=self)

    @factory.post_generation
    def date(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        # needed to overwrite date set by auto date
        self.date = extracted
        self.save()


class _ContactFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Contact]
):
    class Meta:
        model = Contact

    contact_set = factory.SubFactory(ContactSetFactory)
    standing = factory.fuzzy.FuzzyChoice([-10.0, -5.0, 5.0, 10.0])
    is_watched = False


class ContactAllianceFactory(_ContactFactory):
    class Params:
        contact_id = None

    @factory.lazy_attribute
    def eve_entity(self):
        if self.contact_id:
            return EveEntityAllianceFactory(id=self.contact_id)
        return EveEntityAllianceFactory()


class ContactCharacterFactory(_ContactFactory):
    class Params:
        contact_id = None

    @factory.lazy_attribute
    def eve_entity(self):
        if self.contact_id:
            return EveEntityCharacterFactory(id=self.contact_id)
        return EveEntityCharacterFactory()


class ContactCorporationFactory(_ContactFactory):
    class Params:
        contact_id = None

    @factory.lazy_attribute
    def eve_entity(self):
        if self.contact_id:
            return EveEntityCorporationFactory(id=self.contact_id)
        return EveEntityCorporationFactory()


class _StandingRequestFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[StandingRequest]
):
    class Meta:
        model = StandingRequest

    class Params:
        pending = factory.Trait(
            is_effective=False,
            action_by=factory.SubFactory(UserMainApproverFactory),
            action_date=None,
        )
        actioned = factory.Trait(
            is_effective=False,
            action_by=factory.SubFactory(UserMainApproverFactory),
            action_date=factory.LazyFunction(now),
        )
        effective = factory.Trait(
            is_effective=True,
            action_by=factory.SubFactory(UserMainApproverFactory),
            action_date=factory.LazyFunction(now),
        )

    action_by = None
    action_date = None
    effective_date = None
    is_effective = False
    reason = AbstractStandingsRequest.Reason.NONE
    user = factory.SubFactory(UserMainRequestorFactory)


class StandingRequestCharacterFactory(_StandingRequestFactory):
    contact_id = factory.fuzzy.FuzzyInteger(90_800_001, 90_900_001)
    contact_type_id = factory.LazyFunction(ContactTypeId.character_id)


class StandingRequestCorporationFactory(_StandingRequestFactory):
    contact_id = factory.fuzzy.FuzzyInteger(98_800_001, 98_899_999)
    contact_type_id = ContactTypeId.CORPORATION


class _StandingRevocationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[StandingRevocation]
):
    class Meta:
        model = StandingRevocation

    class Params:
        standing_request = None  # when set will copy attributes
        pending = factory.Trait(
            is_effective=False,
            action_by=factory.SubFactory(UserMainApproverFactory),
        )
        effective = factory.Trait(
            is_effective=True,
            action_by=factory.SubFactory(UserMainApproverFactory),
            action_date=factory.LazyFunction(now),
        )

    reason = AbstractStandingsRequest.Reason.NONE

    @factory.lazy_attribute
    def action_by(self):
        if not self.standing_request:
            return None
        return self.standing_request.action_by

    @factory.lazy_attribute
    def effective_date(self):
        if not self.standing_request:
            return None
        return self.standing_request.effective_date

    @factory.lazy_attribute
    def is_effective(self):
        if not self.standing_request:
            return False
        return self.standing_request.is_effective

    @factory.lazy_attribute
    def action_date(self):
        if not self.standing_request:
            return None
        return self.standing_request.action_date

    @factory.lazy_attribute
    def user(self):
        if not self.standing_request:
            return UserMainRequestorFactory()
        return self.standing_request.user


class StandingRevocationCharacterFactory(_StandingRevocationFactory):
    contact_id = factory.fuzzy.FuzzyInteger(90_800_001, 90_899_999)
    contact_type_id = factory.LazyFunction(ContactTypeId.character_id)


class StandingRevocationCorporationFactory(_StandingRevocationFactory):
    contact_id = factory.fuzzy.FuzzyInteger(98_800_001, 98_899_999)
    contact_type_id = ContactTypeId.CORPORATION


class FrozenAuthUserFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[FrozenAuthUser]
):
    class Meta:
        model = FrozenAuthUser

    class Params:
        create_faction = False

    alliance = factory.LazyAttribute(
        lambda o: EveEntityAllianceFactory(id=o.user.profile.main_character.alliance_id)
    )
    character = factory.LazyAttribute(
        lambda o: EveEntityAllianceFactory(
            id=o.user.profile.main_character.character_id
        )
    )
    corporation = factory.LazyAttribute(
        lambda o: EveEntityAllianceFactory(
            id=o.user.profile.main_character.corporation_id
        )
    )
    faction = factory.LazyAttribute(
        lambda o: EveEntityFactionFactory() if o.create_faction else None
    )
    state = factory.SubFactory(StateFactory)
    user = factory.LazyAttribute(lambda o: UserMainRequestorFactory())


class FrozenAltCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[FrozenAlt]
):
    class Meta:
        model = FrozenAlt

    alliance = factory.SubFactory(EveEntityAllianceFactory)
    character = factory.SubFactory(EveEntityCharacterFactory)
    corporation = factory.SubFactory(EveEntityCorporationFactory)
    category = FrozenAlt.Category.CHARACTER
    faction = factory.SubFactory(EveEntityFactionFactory)
