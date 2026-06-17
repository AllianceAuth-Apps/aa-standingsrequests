from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.utils.timezone import now
from eveuniverse.models import EveEntity

from app_utils.testdata_factories import EveCharacterFactory, EveCorporationInfoFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.models import (
    AbstractStandingsRequest,
    StandingRequest,
    StandingRevocation,
)
from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    ContactCharacterFactory,
    ContactCorporationFactory,
    ContactSetFactory,
    EveCorporationHelperFactory,
    StandingRequestCharacterFactory,
    StandingRevocationCharacterFactory,
    UserMainApproverFactory,
    UserMainRequestorFactory,
)

CORE_PATH = "standingsrequests.core"
MODELS_PATH = "standingsrequests.models"
STANDINGS_ALLIANCE_ID = 99_000_123


class TestAbstractStandingsRequest_ReportType(NoSocketsTestCase):
    def test_should_say_standing_request(self):
        # given
        sr = StandingRequestCharacterFactory()
        # then
        self.assertTrue(sr.is_standing_request)
        self.assertFalse(sr.is_standing_revocation)

    def test_should_say_standing_revocation(self):
        # given
        sr = StandingRevocationCharacterFactory()
        # then
        self.assertFalse(sr.is_standing_request)
        self.assertTrue(sr.is_standing_revocation)


class TestAbstractStandingsRequest_EvaluateEffectiveStanding(NoSocketsTestCase):
    def test_should_report_whether_standing_request_is_satisfied_only(self):
        cases = [
            ("positive standing", 10, True),
            ("negative standing", -10, False),
            ("no standing", None, False),
        ]
        for name, standing, want in cases:
            with self.subTest(name=name):
                # given
                if standing is not None:
                    contact = ContactCharacterFactory(standing=standing)
                    sr = StandingRequestCharacterFactory(contact_id=contact.contact_id)
                else:
                    sr = StandingRequestCharacterFactory()

                # when
                got = sr.evaluate_effective_standing(check_only=True)

                # then
                self.assertEqual(got, want)
                sr.refresh_from_db()
                self.assertFalse(sr.is_effective)

    def test_should_report_whether_standing_revocation_is_satisfied_only(self):
        cases = [
            ("positive standing", 10, False),
            ("negative standing", -10, True),
            ("no standing", None, True),
        ]
        for name, standing, want in cases:
            with self.subTest(name=name):
                # given
                if standing is not None:
                    contact = ContactCharacterFactory(standing=standing)
                    sr = StandingRevocationCharacterFactory(
                        contact_id=contact.contact_id
                    )
                else:
                    sr = StandingRevocationCharacterFactory()

                # when
                got = sr.evaluate_effective_standing(check_only=True)

                # then
                self.assertEqual(got, want)
                sr.refresh_from_db()
                self.assertFalse(sr.is_effective)

    def test_should_report_standing_request_as_satisfied_and_mark_as_effective(self):
        # given
        contact = ContactCharacterFactory(standing=10)
        sr = StandingRequestCharacterFactory(contact_id=contact.contact_id)

        # when
        got = sr.evaluate_effective_standing(check_only=False)

        # when
        self.assertTrue(got)
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertIsInstance(sr.effective_date, datetime)

    def test_should_report_standing_revocation_as_satisfied_and_mark_as_effective(self):
        # given
        sr = StandingRevocationCharacterFactory()

        # when
        got = sr.evaluate_effective_standing(check_only=False)

        # when
        self.assertTrue(got)
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertIsInstance(sr.effective_date, datetime)


class TestCharacterAffiliation_CharacterName(NoSocketsTestCase):
    def test_should_return_character_name(self):
        # given
        character_name = "Peter Parker"
        ca = CharacterAffiliationFactory(character__name=character_name)

        # when
        got = ca.character_name

        # then
        self.assertEqual(got, character_name)

    def test_should_return_none_when_no_character_name(self):
        # given
        character = EveEntity.objects.create(id=1999)
        ca = CharacterAffiliationFactory(character=character)

        # when/then
        self.assertIsNone(ca.character_name)


class TestContactSet(NoSocketsTestCase):
    def test_str(self):
        # given
        cs = ContactSetFactory()
        self.assertIsInstance(str(cs), str)


@patch(
    MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Member": ["my_scope"], "Blue": [], "": []}
)
@patch(CORE_PATH + ".app_config.STR_ALLIANCE_IDS", [STANDINGS_ALLIANCE_ID])
@patch("standingsrequests.managers.create_eve_entities", Mock())
class TestContactSet_GenerateStandingRequestsForBlueAlts(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EveCharacterFactory(alliance_id=STANDINGS_ALLIANCE_ID)
        cls.main_character = EveCharacterFactory(alliance_id=STANDINGS_ALLIANCE_ID)

    def test_should_create_request_when_alt_already_has_standing(self):
        # given
        user = UserMainRequestorFactory(main_character__character=self.main_character)
        alt = EveCharacterFactory()
        add_character_to_user(user, alt, scopes=["dummy"])
        cs = ContactSetFactory()
        ContactCharacterFactory(contact_set=cs, contact_id=alt.character_id, standing=5)

        # when
        cs.generate_standing_requests_for_blue_alts()

        # then
        request = StandingRequest.objects.get(contact_id=alt.character_id)
        self.assertTrue(request.is_effective)
        self.assertEqual(request.user, user)
        self.assertEqual(request.contact_id, alt.character_id)
        self.assertEqual(request.is_effective, True)
        self.assertAlmostEqual((now() - request.request_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.action_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.effective_date).seconds, 0, delta=30)

    def test_should_not_create_requests_for_blue_alt_if_request_already_exists(self):
        # given
        user = UserMainRequestorFactory(main_character__character=self.main_character)
        alt = EveCharacterFactory()
        add_character_to_user(user, alt, scopes=["dummy"])
        cs = ContactSetFactory()
        ContactCharacterFactory(contact_set=cs, contact_id=alt.character_id, standing=5)
        req = StandingRequestCharacterFactory(contact_id=alt.character_id, user=user)

        # when
        cs.generate_standing_requests_for_blue_alts()

        # then
        req.refresh_from_db()
        self.assertFalse(req.is_effective)

    def test_should_not_create_requests_for_non_blue_alts(self):
        # given
        user = UserMainRequestorFactory(main_character__character=self.main_character)
        alt = EveCharacterFactory()
        add_character_to_user(user, alt, scopes=["dummy"])
        cs = ContactSetFactory()
        ContactCharacterFactory(
            contact_set=cs, contact_id=alt.character_id, standing=-10
        )

        # when
        cs.generate_standing_requests_for_blue_alts()

        # then
        self.assertFalse(
            StandingRequest.objects.filter(contact_id=alt.character_id).exists()
        )

    def test_should_not_create_requests_for_alts_in_organization(self):
        # given
        user = UserMainRequestorFactory(main_character__character=self.main_character)
        alt = EveCharacterFactory(alliance_id=STANDINGS_ALLIANCE_ID)
        add_character_to_user(user, alt, scopes=["dummy"])
        cs = ContactSetFactory()
        ContactCharacterFactory(contact_set=cs, contact_id=alt.character_id, standing=5)

        # when
        cs.generate_standing_requests_for_blue_alts()

        # then
        self.assertFalse(
            StandingRequest.objects.filter(contact_id=alt.character_id).exists()
        )


class TestStandingRequest_IsStandingSatisfied(NoSocketsTestCase):
    def test_is_standing_satisfied(self):
        class MyStandingRequest(AbstractStandingsRequest):
            EXPECT_STANDING_LTEQ = 5.0
            EXPECT_STANDING_GTEQ = 0.0

        self.assertTrue(MyStandingRequest.is_standing_satisfied(5))
        self.assertTrue(MyStandingRequest.is_standing_satisfied(0))
        self.assertFalse(MyStandingRequest.is_standing_satisfied(-10))
        self.assertFalse(MyStandingRequest.is_standing_satisfied(10))
        self.assertFalse(MyStandingRequest.is_standing_satisfied(None))


class TestStandingRequest_TestMarkStandingActioned(NoSocketsTestCase):
    def test_should_mark_standing_as_actioned(self):
        # given
        sr = StandingRequestCharacterFactory()
        approver = UserMainApproverFactory()

        # when
        sr.mark_actioned(approver)

        # then
        sr.refresh_from_db()
        self.assertEqual(sr.action_by, approver)
        self.assertIsInstance(sr.action_date, datetime)
        self.assertEqual(sr.reason, StandingRequest.Reason.NONE)

    def test_should_mark_standing_as_actioned_with_reason(self):
        # given
        sr = StandingRequestCharacterFactory()
        approver = UserMainApproverFactory()

        # when
        sr.mark_actioned(user=approver, reason=StandingRequest.Reason.STANDING_IN_GAME)

        # then
        sr.refresh_from_db()
        self.assertEqual(sr.action_by, approver)
        self.assertIsInstance(sr.action_date, datetime)
        self.assertEqual(sr.reason, StandingRequest.Reason.STANDING_IN_GAME)


class TestStandingRequest_MarkEffective(NoSocketsTestCase):
    def test_should_mark_standing_as_effective(self):
        # given
        contact = ContactCharacterFactory(standing=10)
        sr = StandingRequestCharacterFactory(contact_id=contact.contact_id)

        # when
        sr.mark_effective()

        # then
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertTrue(sr.effective_date)

    def test_mark_standing_effective_with_date(self):
        # given
        contact = ContactCharacterFactory(standing=10)
        sr = StandingRequestCharacterFactory(contact_id=contact.contact_id)
        my_date = now() - timedelta(hours=4)

        # when
        sr.mark_effective(date=my_date)

        # then
        sr.refresh_from_db()
        self.assertTrue(sr.is_effective)
        self.assertEqual(sr.effective_date, my_date)


class TestStandingRequest_CheckActionedTimeout(NoSocketsTestCase):
    def test_should_return_none_when_already_effective(self):
        # given
        ContactSetFactory()
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        self.assertIsNone(sr.check_actioned_timeout())

    def test_should_return_none_when_not_effective(self):
        # given
        ContactSetFactory()
        sr = StandingRequestCharacterFactory()

        # when
        self.assertIsNone(sr.check_actioned_timeout())

    def test_check_standing_actioned_timeout_after_deadline(self):
        # given
        ContactSetFactory()
        approver = UserMainApproverFactory()
        sr = StandingRequestCharacterFactory(
            action_by=approver,
            action_date=now() - timedelta(hours=25),
            is_effective=False,
        )

        # when
        got = sr.check_actioned_timeout()

        # then
        self.assertEqual(got, approver)
        sr.refresh_from_db()
        self.assertIsNone(sr.action_by)
        self.assertIsNone(sr.action_date)

    def test_should_return_false_when_action_has_not_timed_out(self):
        # given
        ContactSetFactory()
        my_request = StandingRequestCharacterFactory(pending=True)

        # when
        got = my_request.check_actioned_timeout()

        # then
        self.assertFalse(got)

    def test_should_return_none_when_no_contact_set_found(self):
        # given
        sr = StandingRequestCharacterFactory(pending=True)

        # when
        got = sr.check_actioned_timeout()

        # then
        self.assertIsNone(got)


class TestStandingRequest_ResetToInitial(NoSocketsTestCase):
    def test_should_reset_standing_request(self):
        # given
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        sr.reset_to_initial()

        # then
        sr.refresh_from_db()
        self.assertFalse(sr.is_effective)
        self.assertIsNone(sr.effective_date)
        self.assertIsNone(sr.action_by)
        self.assertIsNone(sr.action_date)


class TestStandingRequest_Delete(NoSocketsTestCase):
    def test_should_delete_and_not_add_revocation_when_not_effective(self):
        # given
        sr = StandingRequestCharacterFactory()

        # when
        sr.delete()

        # then
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())
        self.assertFalse(
            StandingRevocation.objects.filter(contact_id=sr.contact_id).exists()
        )

    def test_should_delete_and_add_revocation_when_effective(self):
        # given
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        sr.delete()

        # then
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())
        self.assertTrue(
            StandingRevocation.objects.filter(contact_id=sr.contact_id).exists()
        )

    def test_delete_for_effective_add_revocation_and_reason(self):
        # given
        sr = StandingRequestCharacterFactory(effective=True)

        # when
        sr.delete(reason=AbstractStandingsRequest.Reason.REVOKED_IN_GAME)

        # then
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())
        obj = StandingRevocation.objects.get(contact_id=sr.contact_id)
        self.assertEqual(obj.reason, AbstractStandingsRequest.Reason.REVOKED_IN_GAME)

    def test_should_delete_and_add_revocation_when_pending(self):
        # given
        sr = StandingRequestCharacterFactory(pending=True)

        # when
        sr.delete()

        # then
        self.assertFalse(StandingRequest.objects.filter(pk=sr.pk).exists())
        self.assertTrue(
            StandingRevocation.objects.filter(contact_id=sr.contact_id).exists()
        )

    def test_should_delete_and_not_add_revocation_when_effective_and_revocation_exists(
        self,
    ):
        # given
        rq = StandingRequestCharacterFactory(effective=True)
        StandingRevocationCharacterFactory(standing_request=rq)

        # when
        rq.delete()

        # then
        self.assertFalse(StandingRequest.objects.filter(pk=rq.pk).exists())
        self.assertEqual(
            StandingRevocation.objects.filter(contact_id=rq.contact_id).count(), 1
        )


@patch(MODELS_PATH + ".EveCorporationHelper.get_by_id")
class TestStandingRequest_CanRequestCorporationStanding(NoSocketsTestCase):
    def test_should_confirm_when_user_owns_all_members(self, mock_get_corp_by_id):
        # given
        scope_name = "special_scope"
        cs = ContactSetFactory()
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
        )
        ContactCorporationFactory(
            contact_set=cs, contact_id=corporation.corporation_id, standing=10
        )
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation), scopes=[scope_name]
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": [scope_name]}):
            got = StandingRequest.can_request_corporation_standing(
                corporation.corporation_id, user
            )

        # then
        self.assertTrue(got)

    def test_should_deny_when_user_does_not_own_all_members(self, mock_get_corp_by_id):
        # given
        scope_name = "special_scope"
        cs = ContactSetFactory()
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
        )
        ContactCorporationFactory(
            contact_set=cs, contact_id=corporation.corporation_id, standing=10
        )
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": [scope_name]}):
            got = StandingRequest.can_request_corporation_standing(
                corporation.corporation_id, user
            )

        # then
        self.assertFalse(got)

    def test_should_deny_when_user_owns_all_members_but_some_scopes_are_incorrect(
        self, mock_get_corp_by_id
    ):
        # given
        scope_name = "special_scope"
        cs = ContactSetFactory()
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
        )
        ContactCorporationFactory(
            contact_set=cs, contact_id=corporation.corporation_id, standing=10
        )
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation), scopes=["incorrect"]
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": [scope_name]}):
            got = StandingRequest.can_request_corporation_standing(
                corporation.corporation_id, user
            )

        # then
        self.assertFalse(got)

    def test_should_deny_when_some_members_are_owned_by_another_user(
        self, mock_get_corp_by_id
    ):
        # given
        scope_name = "special_scope"
        cs = ContactSetFactory()
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
        )
        ContactCorporationFactory(
            contact_set=cs, contact_id=corporation.corporation_id, standing=10
        )
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": [scope_name]}):
            got = StandingRequest.can_request_corporation_standing(
                corporation.corporation_id, user
            )

        # then
        self.assertFalse(got)


class TestStandingRequest_GetRequiredScopesForState(NoSocketsTestCase):
    def test_return_scopes_when_defined_for_state(self):
        scope_name = "abc"
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"member": [scope_name]}):
            got = StandingRequest.get_required_scopes_for_state("member")
        self.assertCountEqual(got, [scope_name])

    def test_return_empty_list_when_not_defined_for_state(self):
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"member": ["abc"]}):
            got = StandingRequest.get_required_scopes_for_state("guest")
        self.assertListEqual(got, [])

    def test_return_empty_list_when_state_is_none(self):
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"member": ["abc"]}):
            got = StandingRequest.get_required_scopes_for_state(None)
        self.assertListEqual(got, [])


@patch(MODELS_PATH + ".StandingRequest.get_required_scopes_for_state")
class TestStandingRequest_HasRequiredScopesForRequest(NoSocketsTestCase):
    def test_should_confirm_when_user_has_character_token_with_required_scopes(
        self, mock_get_required_scopes_for_state
    ):
        scope_name = "abc"
        mock_get_required_scopes_for_state.return_value = [scope_name]
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=[scope_name])

        # when
        got = StandingRequest.has_required_scopes_for_request(
            character, quick_check=True
        )

        # then
        self.assertTrue(got)

    def test_should_deny_when_user_has_character_token_but_with_wrong_scopes(
        self, mock_get_required_scopes_for_state
    ):
        scope_name = "abc"
        mock_get_required_scopes_for_state.return_value = [scope_name]
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["other_scope"])

        # when
        got = StandingRequest.has_required_scopes_for_request(
            character, quick_check=True
        )

        # then
        self.assertFalse(got)

    def test_should_deny_when_character_has_no_owner(
        self, mock_get_required_scopes_for_state
    ):
        # given
        mock_get_required_scopes_for_state.return_value = ["abc"]
        character = EveCharacterFactory()

        # when
        got = StandingRequest.has_required_scopes_for_request(character)

        # then
        self.assertFalse(got)
