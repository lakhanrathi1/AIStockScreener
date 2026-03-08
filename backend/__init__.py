"""
Backend package for the AI Indian Stock Mover MVP.

Modules:
- config: environment configuration helpers
- nse_client: functions to fetch NSE data and compute movers
- news_client: fetches related news for stocks
- reason_engine: generates human-readable reasons for stock moves
- firebase_client: writes processed data into Firestore
- run_daily_job: orchestration entrypoint for the scheduled job
"""

