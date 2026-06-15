from unittest.mock import patch

from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.models import StandingRequest, StandingRevocation
from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    EveCorporationFactory,
    StandingRequestFactory,
    StandingRevocationFactory,
    StateFactory,
    UserMainRequestorFactory,
)
from standingsrequests.views import _common

MODULE_PATH = "standingsrequests.views._common"


class TestComposeStandingRequestsData(NoSocketsTestCase):
    def test_can_create_for_character_standing_request(self):
        # given
        main = EveCharacterFactory()
        state = StateFactory(member_characters=[main])
        user = UserMainRequestorFactory(main_character__character=main)
        character = EveCharacterFactory()
        add_character_to_user(user, character)
        StandingRequestFactory(
            user=user, contact_id=character.character_id, action_by=user
        )
        CharacterAffiliationFactory(eve_character=character, is_eve_character=True)
        qs = StandingRequest.objects.all()

        # when
        with patch(
            MODULE_PATH + ".StandingRequest.has_required_scopes_for_request"
        ) as m:
            m.return_value = True
            got = _common.compose_standing_requests_data(qs)

        # then
        self.assertEqual(len(got), 1)
        obj = got[0]
        self.assertEqual(obj["action_by"], user.username)
        self.assertEqual(obj["alliance_id"], character.alliance_id)
        self.assertEqual(obj["alliance_name"], character.alliance_name)
        self.assertEqual(obj["contact_id"], character.character_id)
        self.assertEqual(obj["contact_name"], character.character_name)
        self.assertEqual(obj["corporation_name"], character.corporation_name)
        self.assertEqual(obj["corporation_ticker"], character.corporation_ticker)
        self.assertEqual(obj["has_scopes"], True)
        self.assertEqual(obj["is_character"], True)
        self.assertEqual(obj["is_corporation"], False)
        self.assertEqual(obj["is_effective"], False)
        self.assertCountEqual(obj["labels"], [])
        self.assertEqual(obj["main_character_name"], main.character_name)
        self.assertEqual(obj["state"], state.name)

    def test_can_create_for_character_standing_revocation(self):
        # given
        main = EveCharacterFactory()
        state = StateFactory(member_characters=[main])
        user = UserMainRequestorFactory(main_character__character=main)
        character = EveCharacterFactory()
        add_character_to_user(user, character)
        StandingRevocationFactory(
            user=user, contact_id=character.character_id, action_by=user
        )
        CharacterAffiliationFactory(eve_character=character, is_eve_character=True)
        qs = StandingRevocation.objects.all()

        # when
        with patch(
            MODULE_PATH + ".StandingRequest.has_required_scopes_for_request"
        ) as m:
            m.return_value = True
            got = _common.compose_standing_requests_data(qs)

        # then
        self.assertEqual(len(got), 1)
        obj = got[0]
        self.assertEqual(obj["action_by"], user.username)
        self.assertEqual(obj["alliance_id"], character.alliance_id)
        self.assertEqual(obj["alliance_name"], character.alliance_name)
        self.assertEqual(obj["contact_id"], character.character_id)
        self.assertEqual(obj["contact_name"], character.character_name)
        self.assertEqual(obj["corporation_name"], character.corporation_name)
        self.assertEqual(obj["corporation_ticker"], character.corporation_ticker)
        self.assertEqual(obj["has_scopes"], True)
        self.assertEqual(obj["is_character"], True)
        self.assertEqual(obj["is_corporation"], False)
        self.assertEqual(obj["is_effective"], False)
        self.assertCountEqual(obj["labels"], [])
        self.assertEqual(obj["main_character_name"], main.character_name)
        self.assertEqual(obj["state"], state.name)

    def test_can_create_for_corporation_standing_request(self):
        # given
        corporation = EveCorporationInfoFactory(member_count=1)
        main = EveCharacterFactory(corporation=corporation)
        state = StateFactory(member_characters=[main])
        user = UserMainRequestorFactory(main_character__character=main)
        StandingRequestFactory(
            action_by=user,
            contact_id=corporation.corporation_id,
            is_corporation=True,
            user=user,
        )
        qs = StandingRequest.objects.all()

        # when
        with (
            patch(
                MODULE_PATH + ".StandingRequest.has_required_scopes_for_request"
            ) as has_required_scopes_for_request,
            patch(MODULE_PATH + ".EveCorporation.get_many_by_id") as get_many_by_id,
        ):
            has_required_scopes_for_request.return_value = True
            get_many_by_id.return_value = [
                EveCorporationFactory(
                    ceo_id=corporation.ceo_id,
                    corporation_id=corporation.corporation_id,
                    corporation_name=corporation.corporation_name,
                    member_count=corporation.member_count,
                    ticker=corporation.corporation_ticker,
                )
            ]
            got = _common.compose_standing_requests_data(qs)

        # then
        self.assertEqual(len(got), 1)
        obj = got[0]
        self.assertEqual(obj["action_by"], user.username)
        self.assertIsNone(obj["alliance_id"])
        self.assertEqual(obj["alliance_name"], "")
        self.assertEqual(obj["contact_id"], corporation.corporation_id)
        self.assertEqual(obj["contact_name"], corporation.corporation_name)
        self.assertEqual(obj["corporation_name"], corporation.corporation_name)
        self.assertEqual(obj["corporation_ticker"], corporation.corporation_ticker)
        self.assertEqual(obj["has_scopes"], True)
        self.assertEqual(obj["is_character"], False)
        self.assertEqual(obj["is_corporation"], True)
        self.assertEqual(obj["is_effective"], False)
        self.assertCountEqual(obj["labels"], [])
        self.assertEqual(obj["main_character_name"], main.character_name)
        self.assertEqual(obj["state"], state.name)

    def test_can_create_for_corporation_standing_revocation(self):
        # given
        corporation = EveCorporationInfoFactory(member_count=1)
        main = EveCharacterFactory(corporation=corporation)
        state = StateFactory(member_characters=[main])
        user = UserMainRequestorFactory(main_character__character=main)
        StandingRevocationFactory(
            action_by=user,
            contact_id=corporation.corporation_id,
            is_corporation=True,
            user=user,
        )
        qs = StandingRevocation.objects.all()

        # when
        with (
            patch(
                MODULE_PATH + ".StandingRequest.has_required_scopes_for_request"
            ) as has_required_scopes_for_request,
            patch(MODULE_PATH + ".EveCorporation.get_many_by_id") as get_many_by_id,
        ):
            has_required_scopes_for_request.return_value = True
            get_many_by_id.return_value = [
                EveCorporationFactory(
                    ceo_id=corporation.ceo_id,
                    corporation_id=corporation.corporation_id,
                    corporation_name=corporation.corporation_name,
                    member_count=corporation.member_count,
                    ticker=corporation.corporation_ticker,
                )
            ]
            got = _common.compose_standing_requests_data(qs)

        # then
        self.assertEqual(len(got), 1)
        obj = got[0]
        self.assertEqual(obj["action_by"], user.username)
        self.assertIsNone(obj["alliance_id"])
        self.assertEqual(obj["alliance_name"], "")
        self.assertEqual(obj["contact_id"], corporation.corporation_id)
        self.assertEqual(obj["contact_name"], corporation.corporation_name)
        self.assertEqual(obj["corporation_name"], corporation.corporation_name)
        self.assertEqual(obj["corporation_ticker"], corporation.corporation_ticker)
        self.assertEqual(obj["has_scopes"], True)
        self.assertEqual(obj["is_character"], False)
        self.assertEqual(obj["is_corporation"], True)
        self.assertEqual(obj["is_effective"], False)
        self.assertCountEqual(obj["labels"], [])
        self.assertEqual(obj["main_character_name"], main.character_name)
        self.assertEqual(obj["state"], state.name)


class MainCharacterInfo_CreateFromUser(NoSocketsTestCase):
    def test_should_create_when_user_is_valid(self):
        # given
        character = EveCharacterFactory()
        user = UserMainRequestorFactory(main_character__character=character)

        # when
        got = _common.MainCharacterInfo.create_from_user(user)

        # then
        self.assertEqual(got.character_name, character.character_name)
        self.assertEqual(got.ticker, character.corporation_ticker)
        self.assertNotEqual(got.icon_url, "-")

    def test_should_return_empty_when_no_user_given(self):
        # when
        got = _common.MainCharacterInfo.create_from_user(None)

        # then
        self.assertEqual(got.character_name, "-")
        self.assertEqual(got.ticker, "-")
        self.assertEqual(got.icon_url, "-")

    def test_should_return_empty_when_user_has_no_main(self):
        # given
        user = UserFactory()

        # when
        got = _common.MainCharacterInfo.create_from_user(user)

        # then
        self.assertEqual(got.character_name, "-")
        self.assertEqual(got.ticker, "-")
        self.assertEqual(got.icon_url, "-")
