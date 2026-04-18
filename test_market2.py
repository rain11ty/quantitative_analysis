# -*- coding: utf-8 -*-
from app.services.market_overview_service import MarketOverviewService

res = MarketOverviewService.get_market_overview()
print(f"Number of items: {len(res['items'])}")
for item in res['items']:
    print(item['ts_code'], item['name'], item['error'])
