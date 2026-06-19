from http import HTTPStatus
from unittest.mock import patch

from django.test import RequestFactory
from django.urls import reverse
from eveuniverse.tests.testdata.factories_2 import EveEntityAllianceFactory

from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    ContactAllianceFactory,
    ContactCharacterFactory,
    ContactCorporationFactory,
    ContactSetFactory,
    CorporationDetailsFactory,
    StandingRequestCorporationFactory,
    StateFactory,
)
from standingsrequests.tests.utils import json_response_to_dict_2
from standingsrequests.views import standings

TEST_SCOPE = "publicData"
STANDINGS_ALLIANCE_ID = 98_000_123
STANDINGS_API_CHARID = 90_000_123

APP_CONFIG_PATH = "standingsrequests.core.app_config"


@patch(APP_CONFIG_PATH + ".SR_OPERATION_MODE", "alliance")
@patch(APP_CONFIG_PATH + ".STANDINGS_API_CHARID", STANDINGS_API_CHARID)
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


class TestCharacterStandingsData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cs = ContactSetFactory()
        alliance = EveAllianceInfoFactory(alliance_id=STANDINGS_ALLIANCE_ID)
        cls.state = StateFactory(member_alliances=[alliance])

        cls.main_1 = EveCharacterFactory(
            corporation=EveCorporationInfoFactory(alliance=alliance)
        )
        cls.contact_1 = ContactCharacterFactory(
            contact_set=cs, contact_id=cls.main_1.character_id, standing=10.0
        )
        CharacterAffiliationFactory(is_eve_character=True, eve_character=cls.main_1)
        user_1 = UserMainFactory(
            main_character__character=cls.main_1, main_character__scopes=[TEST_SCOPE]
        )

        cls.alt = EveCharacterFactory()
        cls.contact_2 = ContactCharacterFactory(
            contact_set=cs, contact_id=cls.alt.character_id, standing=5.0
        )
        CharacterAffiliationFactory(is_eve_character=True, eve_character=cls.alt)
        add_character_to_user(user_1, cls.alt, scopes=[TEST_SCOPE])

        cls.contact_3 = ContactCharacterFactory(contact_set=cs, standing=-5.0)
        cls.ca_3 = CharacterAffiliationFactory(character__id=cls.contact_3.contact_id)

        ContactCorporationFactory(contact_set=cs)  # should not appear in response

    def test_should_return_contacts_and_identify_mains_when_user_has_permission(self):
        # given
        requestor = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
                "standingsrequests.view",
            ]
        )
        request = self.factory.get(
            reverse("standingsrequests:character_standings_data")
        )
        request.user = requestor
        my_view_without_cache = standings.character_standings_data.__wrapped__

        # when
        response = my_view_without_cache(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response, "character_id")
        expected = {
            self.contact_1.contact_id,
            self.contact_2.contact_id,
            self.contact_3.contact_id,
        }
        self.assertSetEqual(set(data.keys()), expected)

        data_1 = data[self.contact_1.contact_id]
        self.assertEqual(data_1["character_id"], self.contact_1.contact_id)
        self.assertEqual(data_1["character_name_html"]["sort"], self.contact_1.name)
        self.assertEqual(data_1["main_character_name"], self.main_1.character_name)
        self.assertEqual(data_1["corporation_name"], self.main_1.corporation_name)
        self.assertEqual(data_1["alliance_name"], self.main_1.alliance_name)
        self.assertEqual(data_1["standing"], 10.0)
        self.assertEqual(data_1["state"], self.state.name)

        data_2 = data[self.contact_2.contact_id]
        self.assertEqual(data_2["character_id"], self.contact_2.contact_id)
        self.assertEqual(data_2["character_name_html"]["sort"], self.contact_2.name)
        self.assertEqual(data_2["main_character_name"], self.main_1.character_name)
        self.assertEqual(data_2["corporation_name"], self.alt.corporation_name)
        self.assertEqual(data_2["alliance_name"], self.alt.alliance_name)
        self.assertEqual(data_2["standing"], 5.0)
        self.assertEqual(data_2["state"], self.state.name)

        data_3 = data[self.contact_3.contact_id]
        self.assertEqual(data_3["character_id"], self.contact_3.contact_id)
        self.assertEqual(
            data_3["character_name_html"]["sort"], self.contact_3.eve_entity.name
        )
        self.assertEqual(data_3["main_character_name"], "-")
        self.assertEqual(data_3["corporation_name"], self.ca_3.corporation.name)
        self.assertEqual(data_3["alliance_name"], self.ca_3.alliance.name)
        self.assertEqual(data_3["standing"], -5.0)
        self.assertEqual(data_3["state"], "-")

    def test_should_return_contacts_and_not_identify_mains_when_no_permission(self):
        # given
        requestor = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
            ]
        )
        request = self.factory.get(
            reverse("standingsrequests:character_standings_data")
        )
        request.user = requestor
        my_view_without_cache = standings.character_standings_data.__wrapped__

        # when
        response = my_view_without_cache(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response, "character_id")
        expected = {
            self.contact_1.contact_id,
            self.contact_2.contact_id,
            self.contact_3.contact_id,
        }
        self.assertSetEqual(set(data.keys()), expected)

        data_1 = data[self.contact_1.contact_id]
        self.assertEqual(data_1["character_id"], self.contact_1.contact_id)
        self.assertEqual(data_1["character_name_html"]["sort"], self.contact_1.name)
        self.assertEqual(data_1["main_character_name"], "")
        self.assertEqual(data_1["corporation_name"], self.main_1.corporation_name)
        self.assertEqual(data_1["alliance_name"], self.main_1.alliance_name)
        self.assertEqual(data_1["standing"], 10.0)
        self.assertEqual(data_1["state"], "")

        data_2 = data[self.contact_2.contact_id]
        self.assertEqual(data_2["character_id"], self.contact_2.contact_id)
        self.assertEqual(data_2["character_name_html"]["sort"], self.contact_2.name)
        self.assertEqual(data_2["main_character_name"], "")
        self.assertEqual(data_2["corporation_name"], self.alt.corporation_name)
        self.assertEqual(data_2["alliance_name"], self.alt.alliance_name)
        self.assertEqual(data_2["standing"], 5.0)
        self.assertEqual(data_2["state"], "")

        data_3 = data[self.contact_3.contact_id]
        self.assertEqual(data_3["character_id"], self.contact_3.contact_id)
        self.assertEqual(
            data_3["character_name_html"]["sort"], self.contact_3.eve_entity.name
        )
        self.assertEqual(data_3["main_character_name"], "")
        self.assertEqual(data_3["corporation_name"], self.ca_3.corporation.name)
        self.assertEqual(data_3["alliance_name"], self.ca_3.alliance.name)
        self.assertEqual(data_3["standing"], -5.0)
        self.assertEqual(data_3["state"], "")


class TestCorporationStandingsData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cs = ContactSetFactory()
        alliance = EveAllianceInfoFactory(alliance_id=STANDINGS_ALLIANCE_ID)
        cls.state = StateFactory(member_alliances=[alliance])

        cls.main_1 = EveCharacterFactory(
            corporation=EveCorporationInfoFactory(alliance=alliance)
        )
        cls.contact_1 = ContactCorporationFactory(
            contact_set=cs, contact_id=cls.main_1.corporation_id, standing=10.0
        )
        CorporationDetailsFactory(eve_corporation=cls.main_1.corporation)
        user_1 = UserMainFactory(
            main_character__character=cls.main_1, main_character__scopes=[TEST_SCOPE]
        )
        StandingRequestCorporationFactory(
            contact_id=cls.contact_1.contact_id, user=user_1
        )

        cls.alt = EveCharacterFactory()
        cls.contact_2 = ContactCorporationFactory(
            contact_set=cs, contact_id=cls.alt.corporation_id, standing=5.0
        )
        CorporationDetailsFactory(eve_corporation=cls.alt.corporation)
        add_character_to_user(user_1, cls.alt, scopes=[TEST_SCOPE])
        StandingRequestCorporationFactory(
            contact_id=cls.contact_2.contact_id, user=user_1
        )

        cls.contact_3 = ContactCorporationFactory(contact_set=cs, standing=-5.0)
        cls.ca_3 = CorporationDetailsFactory(corporation=cls.contact_3.eve_entity)

        ContactCharacterFactory(contact_set=cs)  # should not appear in response

    def test_should_return_contacts_and_identify_mains_when_user_has_permission(self):
        # given
        requestor = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
                "standingsrequests.view",
            ]
        )
        request = self.factory.get(
            reverse("standingsrequests:corporation_standings_data")
        )
        request.user = requestor
        my_view_without_cache = standings.corporation_standings_data.__wrapped__

        # when
        response = my_view_without_cache(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response, "corporation_id")
        expected = {
            self.contact_1.contact_id,
            self.contact_2.contact_id,
            self.contact_3.contact_id,
        }
        self.assertSetEqual(set(data.keys()), expected)

        data_1 = data[self.contact_1.contact_id]
        self.assertEqual(data_1["alliance_name"], self.main_1.alliance_name)
        self.assertEqual(data_1["corporation_id"], self.contact_1.contact_id)
        self.assertEqual(data_1["corporation_html"]["sort"], self.contact_1.name)
        self.assertEqual(data_1["main_character_name"], self.main_1.character_name)
        self.assertEqual(data_1["standing"], 10.0)
        self.assertEqual(data_1["state"], self.state.name)

        data_2 = data[self.contact_2.contact_id]
        self.assertEqual(data_2["alliance_name"], self.alt.alliance_name)
        self.assertEqual(data_2["corporation_id"], self.contact_2.contact_id)
        self.assertEqual(data_2["corporation_html"]["sort"], self.contact_2.name)
        self.assertEqual(data_2["main_character_name"], self.main_1.character_name)
        self.assertEqual(data_2["standing"], 5.0)
        self.assertEqual(data_2["state"], self.state.name)

        data_3 = data[self.contact_3.contact_id]
        self.assertEqual(data_3["corporation_id"], self.contact_3.contact_id)
        self.assertEqual(
            data_3["corporation_html"]["sort"], self.contact_3.eve_entity.name
        )
        self.assertEqual(data_3["main_character_name"], "-")
        self.assertEqual(data_3["alliance_name"], self.ca_3.alliance.name)
        self.assertEqual(data_3["standing"], -5.0)
        self.assertEqual(data_3["state"], "-")

    def test_should_return_contacts_and_not_identify_mains_when_no_permission(self):
        # given
        requestor = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
            ]
        )
        request = self.factory.get(
            reverse("standingsrequests:corporation_standings_data")
        )
        request.user = requestor
        my_view_without_cache = standings.corporation_standings_data.__wrapped__

        # when
        response = my_view_without_cache(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response, "corporation_id")
        expected = {
            self.contact_1.contact_id,
            self.contact_2.contact_id,
            self.contact_3.contact_id,
        }
        self.assertSetEqual(set(data.keys()), expected)

        data_1 = data[self.contact_1.contact_id]
        self.assertEqual(data_1["alliance_name"], self.main_1.alliance_name)
        self.assertEqual(data_1["corporation_id"], self.contact_1.contact_id)
        self.assertEqual(data_1["corporation_html"]["sort"], self.contact_1.name)
        self.assertEqual(data_1["main_character_name"], "")
        self.assertEqual(data_1["standing"], 10.0)
        self.assertEqual(data_1["state"], "")

        data_2 = data[self.contact_2.contact_id]
        self.assertEqual(data_2["alliance_name"], self.alt.alliance_name)
        self.assertEqual(data_2["corporation_id"], self.contact_2.contact_id)
        self.assertEqual(data_2["corporation_html"]["sort"], self.contact_2.name)
        self.assertEqual(data_2["main_character_name"], "")
        self.assertEqual(data_2["standing"], 5.0)
        self.assertEqual(data_2["state"], "")

        data_3 = data[self.contact_3.contact_id]
        self.assertEqual(data_3["corporation_id"], self.contact_3.contact_id)
        self.assertEqual(
            data_3["corporation_html"]["sort"], self.contact_3.eve_entity.name
        )
        self.assertEqual(data_3["main_character_name"], "")
        self.assertEqual(data_3["alliance_name"], self.ca_3.alliance.name)
        self.assertEqual(data_3["standing"], -5.0)
        self.assertEqual(data_3["state"], "")


class TestAllianceStandingsData(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_normal(self):
        # given
        cs = ContactSetFactory()
        contact = ContactAllianceFactory(contact_set=cs)
        requestor = UserMainFactory(
            permissions__=[
                "standingsrequests.request_standings",
            ]
        )
        request = self.factory.get(reverse("standingsrequests:alliance_standings_data"))
        request.user = requestor
        my_view_without_cache = standings.alliance_standings_data.__wrapped__

        # when
        response = my_view_without_cache(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = json_response_to_dict_2(response, "alliance_id")
        self.assertSetEqual(set(data.keys()), {contact.contact_id})

        data = data[contact.contact_id]
        self.assertEqual(data["alliance_id"], contact.contact_id)
        self.assertEqual(data["alliance_html"]["sort"], contact.name)
        self.assertEqual(data["standing"], contact.standing)
