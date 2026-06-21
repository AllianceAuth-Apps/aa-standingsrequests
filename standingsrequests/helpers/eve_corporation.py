from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Optional

from django.contrib.auth.models import User
from django.core.cache import cache
from esi.exceptions import HTTPError
from eveuniverse.models import EveEntity

from allianceauth.eveonline.evelinks import eveimageserver
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from standingsrequests import __title__
from standingsrequests.constants import DEFAULT_IMAGE_SIZE
from standingsrequests.helpers import eve_character
from standingsrequests.providers import esi

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

MAX_WORKERS = 10


class EveCorporationHelper:
    CACHE_PREFIX = "STANDINGS_REQUESTS_EVECORPORATION_"
    CACHE_TIME = 60 * 60  # 60 minutes

    def __init__(self, **kwargs):
        self.corporation_id = int(kwargs.get("corporation_id", 0))
        self.corporation_name = kwargs.get("corporation_name")
        self.ticker = kwargs.get("ticker")
        self.member_count = kwargs.get("member_count")
        self.ceo_id = kwargs.get("ceo_id")
        self.alliance_id = kwargs.get("alliance_id")
        self.alliance_name = kwargs.get("alliance_name")

    def __str__(self):
        return self.corporation_name

    def __eq__(self, o: "EveCorporationHelper") -> bool:
        return (
            isinstance(o, type(self))
            and self.corporation_id == o.corporation_id
            and self.corporation_name == o.corporation_name
            and self.ticker == o.ticker
            and self.member_count == o.member_count
            and self.ceo_id == o.ceo_id
            and self.alliance_id == o.alliance_id
            and self.alliance_name == o.alliance_name
        )

    @property
    def is_npc(self) -> bool:
        """returns true if this corporation is an NPC, else false"""
        return self.corporation_is_npc(self.corporation_id)

    @staticmethod
    def corporation_is_npc(corporation_id: int) -> bool:
        """returns true if this corporation is an NPC, else false"""
        return 1000000 <= corporation_id <= 2000000

    def logo_url(self, size: int = DEFAULT_IMAGE_SIZE) -> str:
        return eveimageserver.corporation_logo_url(self.corporation_id, size)

    def member_tokens_count_for_user(
        self, user: User, quick_check: bool = False
    ) -> int:
        """returns the number of character tokens the given user owns
        for this corporation

        Params:
        - user: user owning the characters
        - quick: if True will not check if tokens are valid to save time
        """
        corporation_members = (
            EveCharacter.objects.filter(character_ownership__user=user)
            .select_related("character_ownership__user__profile__state")
            .filter(corporation_id=self.corporation_id)
        )

        return sum(
            (
                1
                if eve_character.has_required_scopes_for_request(
                    character=character, user=user, quick_check=quick_check
                )
                else 0
            )
            for character in corporation_members
        )

    def user_has_all_member_tokens(self, user: User, quick_check: bool = False) -> bool:
        """Report whether a user owns same amount of tokens as there are
        member characters in this corporation

        Params:
        - user: user owning the characters
        - quick: if True will not check if tokens are valid to save time
        """
        if not self.member_count:
            return False

        valid_count = self.member_tokens_count_for_user(
            user=user, quick_check=quick_check
        )
        has_all_tokens = valid_count >= self.member_count
        return has_all_tokens

    @classmethod
    def get_by_id(
        cls, corporation_id: int, ignore_cache: bool = False
    ) -> Optional["EveCorporationHelper"]:
        """Get a corporation from the cache or ESI if not cached
        Corps are cached for 3 hours

        Params
        - corporation_id: int corporation ID to get
        - ignore_cache: when true will always get fresh from API

        Returns corporation object or None
        """
        logger.debug("Getting corporation by id %d", corporation_id)
        my_cache_key = cls._get_cache_key(corporation_id)
        corporation = cache.get(my_cache_key)
        if corporation is None or ignore_cache:
            logger.debug("Corp not in cache or ignoring cache, fetching")
            corporation = cls.fetch_corporation_from_api(corporation_id)
            if corporation is not None:
                cache.set(my_cache_key, corporation, cls.CACHE_TIME)
        else:
            logger.debug("Retrieving corporation %s from cache", corporation_id)
        return corporation

    @classmethod
    def _get_cache_key(cls, corporation_id: int) -> str:
        return cls.CACHE_PREFIX + str(corporation_id)

    @classmethod
    def fetch_corporation_from_api(
        cls, corporation_id: int
    ) -> Optional["EveCorporationHelper"]:
        logger.debug(
            "Attempting to fetch corporation from ESI with id %s", corporation_id
        )
        try:
            obj = esi.client.Corporation.GetCorporationsCorporationId(
                corporation_id=corporation_id
            ).result(use_etag=False)
        except HTTPError:
            logger.exception(
                "Failed to fetch corporation from ESI with id %i", corporation_id
            )
            return None

        args = {
            "corporation_id": corporation_id,
            "corporation_name": obj.name,
            "ticker": obj.ticker,
            "member_count": obj.member_count,
            "ceo_id": obj.ceo_id,
        }
        if obj.alliance_id:
            args["alliance_id"] = obj.alliance_id
            args["alliance_name"] = EveEntity.objects.resolve_name(obj.alliance_id)

        return cls(**args)

    @classmethod
    def get_many_by_id(
        cls, corporation_ids: Iterable[int]
    ) -> List["EveCorporationHelper"]:
        """Returns multiple corporations by ID

        Fetches requested corporations from cache or API as needed.
        Uses threads to fetch them in parallel.
        """
        corporation_ids_unique = set(corporation_ids)
        if not corporation_ids_unique:
            return []

        # make sure client is loaded before starting threads
        esi.client.Status.GetStatus().result(use_etag=False)
        logger.info(
            "Starting to fetch the %d corporations from ESI with up to %d workers",
            len(corporation_ids_unique),
            MAX_WORKERS,
        )
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(cls.get_by_id, corporation_id)
                for corporation_id in corporation_ids_unique
            ]
            logger.info("Waiting for all threads fetching corporations to complete...")

        logger.info(
            "Completed fetching %d corporations from ESI", len(corporation_ids_unique)
        )
        results_raw = (f.result() for f in futures)
        results = [obj for obj in results_raw if obj is not None]
        return results


def user_can_request_corporation_standing(user: User, corporation_id: int) -> bool:
    """
    Report whether user is permitted to request standing for a corporation.

    A user must own all of the required corp tokens to be permitted to request standing.

    Params
    - corporation_id: corp to check for
    - user: User to check for

    returns True if they can request standings, False if they cannot
    """
    corporation = EveCorporationHelper.get_by_id(corporation_id)
    is_permitted = (
        corporation is not None
        and not corporation.is_npc
        and corporation.user_has_all_member_tokens(user)
    )
    return is_permitted
