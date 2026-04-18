# -*- coding: utf-8 -*-
from app.services.market_overview_service import MarketOverviewService
import pprint

res = MarketOverviewService.get_market_overview()
pprint.pprint(res)
