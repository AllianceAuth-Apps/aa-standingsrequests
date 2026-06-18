from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
)

from allianceauth.eveonline.models import EveCharacter
from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.models import StandingRequest
from standingsrequests.tests.testdata.factories import (
    StandingRequestCharacterFactory,
    StandingRequestCorporationFactory,
    StandingRevocationCharacterFactory,
    StandingRevocationCorporationFactory,
    UserMainApproverFactory,
    UserMainRequestorFactory,
)
from standingsrequests.views import create_requests

CORE_PATH = "standingsrequests.core"
MODELS_PATH = "standingsrequests.models"
MANAGERS_PATH = "standingsrequests.managers"
VIEWS_PATH = "standingsrequests.views.create_requests"

STANDINGS_ALLIANCE_ID = 98_000_123
STANDINGS_API_CHARID = 90_000_123
STANDINGS_CORPORATION_ID = 97_000_123


@patch(CORE_PATH + ".app_config.STANDINGS_API_CHARID", STANDINGS_API_CHARID)
@patch(VIEWS_PATH + ".update_all")
@patch(VIEWS_PATH + ".messages")
class TestViewAuthPage(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def _make_request(self, user: User, character: EveCharacter):
        token = user.token_set.get(character_id=character.character_id)
        request = self.factory.get(reverse("standingsrequests:view_auth_page"))
        request.user = user
        request.token = token
        middleware = SessionMiddleware(MagicMock())
        middleware.process_request(request)
        orig_view = create_requests.view_auth_page.__wrapped__.__wrapped__.__wrapped__
        return orig_view(request, token)

    def test_should_return_success_when_configured_owner_character_is_provided(
        self, mock_messages, mock_update_all
    ):
        # given
        owner_character = EveCharacterFactory(
            character_id=STANDINGS_API_CHARID,
            alliance_id=STANDINGS_ALLIANCE_ID,
            corporation_id=STANDINGS_CORPORATION_ID,
        )
        EveEntityAllianceFactory(id=owner_character.alliance_id)
        EveEntityCorporationFactory(id=owner_character.corporation_id)

        user = UserMainApproverFactory(main_character__character=owner_character)
        EveEntityCharacterFactory(id=owner_character.character_id)

        cases = ["corporation", "alliance"]
        for operation_mode in cases:
            with self.subTest(operation_mode=operation_mode):
                # when
                with patch(CORE_PATH + ".app_config.SR_OPERATION_MODE", operation_mode):
                    response = self._make_request(user, owner_character)

                # then
                self.assertEqual(response.status_code, HTTPStatus.FOUND)
                self.assertEqual(response.url, reverse("standingsrequests:index"))
                self.assertTrue(mock_messages.success.called)
                self.assertFalse(mock_messages.error.called)
                self.assertTrue(mock_update_all.delay.called)

    def test_should_return_error_when_not_configured_owner_character_is_not_provided(
        self, mock_messages, mock_update_all
    ):
        # given
        owner_character = EveCharacterFactory(
            character_id=STANDINGS_API_CHARID,
            alliance_id=STANDINGS_ALLIANCE_ID,
            corporation_id=STANDINGS_CORPORATION_ID,
        )
        EveEntityAllianceFactory(id=owner_character.alliance_id)
        EveEntityCorporationFactory(id=owner_character.corporation_id)

        main = EveCharacterFactory()
        user = UserMainApproverFactory(main_character__character=main)
        EveEntityCharacterFactory(id=main.character_id)

        cases = ["corporation", "alliance"]
        for operation_mode in cases:
            with self.subTest(operation_mode=operation_mode):
                # when
                with patch(CORE_PATH + ".app_config.SR_OPERATION_MODE", operation_mode):
                    response = self._make_request(user, user.profile.main_character)

                # then
                self.assertEqual(response.status_code, HTTPStatus.FOUND)
                self.assertEqual(response.url, reverse("standingsrequests:index"))
                self.assertFalse(mock_messages.success.called)
                self.assertTrue(mock_messages.error.called)
                self.assertFalse(mock_update_all.delay.called)


# @patch(CORE_PATH + ".app_config.STANDINGS_API_CHARID", STANDINGS_API_CHARID)
# @patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True)
class TestIndexView(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_redirect_to_create_requests_page_for_requestor_1(self):
        # given
        request = self.factory.get(reverse("standingsrequests:index"))
        request.user = UserMainRequestorFactory()

        # when
        response = create_requests.index_view(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))

    def test_should_redirect_to_create_requests_page_for_requestor_2(self):
        # given
        user = UserMainRequestorFactory()
        StandingRequestCharacterFactory(user=user)
        request = self.factory.get(reverse("standingsrequests:index"))
        request.user = user

        # when
        response = create_requests.index_view(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))

    def test_should_redirect_to_create_requests_page_for_manger(self):
        # given
        request = self.factory.get(reverse("standingsrequests:index"))
        request.user = UserMainApproverFactory()

        # when
        response = create_requests.index_view(request)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))


#     def test_should_redirect_to_manage_requests_page_1(self, mock_esi):
#         # given
#         request = self.factory.get(reverse("standingsrequests:index"))
#         request.user = self.user_manager
#         StandingRequest.objects.get_or_create_2(
#             self.user_requestor,
#             self.alt_character_1.character_id,
#             StandingRequest.ContactType.CHARACTER,
#         )
#         # when
#         response = create_requests.index_view(request)
#         # then
#         self.assertEqual(response.status_code, HTTPStatus.FOUND)
#         self.assertEqual(response.url, reverse("standingsrequests:manage"))

#     def test_should_redirect_to_manage_requests_page_2(self, mock_esi):
#         # given
#         request = self.factory.get(reverse("standingsrequests:index"))
#         request.user = self.user_manager
#         self._create_standing_for_alt(self.alt_character_1)
#         StandingRevocation.objects.add_revocation(
#             self.alt_character_1.character_id,
#             StandingRevocation.ContactType.CHARACTER,
#             user=self.user_requestor,
#         )
#         # when
#         response = create_requests.index_view(request)
#         # then
#         self.assertEqual(response.status_code, HTTPStatus.FOUND)
#         self.assertEqual(response.url, reverse("standingsrequests:manage"))

#     def test_user_can_open_create_requests_page(self, mock_esi):
#         request = self.factory.get(reverse("standingsrequests:create_requests"))
#         request.user = self.user_requestor
#         response = create_requests.create_requests(request)
#         self.assertEqual(response.status_code, HTTPStatus.OK)

#     def test_user_can_open_pilots_standing(self, mock_esi):
#         request = self.factory.get(reverse("standingsrequests:view_pilots"))
#         request.user = self.user_manager
#         response = create_requests.view_pilots_standings(request)
#         self.assertEqual(response.status_code, HTTPStatus.OK)

#     def test_user_can_open_groups_standing(self, mock_esi):
#         request = self.factory.get(reverse("standingsrequests:view_groups"))
#         request.user = self.user_manager
#         response = create_requests.view_groups_standings(request)
#         self.assertEqual(response.status_code, HTTPStatus.OK)

#     def test_user_can_open_manage_requests(self, mock_esi):
#         request = self.factory.get(reverse("standingsrequests:manage"))
#         request.user = self.user_manager
#         response = create_requests.manage_standings(request)
#         self.assertEqual(response.status_code, HTTPStatus.OK)

#     def test_user_can_open_accepted_requests(self, mock_esi):
#         request = self.factory.get(reverse("standingsrequests:effective_requests"))
#         request.user = self.user_manager
#         response = create_requests.effective_requests(request)
#         self.assertEqual(response.status_code, HTTPStatus.OK)


@patch(CORE_PATH + ".app_config.STANDINGS_API_CHARID", STANDINGS_API_CHARID)
@patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": ["required_scope"]})
@patch(MANAGERS_PATH + ".create_eve_entities", MagicMock())
@patch(VIEWS_PATH + ".update_associations_api.delay")
@patch(VIEWS_PATH + ".messages.error")
class TestRequestCharacterStanding(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        EveCharacterFactory(character_id=STANDINGS_API_CHARID)

    def test_should_create_new_pending_request(
        self, mock_message_error, mock_update_associations_api
    ):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["required_scope"])
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.request_character_standing(
            request, character.character_id
        )

        # then
        self.assertFalse(mock_message_error.called)
        self.assertTrue(mock_update_associations_api.called)

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))

        obj = StandingRequest.objects.get(contact_id=character.character_id)
        self.assertTrue(obj.is_pending)

    def test_should_not_create_request_when_character_already_has_pending_request(
        self, mock_message_error, mock_update_associations_api
    ):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["required_scope"])
        StandingRequestCharacterFactory(contact_id=character.character_id)
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.request_character_standing(
            request, character.character_id
        )

        # then
        self.assertTrue(mock_message_error.called)
        self.assertFalse(mock_update_associations_api.called)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(StandingRequest.objects.count(), 1)


@patch(VIEWS_PATH + ".messages")
class TestRemoveCharacterStanding(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_remove_request(self, mock_message):
        # given
        user = UserMainRequestorFactory()
        alt = EveCharacterFactory()
        add_character_to_user(user, alt)
        sr = StandingRequestCharacterFactory(user=user, contact_id=alt.character_id)
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.remove_character_standing(request, alt.character_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))
        self.assertFalse(mock_message.error.called)
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())

    def test_should_raise_error_when_request_not_found(self, mock_message):
        # given
        user = UserMainRequestorFactory()
        alt = EveCharacterFactory()
        add_character_to_user(user, alt)
        request = self.factory.get("/")
        request.user = user

        # when
        with self.assertRaises(Http404):
            create_requests.remove_character_standing(request, alt.character_id)

    def test_should_not_remove_request_and_show_warning_when_character_has_pending_revocation(
        self, mock_message
    ):
        # given
        user = UserMainRequestorFactory()
        alt = EveCharacterFactory()
        add_character_to_user(user, alt)
        EveEntityCharacterFactory(id=alt.character_id)
        sr = StandingRequestCharacterFactory(user=user, contact_id=alt.character_id)
        StandingRevocationCharacterFactory(user=user, contact_id=alt.character_id)
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.remove_character_standing(request, alt.character_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))
        self.assertTrue(mock_message.error.called)
        self.assertTrue(StandingRequest.objects.filter(pk=sr.pk).exists())

    # I believe we do not need this requirement
    # def test_should_create_revocation_if_character_has_satisfied_standing(self):
    #     # given
    #     alt_character = EveCharacterFactory(character_id=1110)
    #     add_character_to_user(self.user, alt_character, scopes=["publicData"])
    #     # when
    #     result = self._view_request_pilot_standing(alt_character.character_id)
    #     # then
    #     self.assertTrue(result)


@patch(VIEWS_PATH + ".update_associations_api.delay")
@patch(VIEWS_PATH + ".messages")
class TestRequestCorporationStanding(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        EveCharacterFactory(character_id=STANDINGS_API_CHARID)

    def test_should_create_new_pending_request(
        self, mock_messages, mock_update_associations_api
    ):
        # given
        user = UserMainRequestorFactory()
        corporation = EveEntityCorporationFactory()
        request = self.factory.get("/")
        request.user = user

        # when
        with patch(
            VIEWS_PATH + ".StandingRequest.objects.create_corporation_request"
        ) as mock_create_corporation_request:
            mock_create_corporation_request.return_value = True
            response = create_requests.request_corp_standing(request, corporation.id)

            # then
            self.assertEqual(response.status_code, HTTPStatus.FOUND)
            self.assertEqual(response.url, reverse("standingsrequests:create_requests"))

            self.assertFalse(mock_messages.error.called)
            self.assertTrue(mock_update_associations_api.called)
            self.assertTrue(mock_create_corporation_request.called)

    def test_should_show_warning_when_request_can_not_be_created(
        self, mock_messages, mock_update_associations_api
    ):
        # given
        user = UserMainRequestorFactory()
        corporation = EveEntityCorporationFactory()
        request = self.factory.get("/")
        request.user = user

        # when
        with patch(
            VIEWS_PATH + ".StandingRequest.objects.create_corporation_request"
        ) as mock_create_corporation_request:
            mock_create_corporation_request.return_value = False
            response = create_requests.request_corp_standing(request, corporation.id)

            # then
            self.assertEqual(response.status_code, HTTPStatus.FOUND)
            self.assertEqual(response.url, reverse("standingsrequests:create_requests"))

            self.assertTrue(mock_create_corporation_request.called)
            self.assertTrue(mock_messages.error.called)
            self.assertFalse(mock_update_associations_api.called)


@patch(VIEWS_PATH + ".messages")
class TestRemoveCorporationStanding_2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_remove_request(self, mock_messages):
        # given
        user = UserMainRequestorFactory()
        alt = EveEntityCorporationFactory()
        sr = StandingRequestCorporationFactory(user=user, contact_id=alt.id)
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.remove_corp_standing(request, alt.id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())

    def test_should_raise_error_when_request_is_not_found(self, mock_messages):
        # given
        user = UserMainRequestorFactory()
        alt = EveEntityCorporationFactory()
        request = self.factory.get("/")
        request.user = user

        # when
        with self.assertRaises(Http404):
            create_requests.remove_corp_standing(request, alt.id)

    def test_should_show_message_when_request_could_not_be_removed(self, mock_messages):
        # given
        user = UserMainRequestorFactory()
        alt = EveEntityCorporationFactory()
        sr = StandingRequestCorporationFactory(user=user, contact_id=alt.id)
        StandingRevocationCorporationFactory(user=user, contact_id=sr.contact_id)
        request = self.factory.get("/")
        request.user = user

        # when
        response = create_requests.remove_corp_standing(request, alt.id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("standingsrequests:create_requests"))
        self.assertTrue(StandingRequest.objects.filter(pk=sr.pk).exists())
        self.assertTrue(mock_messages.error.called)
