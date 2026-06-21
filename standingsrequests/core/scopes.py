from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from esi.models import Token

from allianceauth.eveonline.models import EveCharacter

from standingsrequests.core import app_config


def user_can_request_standing_for_character(
    user: User, character: EveCharacter, quick_check: bool = False
) -> bool:
    """Report whether a user has the required scopes
    for requesting standing for a character.

    Params:
    - user: provide User object to shorten processing time
    - quick_check: if True will not check if tokens are valid to save time
    """
    try:
        owner = character.character_ownership.user
    except ObjectDoesNotExist:
        return False

    if owner != user:
        return False

    try:
        state_name = user.profile.state.name
    except ObjectDoesNotExist:
        return False

    scopes = app_config.required_scopes_for_state(state_name)
    if not scopes:
        return True

    scopes_string = " ".join(scopes)
    token_qs = Token.objects.filter(character_id=character.character_id).require_scopes(
        scopes_string
    )

    if not quick_check:
        token_qs = token_qs.require_valid()

    result = token_qs.exists()
    return result
