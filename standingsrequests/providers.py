from esi.clients import EsiClientProvider

from standingsrequests import __version__

esi = EsiClientProvider(app_info_text=f"aa-standingsrequests v{__version__}")
