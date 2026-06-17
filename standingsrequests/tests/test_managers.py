from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
    EveEntityFactionFactory,
)

from app_utils.testdata_factories import (
    EveCharacterFactory,
    UserFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase

from standingsrequests.models import (
    AbstractStandingsRequest,
    CharacterAffiliation,
    Contact,
    ContactLabel,
    ContactSet,
    CorporationDetails,
    FrozenAlt,
    FrozenAuthUser,
    RequestLogEntry,
    StandingRequest,
    StandingRevocation,
)
from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    ContactCharacterFactory,
    ContactCorporationFactory,
    ContactSetFactory,
    CorporationDetailsFactory,
    FrozenAltCharacterFactory,
    StandingRequestCharacterFactory,
    StandingRequestCorporationFactory,
    StandingRevocationCharacterFactory,
    StateFactory,
    UserMainApproverFactory,
    UserMainRequestorFactory,
    make_esi_url,
)
from standingsrequests.tests.utils_2 import TestCaseWithClearCache

CORE_PATH = "standingsrequests.core"
MANAGERS_PATH = "standingsrequests.managers"
MODELS_PATH = "standingsrequests.models"
STANDINGS_API_CHARID = 1001


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
            patch(CORE_PATH + ".app_config.SR_OPERATION_MODE", "alliance"),
            patch(
                CORE_PATH + ".app_config.STANDINGS_API_CHARID",
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
            patch(CORE_PATH + ".app_config.SR_OPERATION_MODE", "corporation"),
            patch(
                CORE_PATH + ".app_config.STANDINGS_API_CHARID",
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
@patch(CORE_PATH + ".app_config.STANDINGS_API_CHARID", STANDINGS_API_CHARID)
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

    @patch(MODELS_PATH + ".StandingRequest.can_request_corporation_standing")
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

    @patch(MODELS_PATH + ".StandingRequest.can_request_corporation_standing")
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


class TestCharacterAffiliationsManager_UpdateFromESI(TestCaseWithClearCache):
    @pook.on
    def test_should_create_new_for_contacts_minimal(self):
        # given
        cs = ContactSetFactory()
        contact = ContactCharacterFactory(contact_set=cs)
        corporation = EveEntityCorporationFactory()
        pook.post(
            make_esi_url("characters/affiliation"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "character_id": contact.eve_entity.id,
                    "corporation_id": corporation.id,
                }
            ],
        )

        # when
        CharacterAffiliation.objects.update_from_esi()

        # then
        self.assertEqual(CharacterAffiliation.objects.count(), 1)
        obj: CharacterAffiliation = CharacterAffiliation.objects.first()
        self.assertEqual(obj.character, contact.eve_entity)
        self.assertEqual(obj.corporation, corporation)
        self.assertIsNone(obj.alliance)
        self.assertIsNone(obj.faction)
        self.assertIsNone(obj.eve_character)

    @pook.on
    def test_should_create_new_for_contacts_and_requests_and_revocations(self):
        # given
        cs = ContactSetFactory()
        contact = ContactCharacterFactory(contact_set=cs)
        corporation_ct = EveEntityCorporationFactory()
        alliance_ct = EveEntityAllianceFactory()
        faction_ct = EveEntityFactionFactory()

        rq = StandingRequestCharacterFactory()
        EveEntityCharacterFactory(id=rq.contact_id)
        corporation_rq = EveEntityCorporationFactory()
        alliance_rq = EveEntityAllianceFactory()
        faction_rq = EveEntityFactionFactory()

        rv = StandingRevocationCharacterFactory()
        EveEntityCharacterFactory(id=rv.contact_id)
        corporation_rv = EveEntityCorporationFactory()
        alliance_rv = EveEntityAllianceFactory()
        faction_rv = EveEntityFactionFactory()

        pook.post(
            make_esi_url("characters/affiliation"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "alliance_id": alliance_ct.id,
                    "character_id": contact.eve_entity.id,
                    "corporation_id": corporation_ct.id,
                    "faction_id": faction_ct.id,
                },
                {
                    "alliance_id": alliance_rq.id,
                    "character_id": rq.contact_id,
                    "corporation_id": corporation_rq.id,
                    "faction_id": faction_rq.id,
                },
                {
                    "alliance_id": alliance_rv.id,
                    "character_id": rv.contact_id,
                    "corporation_id": corporation_rv.id,
                    "faction_id": faction_rv.id,
                },
            ],
        )

        # when
        CharacterAffiliation.objects.update_from_esi()

        # then
        self.assertEqual(CharacterAffiliation.objects.count(), 3)
        obj: CharacterAffiliation = CharacterAffiliation.objects.get(
            character__id=contact.eve_entity.id
        )
        self.assertEqual(obj.corporation, corporation_ct)
        self.assertEqual(obj.alliance, alliance_ct)
        self.assertEqual(obj.faction, faction_ct)

        obj: CharacterAffiliation = CharacterAffiliation.objects.get(
            character__id=rq.contact_id
        )
        self.assertEqual(obj.corporation, corporation_rq)
        self.assertEqual(obj.alliance, alliance_rq)
        self.assertEqual(obj.faction, faction_rq)

        obj: CharacterAffiliation = CharacterAffiliation.objects.get(
            character__id=rv.contact_id
        )
        self.assertEqual(obj.corporation, corporation_rv)
        self.assertEqual(obj.alliance, alliance_rv)
        self.assertEqual(obj.faction, faction_rv)

    @pook.on
    def test_should_update_existing_for_contacts_minimal(self):
        # given
        cs = ContactSetFactory()
        contact = ContactCharacterFactory(contact_set=cs)
        ca = CharacterAffiliationFactory(character=contact.eve_entity)
        corporation = EveEntityCorporationFactory()
        pook.post(
            make_esi_url("characters/affiliation"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "character_id": contact.eve_entity.id,
                    "corporation_id": corporation.id,
                }
            ],
        )

        # when
        CharacterAffiliation.objects.update_from_esi()

        # then
        ca.refresh_from_db()
        self.assertEqual(ca.character, contact.eve_entity)
        self.assertEqual(ca.corporation, corporation)
        self.assertIsNone(ca.alliance)
        self.assertIsNone(ca.faction)
        self.assertIsNone(ca.eve_character)

    @pook.on
    def test_should_update_existing_for_contacts_and_requests_and_revocations(self):
        # given
        cs = ContactSetFactory()
        contact = ContactCharacterFactory(contact_set=cs)
        ca_ct = CharacterAffiliationFactory(character=contact.eve_entity)
        corporation_ct = EveEntityCorporationFactory()
        alliance_ct = EveEntityAllianceFactory()
        faction_ct = EveEntityFactionFactory()

        rq = StandingRequestCharacterFactory()
        character_rq = EveEntityCharacterFactory(id=rq.contact_id)
        ca_rq = CharacterAffiliationFactory(character=character_rq)
        corporation_rq = EveEntityCorporationFactory()
        alliance_rq = EveEntityAllianceFactory()
        faction_rq = EveEntityFactionFactory()

        rv = StandingRevocationCharacterFactory()
        character_rv = EveEntityCharacterFactory(id=rv.contact_id)
        ca_rv = CharacterAffiliationFactory(character=character_rv)
        corporation_rv = EveEntityCorporationFactory()
        alliance_rv = EveEntityAllianceFactory()
        faction_rv = EveEntityFactionFactory()

        pook.post(
            make_esi_url("characters/affiliation"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "alliance_id": alliance_ct.id,
                    "character_id": contact.eve_entity.id,
                    "corporation_id": corporation_ct.id,
                    "faction_id": faction_ct.id,
                },
                {
                    "alliance_id": alliance_rq.id,
                    "character_id": rq.contact_id,
                    "corporation_id": corporation_rq.id,
                    "faction_id": faction_rq.id,
                },
                {
                    "alliance_id": alliance_rv.id,
                    "character_id": rv.contact_id,
                    "corporation_id": corporation_rv.id,
                    "faction_id": faction_rv.id,
                },
            ],
        )

        # when
        CharacterAffiliation.objects.update_from_esi()

        # then
        ca_ct.refresh_from_db()
        self.assertEqual(ca_ct.corporation, corporation_ct)
        self.assertEqual(ca_ct.alliance, alliance_ct)
        self.assertEqual(ca_ct.faction, faction_ct)

        ca_rq.refresh_from_db()
        self.assertEqual(ca_rq.corporation, corporation_rq)
        self.assertEqual(ca_rq.alliance, alliance_rq)
        self.assertEqual(ca_rq.faction, faction_rq)

        ca_rv.refresh_from_db()
        self.assertEqual(ca_rv.corporation, corporation_rv)
        self.assertEqual(ca_rv.alliance, alliance_rv)
        self.assertEqual(ca_rv.faction, faction_rv)

    @pook.on
    def test_should_do_nothing_when_fetching_from_esi_failed(self):
        # given
        cs = ContactSetFactory()
        ContactCharacterFactory(contact_set=cs)
        pook.post(
            make_esi_url("characters/affiliation"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "not found"},
        )

        # when
        CharacterAffiliation.objects.update_from_esi()


class TestCharacterAffiliationsManager_UpdateEveCharacterRelations_2(NoSocketsTestCase):
    def test_should_set_new_from_matching_eve_characters(self):
        # given
        character = EveCharacterFactory()
        CharacterAffiliationFactory(character__id=character.character_id)

        # when
        CharacterAffiliation.objects.update_eve_character_relations()

        # then
        self.assertEqual(CharacterAffiliation.objects.count(), 1)
        obj = CharacterAffiliation.objects.first()
        self.assertEqual(obj.eve_character, character)

    def test_should_update_from_matching_eve_characters(self):
        # given
        character = EveCharacterFactory()
        CharacterAffiliationFactory(
            character__id=character.character_id, eve_character=EveCharacterFactory()
        )

        # when
        CharacterAffiliation.objects.update_eve_character_relations()

        # then
        self.assertEqual(CharacterAffiliation.objects.count(), 1)
        obj = CharacterAffiliation.objects.first()
        self.assertEqual(obj.eve_character, character)


class TestCorporationDetailsManager_UpdateOrCreateFromEsi(TestCaseWithClearCache):
    @pook.on
    def test_should_update_corporations(self):
        # given
        corporation = EveEntityCorporationFactory()
        alliance = EveEntityAllianceFactory()
        ceo = EveEntityCharacterFactory()
        corporation_ticker = "WYT"
        member_count = 42
        pook.get(
            make_esi_url(f"corporations/{corporation.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "alliance_id": alliance.id,
                "ceo_id": ceo.id,
                "creator_id": 90000001,
                "member_count": member_count,
                "name": corporation.name,
                "tax_rate": 0,
                "ticker": corporation_ticker,
            },
        )
        # when
        obj: CorporationDetails
        obj, created = CorporationDetails.objects.update_or_create_from_esi(
            corporation.id
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.corporation, corporation)
        self.assertEqual(obj.alliance, alliance)
        self.assertEqual(obj.ceo, ceo)
        self.assertEqual(obj.member_count, member_count)
        self.assertEqual(obj.ticker, corporation_ticker)
        self.assertIsNone(obj.faction)

    @pook.on
    def test_should_handle_missing_ceo(self):
        # given
        corporation = EveEntityCorporationFactory()
        alliance = EveEntityAllianceFactory()
        corporation_ticker = "WYT"
        member_count = 42
        pook.get(
            make_esi_url(f"corporations/{corporation.id}"),
            reply=HTTPStatus.OK,
            response_json={
                "alliance_id": alliance.id,
                "ceo_id": 1,
                "creator_id": 90000001,
                "member_count": member_count,
                "name": corporation.name,
                "tax_rate": 0,
                "ticker": corporation_ticker,
            },
        )
        # when
        obj: CorporationDetails
        obj, created = CorporationDetails.objects.update_or_create_from_esi(
            corporation.id
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.corporation, corporation)
        self.assertEqual(obj.alliance, alliance)
        self.assertIsNone(obj.ceo)
        self.assertEqual(obj.member_count, member_count)
        self.assertEqual(obj.ticker, corporation_ticker)
        self.assertIsNone(obj.faction)


class TestCorporationDetailsManager_CorporationIdsFromContacts(NoSocketsTestCase):
    def test_should_return_all_corporation_ids(self):
        # given
        character = ContactCharacterFactory()
        ca = CharacterAffiliationFactory(character__id=character.contact_id)
        corporation_1 = ContactCorporationFactory()

        # when
        got = CorporationDetails.objects.corporation_ids_from_contacts()

        # then
        want = {corporation_1.contact_id, ca.corporation.id}
        self.assertSetEqual(got, want)


@patch(MANAGERS_PATH + ".create_eve_entities")
class TestRequestLogEntryManager_CreateFromStandingRequest(NoSocketsTestCase):
    def test_should_create_entry_for_effective_request_with_approver(
        self, mock_create_eve_entities
    ):
        # given
        approver_2 = UserMainApproverFactory()
        action = RequestLogEntry.Action.CONFIRMED
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        obj: RequestLogEntry = RequestLogEntry.objects.create_from_standing_request(
            sr, action, approver_2
        )

        # then
        self.assertEqual(obj.action, action)
        self.assertEqual(obj.action_by.user.username, approver_2.username)
        self.assertEqual(obj.reason, sr.reason)
        self.assertEqual(obj.request_type, RequestLogEntry.RequestType.REQUEST)
        self.assertEqual(obj.requested_by.user.username, sr.user.username)
        self.assertEqual(obj.requested_for.character.id, sr.contact_id)
        self.assertTrue(mock_create_eve_entities.delay.called)

    def test_should_create_entry_for_effective_request_without_approver(
        self, mock_create_eve_entities
    ):
        # given
        action = RequestLogEntry.Action.CONFIRMED
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        obj: RequestLogEntry = RequestLogEntry.objects.create_from_standing_request(
            sr, action, None
        )

        # then
        self.assertEqual(obj.action, action)
        self.assertIsNone(obj.action_by)
        self.assertEqual(obj.reason, sr.reason)
        self.assertEqual(obj.request_type, RequestLogEntry.RequestType.REQUEST)
        self.assertEqual(obj.requested_by.user.username, sr.user.username)
        self.assertEqual(obj.requested_for.character.id, sr.contact_id)
        self.assertTrue(mock_create_eve_entities.delay.called)

    def test_should_create_entry_for_effective_revocation(
        self, mock_create_eve_entities
    ):
        # given
        approver_2 = UserMainApproverFactory()
        action = RequestLogEntry.Action.CONFIRMED
        sr = StandingRevocationCharacterFactory(effective=True)

        # when
        obj: RequestLogEntry = RequestLogEntry.objects.create_from_standing_request(
            sr, action, approver_2
        )

        # then
        self.assertEqual(obj.action, action)
        self.assertEqual(obj.action_by.user.username, approver_2.username)
        self.assertEqual(obj.reason, sr.reason)
        self.assertEqual(obj.request_type, RequestLogEntry.RequestType.REVOCATION)
        self.assertEqual(obj.requested_by.user.username, sr.user.username)
        self.assertEqual(obj.requested_for.character.id, sr.contact_id)
        self.assertTrue(mock_create_eve_entities.delay.called)


class TestFrozenAuthUserManager_GetOrCreateFromUser(NoSocketsTestCase):
    def test_should_create_minimal_obj(self):
        # given
        main = EveCharacterFactory(corporation__create_alliance=False)
        state = StateFactory(member_characters=[main])
        user = UserMainFactory(main_character__character=main)

        # when
        obj: FrozenAuthUser
        obj, created = FrozenAuthUser.objects.get_or_create_from_user(user)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.user, user)
        self.assertEqual(obj.character.id, main.character_id)
        self.assertEqual(obj.corporation.id, main.corporation_id)
        self.assertIsNone(obj.alliance)
        self.assertIsNone(obj.faction)
        self.assertEqual(obj.state, state)

    def test_should_create_full_obj(self):
        # given
        main = EveCharacterFactory()
        main.faction_id = 500001
        main.faction_name = "Caldari State"
        main.save()
        state = StateFactory(member_characters=[main])
        user = UserMainFactory(main_character__character=main)

        # when
        obj: FrozenAuthUser
        obj, created = FrozenAuthUser.objects.get_or_create_from_user(user)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.user, user)
        self.assertEqual(obj.character.id, main.character_id)
        self.assertEqual(obj.corporation.id, main.corporation_id)
        self.assertEqual(obj.alliance.id, main.alliance_id)
        self.assertEqual(obj.faction.id, main.faction_id)
        self.assertEqual(obj.state, state)

    def test_should_create_from_user_without_main(self):
        # given
        user = UserFactory()

        # when
        obj: FrozenAuthUser
        obj, created = FrozenAuthUser.objects.get_or_create_from_user(user)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.user, user)
        self.assertIsNone(obj.character)
        self.assertIsNone(obj.corporation)
        self.assertIsNone(obj.alliance)

    def test_should_not_save_updated_obj(self):
        # given
        user = UserMainFactory()
        obj, _ = FrozenAuthUser.objects.get_or_create_from_user(user)

        # when
        obj.character_id = 1002
        with self.assertRaises(RuntimeError):
            obj.save()

    def test_should_not_update_obj(self):
        # given
        user = UserMainFactory()
        obj, _ = FrozenAuthUser.objects.get_or_create_from_user(user)

        # when
        with self.assertRaises(RuntimeError):
            FrozenAuthUser.objects.filter(pk=obj.pk).update(character_id=1002)

    def test_should_return_existing_obj_when_it_already_exists(self):
        # given
        main = EveCharacterFactory(corporation__create_alliance=False)
        StateFactory(member_characters=[main])
        user = UserMainFactory(main_character__character=main)
        obj_1, _ = FrozenAuthUser.objects.get_or_create_from_user(user)

        # when
        obj_2, created = FrozenAuthUser.objects.get_or_create_from_user(user)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_2, obj_1)

    def test_should_return_existing_obj_when_it_already_exists_and_no_main(self):
        # given
        user = UserFactory()
        obj_1, _ = FrozenAuthUser.objects.get_or_create_from_user(user)

        # when
        obj_2, created = FrozenAuthUser.objects.get_or_create_from_user(user)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_1, obj_2)

    def test_should_reset_to_sentinel_when_user_is_deleted(self):
        # given
        user = UserMainFactory()
        obj, _ = FrozenAuthUser.objects.get_or_create_from_user(user)

        # when
        user.delete()

        # then
        obj.refresh_from_db()
        self.assertEqual(obj.user.username, "deleted")


class TestFrozenAltManager_GetOrCreateFromStandingRequest(NoSocketsTestCase):
    def test_should_create_new_character_without_affiliations(self):
        # given
        sr = StandingRequestCharacterFactory()

        # when
        obj: FrozenAlt
        obj, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.character.id, sr.contact_id)
        self.assertIsNone(obj.corporation)
        self.assertIsNone(obj.alliance)
        self.assertEqual(obj.category, FrozenAlt.Category.CHARACTER)

    def test_should_create_new_character_with_affiliations(self):
        # given
        sr = StandingRequestCharacterFactory()
        ca = CharacterAffiliationFactory(character__id=sr.contact_id)

        # when
        obj: FrozenAlt
        obj, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.character.id, sr.contact_id)
        self.assertEqual(obj.corporation, ca.corporation)
        self.assertEqual(obj.alliance, ca.alliance)
        self.assertEqual(obj.faction, ca.faction)
        self.assertEqual(obj.category, FrozenAlt.Category.CHARACTER)

    def test_should_create_new_corporation_without_affiliations(self):
        # given
        sr = StandingRequestCorporationFactory()

        # when
        obj: FrozenAlt
        obj, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertTrue(created)
        self.assertIsNone(obj.character)
        self.assertEqual(obj.corporation.id, sr.contact_id)
        self.assertIsNone(obj.alliance)
        self.assertEqual(obj.category, FrozenAlt.Category.CORPORATION)

    def test_should_create_new_corporation_with_affiliations(self):
        # given
        sr = StandingRequestCorporationFactory()
        cd = CorporationDetailsFactory(corporation__id=sr.contact_id)

        # when
        obj: FrozenAlt
        obj, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertTrue(created)
        self.assertIsNone(obj.character)
        self.assertEqual(obj.corporation, cd.corporation)
        self.assertEqual(obj.alliance, cd.alliance)
        self.assertEqual(obj.category, FrozenAlt.Category.CORPORATION)

    def test_should_return_existing_minimal_obj_when_it_exists(self):
        # given
        sr = StandingRequestCharacterFactory()
        obj_1 = FrozenAltCharacterFactory(
            character__id=sr.contact_id, corporation=None, alliance=None, faction=None
        )

        # when
        obj_2, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_1, obj_2)

    def test_should_return_existing_full_obj_when_it_exists(self):
        # given
        sr = StandingRequestCharacterFactory()
        ca = CharacterAffiliationFactory(character__id=sr.contact_id)
        obj_1 = FrozenAltCharacterFactory(
            character=ca.character,
            alliance=ca.alliance,
            corporation=ca.corporation,
            faction=ca.faction,
        )
        # when
        obj_2, created = FrozenAlt.objects.get_or_create_from_standing_request(sr)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_1, obj_2)
