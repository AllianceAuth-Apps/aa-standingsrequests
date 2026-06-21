from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.evelinks import eveimageserver
from allianceauth.eveonline.models import EveCharacter

from standingsrequests.constants import DEFAULT_IMAGE_SIZE
from standingsrequests.core import app_config


class EveCharacterHelper:
    """A character object mimicking Alliance Auth's EveCharacter,
    but with internal standings tool data instead.
    """

    corporation_ticker = None  # Not implemented

    user = None

    def __init__(self, character_id):
        from standingsrequests.models import CharacterAffiliation

        self.character_id = int(character_id)
        self.alliance_name = None
        try:
            assoc = CharacterAffiliation.objects.select_related(
                "character", "corporation", "alliance"
            ).get(character_id=self.character_id)
        except CharacterAffiliation.DoesNotExist:
            assoc = None
            self.corporation_id = None
            self.corporation_name = None
            self.alliance_id = None
        else:
            self.corporation_id = assoc.corporation_id
            self.alliance_id = assoc.alliance_id

        self.character_name = (
            assoc.character.name if assoc and assoc.character else None
        )
        self.corporation_name = (
            assoc.corporation.name if assoc and assoc.corporation else None
        )
        self.alliance_name = assoc.alliance.name if assoc and assoc.alliance else None

    def portrait_url(self, size: int = DEFAULT_IMAGE_SIZE) -> str:
        return eveimageserver.character_portrait_url(self.character_id, size)


def has_required_scopes_for_request(
    character: EveCharacter, user: Optional[User] = None, quick_check: bool = False
) -> bool:
    """Report whether character has the required scopes
    for issuing a standings request.

    Params:
    - user: provide User object to shorten processing time
    - quick_check: if True will not check if tokens are valid to save time
    """
    if not user:
        try:
            ownership = CharacterOwnership.objects.select_related(
                "user", "user__profile__state"
            ).get(character__character_id=character.character_id)
        except CharacterOwnership.DoesNotExist:
            return False

        user = ownership.user

    try:
        state_name = user.profile.state.name
    except ObjectDoesNotExist:
        return False

    scopes_string = " ".join(app_config.required_scopes_for_state(state_name))
    token_qs = Token.objects.filter(character_id=character.character_id).require_scopes(
        scopes_string
    )

    if not quick_check:
        token_qs = token_qs.require_valid()

    result = token_qs.exists()
    return result
