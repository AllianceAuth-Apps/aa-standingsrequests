from unittest.mock import patch

from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.helpers.eve_character import (
    EveCharacterHelper,
    has_required_scopes_for_request,
)
from standingsrequests.tests.factories import (
    CharacterAffiliationFactory,
    UserMainRequestorFactory,
)

MODULE_PATH = "standingsrequests.helpers.eve_character"


class TestEveCharacterHelper(NoSocketsTestCase):
    def test_should_initialize_from_character_affiliation_with_alliance(self):
        # given
        ca = CharacterAffiliationFactory()

        # when
        character = EveCharacterHelper(character_id=ca.character.id)

        # then
        self.assertEqual(character.character_id, ca.character.id)
        self.assertEqual(character.character_name, ca.character.name)
        self.assertEqual(character.corporation_id, ca.corporation.id)
        self.assertEqual(character.corporation_name, ca.corporation.name)
        self.assertEqual(character.alliance_id, ca.alliance.id)
        self.assertEqual(character.alliance_name, ca.alliance.name)

    def test_should_initialize_from_character_affiliation_without_alliance(self):
        # given
        ca = CharacterAffiliationFactory(alliance=None)

        # when
        character = EveCharacterHelper(character_id=ca.character.id)

        # then
        self.assertEqual(character.character_id, ca.character.id)
        self.assertEqual(character.character_name, ca.character.name)
        self.assertEqual(character.corporation_id, ca.corporation.id)
        self.assertEqual(character.corporation_name, ca.corporation.name)
        self.assertIsNone(character.alliance_id)
        self.assertIsNone(character.alliance_name)

    def test_should_initialize_without_character_affiliation(self):
        # when
        character = EveCharacterHelper(1001)

        # then
        self.assertEqual(character.character_id, 1001)


@patch(MODULE_PATH + ".app_config.required_scopes_for_state")
class TestStandingRequest_HasRequiredScopesForRequest(NoSocketsTestCase):
    def test_should_confirm_when_user_has_character_token_with_required_scopes(
        self, mock_required_scopes_for_state
    ):
        scope_name = "abc"
        mock_required_scopes_for_state.return_value = [scope_name]
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=[scope_name])

        # when
        got = has_required_scopes_for_request(character, quick_check=True)

        # then
        self.assertTrue(got)

    def test_should_deny_when_user_has_character_token_but_with_wrong_scopes(
        self, mock_required_scopes_for_state
    ):
        scope_name = "abc"
        mock_required_scopes_for_state.return_value = [scope_name]
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character, scopes=["other_scope"])

        # when
        got = has_required_scopes_for_request(character, quick_check=True)

        # then
        self.assertFalse(got)

    def test_should_deny_when_character_has_no_owner(
        self, mock_required_scopes_for_state
    ):
        # given
        mock_required_scopes_for_state.return_value = ["abc"]
        character = EveCharacterFactory()

        # when
        got = has_required_scopes_for_request(character)

        # then
        self.assertFalse(got)
