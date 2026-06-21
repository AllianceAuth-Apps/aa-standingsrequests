from typing import List, NamedTuple
from unittest.mock import patch

from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCorporationFactory,
)

from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase

from standingsrequests.core import app_config

MODULE_PATH = "standingsrequests.core.app_config"


class TestOwnerCharacter(NoSocketsTestCase):
    def test_should_return_existing_character(self):
        # given
        character = EveCharacterFactory()

        with patch(MODULE_PATH + ".STANDINGS_API_CHARID", character.character_id):
            # when
            owner_character = app_config.owner_character()

            # then
            self.assertEqual(character, owner_character)

    @patch(MODULE_PATH + ".EveCharacter.objects.create_character")
    def test_create_new_character_if_not_exists(self, mock_create_character):
        # given
        mock_create_character.side_effect = lambda x: EveCharacterFactory(
            character_id=x
        )
        character_id = 90_000_001

        # when
        with patch(MODULE_PATH + ".STANDINGS_API_CHARID", character_id):
            owner_character = app_config.owner_character()

        # then
        self.assertEqual(owner_character.character_id, character_id)


class TestStandingsSourceEntity(NoSocketsTestCase):
    def test_should_return_alliance(self):
        # given
        character = EveCharacterFactory()
        alliance = EveEntityAllianceFactory(id=character.alliance_id)

        # when

        with (
            patch(MODULE_PATH + ".STANDINGS_API_CHARID", character.character_id),
            patch(MODULE_PATH + ".SR_OPERATION_MODE", "alliance"),
        ):
            got = app_config.standings_source_entity()

        # then
        self.assertEqual(got, alliance)

    def test_should_return_corporation(self):
        # given
        character = EveCharacterFactory()
        corporation = EveEntityCorporationFactory(id=character.corporation_id)

        # when

        with (
            patch(MODULE_PATH + ".STANDINGS_API_CHARID", character.character_id),
            patch(MODULE_PATH + ".SR_OPERATION_MODE", "corporation"),
        ):
            got = app_config.standings_source_entity()

        # then
        self.assertEqual(got, corporation)


class TestIsCharacterAMember(NoSocketsTestCase):
    def test_all(self):
        character = EveCharacterFactory()

        class Case(NamedTuple):
            name: str
            corp_ids: List[int]
            alliance_ids: List[int]
            want: bool

        cases = [
            Case("is corp member", [character.corporation_id], [], True),
            Case("is alliance member", [], [character.alliance_id], True),
            Case("no corp or alliance defined", [], [], False),
            Case("not member of corp", [666], [], False),
            Case("not member of alliance", [], [666], False),
        ]

        for tc in cases:
            with self.subTest(name=tc.name):
                with (
                    patch(MODULE_PATH + ".STR_CORP_IDS", tc.corp_ids),
                    patch(MODULE_PATH + ".STR_ALLIANCE_IDS", tc.alliance_ids),
                ):
                    self.assertEqual(
                        app_config.is_character_a_member(character), tc.want
                    )


class TestGetRequiredScopesForState(NoSocketsTestCase):
    def test_return_scopes_when_defined_for_state(self):
        scope_name = "abc"
        with patch(MODULE_PATH + ".SR_REQUIRED_SCOPES", {"member": [scope_name]}):
            got = app_config.required_scopes_for_state("member")
        self.assertCountEqual(got, [scope_name])

    def test_return_empty_list_when_not_defined_for_state(self):
        with patch(MODULE_PATH + ".SR_REQUIRED_SCOPES", {"member": ["abc"]}):
            got = app_config.required_scopes_for_state("guest")
        self.assertListEqual(got, [])

    def test_return_empty_list_when_state_is_none(self):
        with patch(MODULE_PATH + ".SR_REQUIRED_SCOPES", {"member": ["abc"]}):
            got = app_config.required_scopes_for_state(None)
        self.assertListEqual(got, [])
