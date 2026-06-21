from unittest.mock import patch

from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from standingsrequests.core.scopes import user_can_request_standing_for_character
from standingsrequests.tests.factories import UserMainRequestorFactory

MODULE_PATH = "standingsrequests.core.scopes"


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
        got = user_can_request_standing_for_character(user, character, quick_check=True)

        # then
        self.assertTrue(got)

    def test_should_confirm_when_state_does_not_require_scopes(
        self, mock_required_scopes_for_state
    ):
        mock_required_scopes_for_state.return_value = []
        user = UserMainRequestorFactory()
        character = EveCharacterFactory()
        add_character_to_user(user, character)

        # when
        got = user_can_request_standing_for_character(user, character, quick_check=True)

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
        got = user_can_request_standing_for_character(user, character, quick_check=True)

        # then
        self.assertFalse(got)

    def test_should_deny_when_user_does_not_own_the_character(
        self, mock_required_scopes_for_state
    ):
        # given
        scope_name = "abc"
        mock_required_scopes_for_state.return_value = [scope_name]
        user_1 = UserMainRequestorFactory()
        character = EveCharacterFactory()
        user_2 = UserMainRequestorFactory()
        add_character_to_user(user_2, character, scopes=[scope_name])

        # when
        got = user_can_request_standing_for_character(user_1, character)

        # then
        self.assertFalse(got)
