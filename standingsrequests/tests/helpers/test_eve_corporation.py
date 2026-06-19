from http import HTTPStatus
from unittest.mock import patch

import pook

from eveuniverse.tests.testdata.factories_2 import EveEntityAllianceFactory

from app_utils.testdata_factories import EveCharacterFactory, EveCorporationInfoFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.helpers.eve_corporation import (
    EveCorporationHelper,
    user_can_request_corporation_standing,
)
from standingsrequests.tests.factories import (
    EveCorporationHelperFactory,
    UserMainRequestorFactory,
    make_esi_url,
)
from standingsrequests.tests.utils import TestCaseWithClearCache

EVECORPORATION_PATH = "standingsrequests.helpers.eve_corporation"
MODELS_PATH = "standingsrequests.models"


class TestEveCorporation(NoSocketsTestCase):
    def test_can_create(self):
        # given
        corporation = EveCorporationHelperFactory(
            corporation_id=98000001,
            corporation_name="Wayne Technologies",
            ticker="WYT",
            ceo_id=1003,
            member_count=3,
            alliance_id=99000001,
            alliance_name="Wayne Enterprises",
        )
        # when/then
        self.assertEqual(corporation.corporation_id, 98000001)
        self.assertEqual(corporation.corporation_name, "Wayne Technologies")
        self.assertEqual(corporation.ticker, "WYT")
        self.assertEqual(corporation.member_count, 3)
        self.assertEqual(corporation.alliance_id, 99000001)
        self.assertEqual(corporation.alliance_name, "Wayne Enterprises")

    def test_can_report_whether_corp_is_npc(self):
        cases = [
            (EveCorporationHelperFactory(corporation_id=1000134), True),
            (EveCorporationHelperFactory(corporation_id=98000001), False),
        ]
        for corporation, want in cases:
            self.assertEqual(corporation.is_npc, want)


@patch(EVECORPORATION_PATH + ".cache")
class TestEveCorporation_GetByID(TestCaseWithClearCache):
    @pook.on
    def test_get_corp_by_id_not_in_cache(self, mock_cache):
        # given
        alliance_id = 99000001
        alliance_name = "Wayne Enterprises"
        ceo_id = 90000001
        corporation_id = 98000001
        corporation_name = "Wayne Technologies"
        corporation_ticker = "WYT"
        member_count = 42
        EveEntityAllianceFactory(id=alliance_id, name=alliance_name)
        pook.get(
            make_esi_url(f"corporations/{corporation_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "alliance_id": alliance_id,
                "ceo_id": ceo_id,
                "creator_id": 90000001,
                "member_count": member_count,
                "name": corporation_name,
                "tax_rate": 0,
                "ticker": corporation_ticker,
            },
        )
        mock_cache.get.return_value = None

        # when
        got = EveCorporationHelper.get_by_id(corporation_id)

        # then
        self.assertEqual(got.alliance_id, alliance_id)
        self.assertEqual(got.alliance_name, alliance_name)
        self.assertEqual(got.ceo_id, ceo_id)
        self.assertEqual(got.corporation_id, corporation_id)
        self.assertEqual(got.corporation_name, corporation_name)
        self.assertEqual(got.ticker, corporation_ticker)
        self.assertEqual(got.member_count, member_count)

        self.assertTrue(mock_cache.set.called)

    @pook.on
    def test_get_corp_by_id_not_in_cache_and_esi_failed(self, mock_cache):
        # given
        corporation_id = 98000001
        pook.get(
            make_esi_url(f"corporations/{corporation_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "some error"},
        )
        mock_cache.get.return_value = None

        # when
        obj = EveCorporationHelper.get_by_id(corporation_id)

        # then
        self.assertIsNone(obj)

    @pook.on
    def test_get_corp_by_id_in_cache(self, mock_cache):
        # given
        corporation = EveCorporationHelperFactory()
        mock_cache.get.return_value = corporation

        # when
        obj = EveCorporationHelper.get_by_id(corporation.corporation_id)

        # then
        self.assertEqual(obj, corporation)


class TestEveCorporation_FetchCorporationFromApi(TestCaseWithClearCache):
    @pook.on
    def test_can_fetch_corporation_from_api(self):
        # given
        alliance_id = 99000001
        alliance_name = "Wayne Enterprises"
        ceo_id = 90000001
        corporation_id = 98000001
        corporation_name = "Wayne Technologies"
        corporation_ticker = "WYT"
        member_count = 42
        EveEntityAllianceFactory(id=alliance_id, name=alliance_name)
        pook.get(
            make_esi_url(f"corporations/{corporation_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "alliance_id": alliance_id,
                "ceo_id": ceo_id,
                "creator_id": 90000001,
                "member_count": member_count,
                "name": corporation_name,
                "tax_rate": 0,
                "ticker": corporation_ticker,
            },
        )

        # when
        got = EveCorporationHelper.fetch_corporation_from_api(corporation_id)

        # then
        self.assertEqual(got.alliance_id, alliance_id)
        self.assertEqual(got.alliance_name, alliance_name)
        self.assertEqual(got.ceo_id, ceo_id)
        self.assertEqual(got.corporation_id, corporation_id)
        self.assertEqual(got.corporation_name, corporation_name)
        self.assertEqual(got.ticker, corporation_ticker)
        self.assertEqual(got.member_count, member_count)

    @pook.on
    def test_should_return_none_when_request_failed(self):
        # given
        corporation_id = 98000001
        pook.get(
            make_esi_url(f"corporations/{corporation_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "some error"},
        )

        # when
        obj = EveCorporationHelper.get_by_id(corporation_id)

        # then
        self.assertIsNone(obj)


class TestEveCorporation_GetManyById(TestCaseWithClearCache):
    @pook.on
    def test_should_return_corporations(self):
        # given
        corporation_id_1 = 90000001
        corporation_id_2 = 90000002
        pook.get(
            make_esi_url(f"corporations/{corporation_id_1}"),
            reply=HTTPStatus.OK,
            response_json={
                "ceo_id": 90000001,
                "creator_id": 90000001,
                "member_count": 1,
                "name": "corp #90000001",
                "tax_rate": 0,
                "ticker": "string",
            },
        )
        pook.get(
            make_esi_url(f"corporations/{corporation_id_2}"),
            reply=HTTPStatus.OK,
            response_json={
                "ceo_id": 90000002,
                "creator_id": 90000002,
                "member_count": 1,
                "name": "corp 90000002",
                "tax_rate": 0,
                "ticker": "string",
            },
        )
        pook.get(
            make_esi_url("status"),
            reply=HTTPStatus.OK,
            response_json={
                "players": 42,
                "server_version": "string",
                "start_time": "2019-08-24T14:15:22Z",
            },
        )

        # when
        result = EveCorporationHelper.get_many_by_id(
            [corporation_id_1, corporation_id_2]
        )

        # then
        got = {obj.corporation_id for obj in result}
        self.assertSetEqual(got, {corporation_id_1, corporation_id_2})
        self.assertTrue(pook.isdone())


class TestEveCorporation_MemberTokensCountForUser(NoSocketsTestCase):
    def test_should_count_valid_characters_only(self):
        # given
        scope_name = "special-scope"
        corporation = EveCorporationInfoFactory()
        corporation_2 = EveCorporationHelperFactory(corporation=corporation)
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation), scopes=[scope_name]
        )  # same corp and valid scope
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation)
        )  # same corp, but invalid scope
        add_character_to_user(user, EveCharacterFactory())  # different corp

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": {scope_name}}):
            result = corporation_2.member_tokens_count_for_user(user)

        # then
        self.assertEqual(result, 2)


class TestEveCorporation_UserHasAllMemberTokens(NoSocketsTestCase):
    def test_should_confirm_when_user_has_all_tokens(self):
        # given
        scope_name = "special-scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        corporation_2 = EveCorporationHelperFactory(corporation=corporation)
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation), scopes=[scope_name]
        )  # same corp and valid scope

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": {scope_name}}):
            got = corporation_2.user_has_all_member_tokens(user)

        # then
        self.assertTrue(got)

    def test_should_deny_when_not_all_members_in_auth(self):
        # given
        scope_name = "special-scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        corporation_2 = EveCorporationHelperFactory(corporation=corporation)
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": {scope_name}}):
            got = corporation_2.user_has_all_member_tokens(user)

        # then
        self.assertFalse(got)

    def test_should_deny_when_not_all_members_with_correct_scope(self):
        # given
        scope_name = "special-scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        corporation_2 = EveCorporationHelperFactory(corporation=corporation)
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )
        add_character_to_user(
            user, EveCharacterFactory(corporation=corporation), scopes=["invalid-scope"]
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": {scope_name}}):
            got = corporation_2.user_has_all_member_tokens(user)

        # then
        self.assertFalse(got)


@patch(EVECORPORATION_PATH + ".EveCorporationHelper.get_by_id")
class TestUserCanRequestCorporationStanding(NoSocketsTestCase):
    def test_should_confirm_when_user_owns_all_members(self, mock_get_corp_by_id):
        # given
        scope_name = "special_scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
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
            got = user_can_request_corporation_standing(
                user, corporation.corporation_id
            )

        # then
        self.assertTrue(got)

    def test_should_deny_when_user_does_not_own_all_members(self, mock_get_corp_by_id):
        # given
        scope_name = "special_scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
        )
        user = UserMainRequestorFactory(
            main_character__character=EveCharacterFactory(corporation=corporation),
            main_character__scopes=[scope_name],
        )

        # when
        with patch(MODELS_PATH + ".SR_REQUIRED_SCOPES", {"Guest": [scope_name]}):
            got = user_can_request_corporation_standing(
                user, corporation.corporation_id
            )

        # then
        self.assertFalse(got)

    def test_should_deny_when_user_owns_all_members_but_some_scopes_are_incorrect(
        self, mock_get_corp_by_id
    ):
        # given
        scope_name = "special_scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
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
            got = user_can_request_corporation_standing(
                user, corporation.corporation_id
            )

        # then
        self.assertFalse(got)

    def test_should_deny_when_some_members_are_owned_by_another_user(
        self, mock_get_corp_by_id
    ):
        # given
        scope_name = "special_scope"
        corporation = EveCorporationInfoFactory(member_count=2)
        mock_get_corp_by_id.return_value = EveCorporationHelperFactory(
            corporation=corporation
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
            got = user_can_request_corporation_standing(
                user, corporation.corporation_id
            )

        # then
        self.assertFalse(got)
