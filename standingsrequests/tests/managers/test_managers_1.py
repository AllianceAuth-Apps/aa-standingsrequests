from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
)

from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.constants import CreateCharacterRequestResult
from standingsrequests.models import (
    AbstractStandingsRequest,
    Contact,
    ContactLabel,
    ContactSet,
    RequestLogEntry,
    StandingRequest,
    StandingRevocation,
)
from standingsrequests.tests.factories import (
    ContactCharacterFactory,
    ContactCorporationFactory,
    StandingRequestCharacterFactory,
    StandingRequestCorporationFactory,
    StandingRevocationCharacterFactory,
    StandingRevocationCorporationFactory,
    UserMainApproverFactory,
    UserMainRequestorFactory,
    make_esi_url,
)
from standingsrequests.tests.utils import TestCaseWithClearCache, extract

APP_CONFIG_PATH = "standingsrequests.core.app_config"
MANAGERS_PATH = "standingsrequests.managers"
MODELS_PATH = "standingsrequests.models"
STANDINGS_API_CHARID = 90_000_123


class TestContactSetManager_CreateNewFromApi(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_from_api_in_alliance_mode(self):
        # given
        owner_character = EveCharacterFactory(corporation__create_alliance=True)
        UserMainFactory(
            main_character__character=owner_character,
            main_character__scopes=["esi-alliances.read_contacts.v1"],
        )
        label_id = 42
        label_name = "Alpha"
        pook.get(
            make_esi_url(f"alliances/{owner_character.alliance_id}/contacts/labels"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "label_id": label_id,
                    "label_name": label_name,
                }
            ],
        )

        character = EveEntityCharacterFactory()
        standing = -5
        pook.get(
            make_esi_url(f"alliances/{owner_character.alliance_id}/contacts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": character.id,
                    "contact_type": "character",
                    "label_ids": [label_id],
                    "standing": standing,
                }
            ],
        )

        # when
        with (
            patch(APP_CONFIG_PATH + ".SR_OPERATION_MODE", "alliance"),
            patch(
                APP_CONFIG_PATH + ".STANDINGS_API_CHARID", owner_character.character_id
            ),
        ):
            contact_set: ContactSet = ContactSet.objects.create_new_from_api()

        # then
        self.assertEqual(contact_set.labels.count(), 1)
        label: ContactLabel = contact_set.labels.first()
        self.assertEqual(label.name, label_name)
        self.assertEqual(label.label_id, label_id)

        self.assertEqual(contact_set.contacts.count(), 1)
        contact: Contact = contact_set.contacts.first()
        self.assertEqual(contact.eve_entity, character)
        self.assertEqual(contact.standing, standing)
        self.assertCountEqual(contact.labels.all(), [label])

    @pook.on
    def test_can_create_new_from_api_in_corporation_mode(self):
        # given
        owner_character = EveCharacterFactory()
        UserMainFactory(
            main_character__character=owner_character,
            main_character__scopes=["esi-corporations.read_contacts.v1"],
        )
        label_id = 42
        label_name = "Alpha"
        pook.get(
            make_esi_url(
                f"corporations/{owner_character.corporation_id}/contacts/labels"
            ),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "label_id": label_id,
                    "label_name": label_name,
                }
            ],
        )

        character = EveEntityCharacterFactory()
        standing = -5
        pook.get(
            make_esi_url(f"corporations/{owner_character.corporation_id}/contacts"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "contact_id": character.id,
                    "contact_type": "character",
                    "label_ids": [label_id],
                    "standing": standing,
                }
            ],
        )

        # when
        with (
            patch(APP_CONFIG_PATH + ".SR_OPERATION_MODE", "corporation"),
            patch(
                APP_CONFIG_PATH + ".STANDINGS_API_CHARID",
                owner_character.character_id,
            ),
        ):
            contact_set: ContactSet = ContactSet.objects.create_new_from_api()

        # then
        self.assertEqual(contact_set.labels.count(), 1)
        label: ContactLabel = contact_set.labels.first()
        self.assertEqual(label.name, label_name)
        self.assertEqual(label.label_id, label_id)

        self.assertEqual(contact_set.contacts.count(), 1)
        contact: Contact = contact_set.contacts.first()
        self.assertEqual(contact.eve_entity, character)
        self.assertEqual(contact.standing, standing)
        self.assertCountEqual(contact.labels.all(), [label])


class TestAbstractStandingsRequestManager_PendingRequests(NoSocketsTestCase):
    def test_should_return_zero_when_no_requests(self):
        self.assertEqual(StandingRequest.objects.pending_requests().count(), 0)

    def test_should_return_count_of_pending_requests(self):
        # given
        StandingRequestCharacterFactory()
        StandingRequestCharacterFactory(effective=True)
        StandingRequestCharacterFactory(pending=True)

        # when

        result = StandingRequest.objects.pending_requests()
        # then
        self.assertEqual(result.count(), 2)


@patch(MANAGERS_PATH + ".app_config.SR_OPERATION_MODE", "alliance")
@patch(APP_CONFIG_PATH + ".STANDINGS_API_CHARID", STANDINGS_API_CHARID)
@patch(MANAGERS_PATH + ".notify")
class TestAbstractStandingsRequest_ProcessRequests(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        owner_character = EveCharacterFactory(character_id=STANDINGS_API_CHARID)
        EveEntityAllianceFactory(id=owner_character.alliance_id)

    def test_when_pilot_standing_satisfied_in_game_mark_effective_and_inform_user(
        self, mock_notify
    ):
        # given
        contact = ContactCharacterFactory(standing=5)
        sr = StandingRequestCharacterFactory(
            contact_id=contact.contact_id, pending=True
        )

        # when
        with patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            StandingRequest.objects.process_requests()

        # then
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertIsNotNone(sr.effective_date)
        self.assertEqual(mock_notify.call_count, 1)
        _, kwargs = mock_notify.call_args
        self.assertEqual(kwargs["user"], sr.user)

    def test_when_pilot_standing_satisfied_in_game_mark_effective_and_not_inform_user(
        self, mock_notify
    ):
        # given
        contact = ContactCharacterFactory(standing=5)
        sr = StandingRequestCharacterFactory(
            contact_id=contact.contact_id, pending=True
        )

        # when
        with patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", False):
            StandingRequest.objects.process_requests()

        # then
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertIsNotNone(sr.effective_date)
        self.assertEqual(mock_notify.call_count, 0)

    def test_dont_inform_user_when_sr_was_effective_before(self, mock_notify):
        # given
        contact = ContactCharacterFactory(standing=5)
        StandingRequestCharacterFactory(contact_id=contact.contact_id, effective=True)

        # when
        with patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            StandingRequest.objects.process_requests()

        # then
        self.assertEqual(mock_notify.call_count, 0)

    def test_when_corporation_standing_satisfied_in_game_mark_effective(
        self, mock_notify
    ):
        contact = ContactCorporationFactory(standing=5)
        sr = StandingRequestCorporationFactory(
            contact_id=contact.contact_id, pending=True
        )

        # when
        with patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            StandingRequest.objects.process_requests()

        # then
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertIsNotNone(sr.effective_date)
        self.assertTrue(mock_notify.called)

    def test_notify_about_requests_that_are_reset_and_timed_out(self, mock_notify):
        # given
        contact = ContactCharacterFactory(standing=-5)
        StandingRequestCharacterFactory(
            contact_id=contact.contact_id,
            pending=True,
            action_date=now() - timedelta(hours=25),
        )

        # when
        with (
            patch(MODELS_PATH + ".SR_STANDING_TIMEOUT_HOURS", 24),
            patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True),
        ):
            StandingRequest.objects.process_requests()

        # then
        self.assertEqual(mock_notify.call_count, 2)

    def test_dont_notify_about_requests_that_are_reset_and_not_timed_out(
        self, mock_notify
    ):
        # given
        contact = ContactCharacterFactory(standing=-5)
        StandingRequestCharacterFactory(
            contact_id=contact.contact_id,
            pending=True,
        )

        # when
        with (
            patch(MODELS_PATH + ".SR_STANDING_TIMEOUT_HOURS", 24),
            patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True),
        ):
            StandingRequest.objects.process_requests()

        # then
        self.assertEqual(mock_notify.call_count, 0)

    def test_no_action_when_actioned_standing_but_not_in_game_yet(self, mock_notify):
        # given
        contact = EveEntityCharacterFactory()
        sr = StandingRequestCharacterFactory(
            contact_id=contact.id,
            pending=True,
        )

        # when
        with patch(MANAGERS_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            StandingRequest.objects.process_requests()

        # then
        sr.refresh_from_db()
        self.assertFalse(sr.is_effective)
        self.assertIsNone(sr.effective_date)
        self.assertEqual(mock_notify.call_count, 0)

    def test_raise_exception_when_called_from_abstract_class(self, mock_notify):
        with self.assertRaises(TypeError):
            AbstractStandingsRequest.objects.process_requests()


class TestAbstractStandingsRequest_PendingRequests(NoSocketsTestCase):
    def test_should_return_true_when_contact_has_pending_request(self):
        sr = StandingRequestCharacterFactory(pending=True)
        got = AbstractStandingsRequest.objects.has_pending_request(sr.contact_id)
        self.assertTrue(got)

    def test_should_return_false_when_contact_has_no_pending_request(self):
        sr = StandingRequestCharacterFactory(effective=True)
        got = AbstractStandingsRequest.objects.has_pending_request(sr.contact_id)
        self.assertFalse(got)


class TestAbstractStandingsRequest_AnnotateIsPending(NoSocketsTestCase):
    def test_pending_request_annotation(self):
        # given
        r1 = StandingRequestCharacterFactory(pending=True)
        r2 = StandingRequestCharacterFactory(effective=True)

        # when
        requests = StandingRequest.objects.all().annotate_is_pending()

        # then
        self.assertTrue(requests.get(pk=r1.pk).is_pending_annotated)
        self.assertFalse(requests.get(pk=r2.pk).is_pending_annotated)


class TestStandingsRequest_ValidateRequests(NoSocketsTestCase):
    def test_should_do_nothing_when_user_has_permission(self):
        # given
        user = UserMainRequestorFactory()
        StandingRequestCharacterFactory(user=user)

        # when
        got = StandingRequest.objects.validate_requests()

        # then
        self.assertEqual(got, 0)
        self.assertFalse(StandingRevocation.objects.exists())

    def test_should_create_revocation_when_no_permission(
        self,
    ):
        # given
        user = UserFactory()
        rq = StandingRequestCharacterFactory(user=user)

        # when
        StandingRequest.objects.validate_requests()

        # then
        my_revocation = StandingRevocation.objects.get(contact_id=rq.contact_id)
        self.assertEqual(
            my_revocation.reason, StandingRevocation.Reason.LOST_PERMISSION
        )

    @patch(MANAGERS_PATH + ".user_can_request_corporation_standing")
    def test_should_create_revocation_when_corporation_is_missing_token(
        self, mock_can_request_corporation_standing
    ):
        # given
        mock_can_request_corporation_standing.return_value = False
        user = UserMainRequestorFactory()
        rq = StandingRequestCorporationFactory(user=user)

        # when
        StandingRequest.objects.validate_requests()

        # then
        my_revocation = StandingRevocation.objects.get(contact_id=rq.contact_id)
        self.assertEqual(
            my_revocation.reason, StandingRevocation.Reason.MISSING_CORP_TOKEN
        )

    @patch(MANAGERS_PATH + ".user_can_request_corporation_standing")
    def test_keep_corp_standing_request_when_all_token_recorded(
        self, mock_can_request_corporation_standing
    ):
        # given
        mock_can_request_corporation_standing.return_value = True
        user = UserMainRequestorFactory()
        StandingRequestCorporationFactory(user=user)

        # when
        StandingRequest.objects.validate_requests()

        # then
        self.assertFalse(StandingRevocation.objects.exists())


@patch(MANAGERS_PATH + ".create_eve_entities", MagicMock())
@patch(APP_CONFIG_PATH + ".SR_REQUIRED_SCOPES", {"Guest": ["required_scope"]})
class TestStandingsRequestManager_CreateCharacterRequest(NoSocketsTestCase):
    def test_should_create_pending_request_when_contact_has_no_standing(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["required_scope"])

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.NO_ERROR)
        self.assertEqual(StandingRequest.objects.count(), 1)
        sr: StandingRequest = StandingRequest.objects.first()
        self.assertEqual(sr.contact_id, character.character_id)
        self.assertTrue(sr.is_pending)

    def test_should_create_auto_confirm_request_when_contact_has_standing(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        ContactCharacterFactory(contact_id=character.character_id, standing=5)
        add_character_to_user(user, character, scopes=["required_scope"])

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.NO_ERROR)
        self.assertEqual(StandingRequest.objects.count(), 1)
        sr: StandingRequest = StandingRequest.objects.first()
        self.assertEqual(sr.contact_id, character.character_id)
        self.assertTrue(sr.is_effective)
        self.assertEqual(
            RequestLogEntry.objects.filter(
                action_by__isnull=True,
                requested_for__character_id=character.character_id,
                requested_by__user=user,
                request_type=RequestLogEntry.RequestType.REQUEST,
                action=RequestLogEntry.Action.CONFIRMED,
                reason=StandingRequest.Reason.STANDING_IN_GAME,
            ).count(),
            1,
        )

    def test_should_not_create_request_when_character_already_has_pending_request(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["required_scope"])
        sr = StandingRequestCharacterFactory(contact_id=character.character_id)

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.CHARACTER_HAS_REQUEST)
        self.assertSetEqual(extract(StandingRequest.objects, "pk"), {sr.pk})

    def test_should_not_create_request_when_character_already_has_pending_revocation(
        self,
    ):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["required_scope"])
        StandingRevocationCharacterFactory(contact_id=character.character_id)

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.CHARACTER_HAS_REQUEST)
        self.assertEqual(StandingRequest.objects.count(), 0)

    def test_should_not_create_new_request_when_character_is_missing_scopes(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["invalid_scope"])

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(
            result, CreateCharacterRequestResult.CHARACTER_IS_MISSING_SCOPES
        )
        self.assertEqual(StandingRequest.objects.count(), 0)

    def test_should_not_create_new_request_when_another_user_owns_character(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(
            UserMainRequestorFactory(), character, scopes=["required_scope"]
        )

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.USER_IS_NOT_OWNER)
        self.assertEqual(StandingRequest.objects.count(), 0)

    def test_should_not_create_new_request_when_character_is_orphan(self):
        # given
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()

        # when
        result: CreateCharacterRequestResult = (
            StandingRequest.objects.create_character_request(
                user=user, character=character
            )
        )

        # then
        self.assertEqual(result, CreateCharacterRequestResult.USER_IS_NOT_OWNER)
        self.assertEqual(StandingRequest.objects.count(), 0)


class TestStandingsRequestManager_CreateCorporationRequest(NoSocketsTestCase):
    def test_should_create_request(self):
        # given
        user = UserMainRequestorFactory()
        corporation = EveCorporationInfoFactory()

        # when
        with patch(MANAGERS_PATH + ".user_can_request_corporation_standing") as m:
            m.return_value = True
            got = StandingRequest.objects.create_corporation_request(
                user=user, corporation_id=corporation.corporation_id
            )

        # then
        self.assertTrue(got)
        self.assertEqual(StandingRequest.objects.count(), 1)
        sr: StandingRequest = StandingRequest.objects.first()
        self.assertEqual(sr.contact_id, corporation.corporation_id)
        self.assertTrue(sr.is_pending)

    def test_should_not_create_request_when_user_is_missing_tokens(self):
        # given
        user = UserMainRequestorFactory()
        corporation = EveCorporationInfoFactory()

        # when
        with patch(MANAGERS_PATH + ".user_can_request_corporation_standing") as m:
            m.return_value = False
            got = StandingRequest.objects.create_corporation_request(
                user=user, corporation_id=corporation.corporation_id
            )

        # then
        self.assertFalse(got)
        self.assertEqual(StandingRequest.objects.count(), 0)

    def test_should_not_create_request_when_contact_already_has_pending_request(self):
        # given
        user = UserMainRequestorFactory()
        corporation = EveCorporationInfoFactory()
        sr = StandingRequestCorporationFactory(contact_id=corporation.corporation_id)

        # when
        with patch(MANAGERS_PATH + ".user_can_request_corporation_standing") as m:
            m.return_value = True
            got = StandingRequest.objects.create_corporation_request(
                user=user, corporation_id=corporation.corporation_id
            )

        # then
        self.assertFalse(got)
        self.assertSetEqual(extract(StandingRequest.objects, "pk"), {sr.pk})

    def test_should_not_create_request_when_contact_already_has_revocation(self):
        # given
        user = UserMainRequestorFactory()
        corporation = EveCorporationInfoFactory()
        StandingRevocationCorporationFactory(contact_id=corporation.corporation_id)

        # when
        with patch(MANAGERS_PATH + ".user_can_request_corporation_standing") as m:
            m.return_value = True
            got = StandingRequest.objects.create_corporation_request(
                user=user, corporation_id=corporation.corporation_id
            )

        # then
        self.assertFalse(got)
        self.assertEqual(StandingRequest.objects.count(), 0)


class TestStandingsRequestManager_GetOrCreate2(NoSocketsTestCase):
    def test_should_create_new_request_when_none_exists(self):
        # when
        user = UserMainRequestorFactory()
        contact = ContactCharacterFactory()

        # when
        obj: StandingRequest
        obj = StandingRequest.objects.get_or_create_2(
            user, contact.contact_id, StandingRequest.ContactType.CHARACTER
        )

        # then
        self.assertEqual(obj.contact_id, contact.contact_id)

    def test_should_return_existing_request(self):
        # when
        user = UserMainRequestorFactory()
        contact = ContactCharacterFactory()
        obj_1 = StandingRequestCharacterFactory(contact_id=contact.contact_id)

        # when
        obj_2: StandingRequest
        obj_2 = StandingRequest.objects.get_or_create_2(
            user, contact.contact_id, StandingRequest.ContactType.CHARACTER
        )

        # then
        self.assertEqual(StandingRequest.objects.count(), 1)
        self.assertEqual(obj_2, obj_1)


class TestStandingsRevocationManager_AddRevocation(NoSocketsTestCase):
    def test_can_create_minimal(self):
        # given
        contact_id = 90_000_123

        # when
        got: StandingRevocation = StandingRevocation.objects.add_revocation(
            contact_id=contact_id,
            contact_type=StandingRevocation.ContactType.CHARACTER,
        )

        # then
        self.assertEqual(got.contact_id, contact_id)
        self.assertIsNone(got.user)
        self.assertEqual(got.reason, StandingRevocation.Reason.NONE)

    def test_can_create_full(self):
        # given
        contact_id = 90_000_123
        user = UserMainApproverFactory()
        reason = StandingRevocation.Reason.REVOKED_IN_GAME

        # when
        got: StandingRevocation = StandingRevocation.objects.add_revocation(
            contact_id=contact_id,
            contact_type=StandingRevocation.ContactType.CHARACTER,
            user=user,
            reason=reason,
        )

        # then
        self.assertEqual(got.contact_id, contact_id)
        self.assertEqual(got.user, user)
        self.assertEqual(got.reason, reason)

    def test_should_return_none_when_revocation_already(self):
        # given
        contact_id = 90_000_123
        StandingRevocationCharacterFactory(contact_id=contact_id)

        # when
        got = StandingRevocation.objects.add_revocation(
            contact_id, StandingRevocation.ContactType.CHARACTER
        )

        # then
        self.assertIsNone(got)
