import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.models import EveEntity
from eveuniverse.tests.testdata.factories_2 import EveEntityAllianceFactory

from allianceauth.eveonline.models import EveAllianceInfo, EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.core.contact_types import ContactTypeId
from standingsrequests.models import CharacterAffiliation, Contact, StandingRequest
from standingsrequests.tests.testdata.factories import ContactSetFactory
from standingsrequests.tests.testdata.my_test_data import (
    STANDINGS_ALLIANCE_ID,
    STANDINGS_API_CHARID,
    create_contacts_set,
    create_eve_objects,
    load_corporation_details,
    load_eve_entities,
)
from standingsrequests.tests.utils import PartialDictEqualMixin, json_response_to_dict_2
from standingsrequests.views import standings
from standingsrequests.views.standings import _identify_main_for_character

TEST_SCOPE = "publicData"
MODULE_PATH = "standingsrequests.views.standings"


@patch("standingsrequests.core.app_config.SR_OPERATION_MODE", "alliance")
@patch("standingsrequests.core.app_config.STANDINGS_API_CHARID", STANDINGS_API_CHARID)
class TestStandingsView(NoSocketsTestCase):
    def test_should_open_page_when_user_is_requestor(self):
        # given
        cs = ContactSetFactory()
        EveCharacterFactory(
            character_id=STANDINGS_API_CHARID, alliance_id=STANDINGS_ALLIANCE_ID
        )
        owner_alliance = EveEntityAllianceFactory(id=STANDINGS_ALLIANCE_ID)
        user = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
            ]
        )
        self.client.force_login(user)

        # when
        response = self.client.get(reverse("standingsrequests:standings"))

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["lastUpdate"], cs.date)
        self.assertEqual(response.context["organization"], owner_alliance)
        self.assertFalse(response.context["show_mains"])

    def test_should_open_page_when_user_is_requestor_and_can_view_standings(self):
        # given
        cs = ContactSetFactory()
        EveCharacterFactory(
            character_id=STANDINGS_API_CHARID, alliance_id=STANDINGS_ALLIANCE_ID
        )
        owner_alliance = EveEntityAllianceFactory(id=STANDINGS_ALLIANCE_ID)
        user = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
                "standingsrequests.view",
            ]
        )
        self.client.force_login(user)

        # when
        response = self.client.get(reverse("standingsrequests:standings"))

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["lastUpdate"], cs.date)
        self.assertEqual(response.context["organization"], owner_alliance)
        self.assertTrue(response.context["show_mains"])


class TestCharacterStandingsData(PartialDictEqualMixin, NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        load_eve_entities()
        create_eve_objects()
        cls.contact_set = create_contacts_set()
        CharacterAffiliation.objects.update_eve_character_relations()

        member_state = AuthUtils.get_member_state()
        member_state.member_alliances.add(EveAllianceInfo.objects.get(alliance_id=3001))
        cls.user = AuthUtils.create_member("John Doe")
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "standingsrequests.request_standings", cls.user
        )
        EveCharacter.objects.get(character_id=1009).delete()
        cls.main_character_1 = EveCharacter.objects.get(character_id=1002)
        cls.user_1 = AuthUtils.create_member(cls.main_character_1.character_name)
        add_character_to_user(
            cls.user_1,
            cls.main_character_1,
            is_main=True,
            scopes=[TEST_SCOPE],
        )
        cls.alt_character_1 = EveCharacter.objects.get(character_id=1007)
        add_character_to_user(
            cls.user_1,
            cls.alt_character_1,
            scopes=[TEST_SCOPE],
        )

    def test_normal_with_full_permissions(self):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "standingsrequests.view", self.user
        )
        self.maxDiff = None
        request = self.factory.get(
            reverse("standingsrequests:character_standings_data")
        )
        request.user = self.user
        my_view_without_cache = standings.character_standings_data.__wrapped__
        # when
        response = my_view_without_cache(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response, "character_id")
        expected = {1001, 1002, 1003, 1004, 1005, 1006, 1008, 1009, 1010, 1110}
        self.assertSetEqual(set(data.keys()), expected)

        data_character_1002 = data[1002]
        expected = {
            "character_id": 1002,
            "corporation_name": "Wayne Technologies",
            "alliance_name": "Wayne Enterprises",
            "faction_name": "",
            "standing": 10.0,
            "labels_str": "blue, green",
            "main_character_name": "Peter Parker",
            "state": "Member",
        }
        self.assertPartialDictEqual(data_character_1002, expected)

        data_character_1009 = data[1009]
        expected = {
            "character_id": 1009,
            "corporation_name": "Lexcorp",
            "alliance_name": "",
            "faction_name": "",
            "standing": -10.0,
            "labels_str": "red",
            "main_character_name": "-",
            "state": "-",
        }
        self.assertPartialDictEqual(data_character_1009, expected)

    def test_normal_with_basic_permission(self):
        # given
        self.maxDiff = None
        request = self.factory.get(
            reverse("standingsrequests:character_standings_data")
        )
        request.user = self.user
        my_view_without_cache = standings.character_standings_data.__wrapped__
        # when
        response = my_view_without_cache(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response, "character_id")
        expected = {1001, 1002, 1003, 1004, 1005, 1006, 1008, 1009, 1010, 1110}
        self.assertSetEqual(set(data.keys()), expected)

        data_character_1002 = data[1002]
        expected = {
            "character_id": 1002,
            "corporation_name": "Wayne Technologies",
            "alliance_name": "Wayne Enterprises",
            "faction_name": "",
            "standing": 10.0,
            "labels_str": "blue, green",
            "main_character_name": "",
            "state": "",
        }
        self.assertPartialDictEqual(data_character_1002, expected)

    def test_identify_main_works_without_main(self):
        # given
        character = EveCharacter.objects.get(character_id=1004)
        add_character_to_user(
            self.user,
            character,
            scopes=[TEST_SCOPE],
        )
        character_entity = EveEntity.objects.get(id=1004)
        contact = Contact.objects.create(
            contact_set=self.contact_set,
            eve_entity=character_entity,
            standing=10.0,
        )
        # checks that there's no main defined
        self.assertIsNone(self.user.profile.main_character)
        # when
        state, main_character_name, main_character_html = _identify_main_for_character(
            contact
        )
        # then
        self.assertEqual(main_character_name, "No main associated")
        self.assertEqual(main_character_html, "")
        self.assertEqual(
            state, "Member"
        )  # AuthUtils.create_member gives them Member by default


class TestCorporationStandingsData(PartialDictEqualMixin, NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.contact_set = create_contacts_set()
        load_eve_entities()
        create_eve_objects()
        load_corporation_details()
        member_state = AuthUtils.get_member_state()
        member_state.member_alliances.add(EveAllianceInfo.objects.get(alliance_id=3001))
        cls.user_1 = AuthUtils.create_member("John Doe")
        cls.user_1 = AuthUtils.add_permission_to_user_by_name(
            "standingsrequests.request_standings", cls.user_1
        )
        EveCharacter.objects.get(character_id=1009).delete()
        cls.main_character_1 = EveCharacter.objects.get(character_id=1002)
        cls.user_2 = AuthUtils.create_member(cls.main_character_1.character_name)
        add_character_to_user(
            cls.user_2,
            cls.main_character_1,
            is_main=True,
            scopes=[TEST_SCOPE],
        )
        cls.alt_character_1 = EveCharacter.objects.get(character_id=1007)
        add_character_to_user(
            cls.user_2,
            cls.alt_character_1,
            scopes=[TEST_SCOPE],
        )
        StandingRequest.objects.create(
            user=cls.user_2,
            contact_id=2102,
            contact_type_id=ContactTypeId.CORPORATION,
            action_by=cls.user_1,
            action_date=now() - dt.timedelta(days=1, hours=1),
            is_effective=True,
            effective_date=now() - dt.timedelta(days=1),
        )

    def test_with_full_permissions(self):
        # given
        self.user_1 = AuthUtils.add_permission_to_user_by_name(
            "standingsrequests.view", self.user_1
        )
        self.maxDiff = None
        request = self.factory.get(
            reverse("standingsrequests:corporation_standings_data")
        )
        request.user = self.user_1
        my_view_without_cache = standings.corporation_standings_data.__wrapped__
        # when
        response = my_view_without_cache(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response, "corporation_id")
        self.assertSetEqual(set(data.keys()), {2001, 2003, 2102})
        obj = data[2001]
        expected = {
            "corporation_id": 2001,
            "alliance_name": "Wayne Enterprises",
            "faction_name": "",
            "standing": 10.0,
            "state": "-",
            "main_character_name": "-",
        }
        self.assertPartialDictEqual(obj, expected)
        obj = data[2102]
        self.assertPartialDictEqual(
            obj,
            {
                "corporation_id": 2102,
                "alliance_name": "",
                "faction_name": "",
                "standing": -10.0,
                "state": "Member",
                "main_character_name": "Peter Parker",
            },
        )

    def test_with_basic_permissions(self):
        # given
        self.maxDiff = None
        request = self.factory.get(
            reverse("standingsrequests:corporation_standings_data")
        )
        request.user = self.user_1
        my_view_without_cache = standings.corporation_standings_data.__wrapped__
        # when
        response = my_view_without_cache(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response, "corporation_id")
        obj = data[2102]
        self.assertPartialDictEqual(
            obj,
            {
                "corporation_id": 2102,
                "alliance_name": "",
                "faction_name": "",
                "standing": -10.0,
                "state": "",
                "main_character_name": "",
            },
        )


class TestAllianceStandingsData(PartialDictEqualMixin, NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.contact_set = create_contacts_set()
        load_eve_entities()
        create_eve_objects()
        load_corporation_details()
        member_state = AuthUtils.get_member_state()
        member_state.member_alliances.add(EveAllianceInfo.objects.get(alliance_id=3001))
        cls.user = AuthUtils.create_member("John Doe")
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "standingsrequests.request_standings", cls.user
        )
        EveCharacter.objects.get(character_id=1009).delete()
        cls.main_character_1 = EveCharacter.objects.get(character_id=1002)
        cls.user_1 = AuthUtils.create_member(cls.main_character_1.character_name)
        add_character_to_user(
            cls.user_1,
            cls.main_character_1,
            is_main=True,
            scopes=[TEST_SCOPE],
        )
        cls.alt_character_1 = EveCharacter.objects.get(character_id=1007)
        add_character_to_user(
            cls.user_1,
            cls.alt_character_1,
            scopes=[TEST_SCOPE],
        )

    def test_normal(self):
        # given
        self.maxDiff = None
        request = self.factory.get(reverse("standingsrequests:alliance_standings_data"))
        request.user = self.user
        my_view_without_cache = standings.alliance_standings_data.__wrapped__
        # when
        response = my_view_without_cache(request)
        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_dict_2(response, "alliance_id")
        self.assertSetEqual(set(data.keys()), {3010})
        obj = data[3010]
        self.assertPartialDictEqual(obj, {"alliance_id": 3010, "standing": -10.0})
