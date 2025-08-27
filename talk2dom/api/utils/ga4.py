# ga4.py
import os
import time
import uuid
import requests
from loguru import logger

GA4_MEASUREMENT_ID = os.getenv("GA4_MEASUREMENT_ID")  # G-XXXXXXX
GA4_API_SECRET = os.getenv("GA4_API_SECRET")
GA4_COLLECT = "https://www.google-analytics.com/mp/collect"
GA4_DEBUG = "https://www.google-analytics.com/debug/mp"


class GA4:
    def __init__(self, measurement_id=None, api_secret=None, debug=False, timeout=5):
        self.mid = measurement_id or GA4_MEASUREMENT_ID
        self.secret = api_secret or GA4_API_SECRET
        self.debug = debug
        self.timeout = timeout

    def send(
        self,
        user_id: str,
        events: list[dict],  # [{"name":..., "params": {...}, "event_id": "..."}]
        user_properties: dict | None = None,
        timestamp_micros: int | None = None,
        non_personalized_ads: bool = False,
    ):
        if not self.mid or not self.secret:
            logger.warning("Please set GA4_API_SECRET and GA4_MEASUREMENT_ID")
            return
        payload = {
            "user_id": str(user_id),
            "timestamp_micros": timestamp_micros or int(time.time() * 1_000_000),
            "non_personalized_ads": non_personalized_ads,
            "events": [],
        }
        if user_properties:
            payload["user_properties"] = {
                k: {"value": v} for k, v in user_properties.items()
            }
        # 组装事件，补齐必需字段
        for e in events:
            name = e["name"]
            params = dict(e.get("params") or {})
            params.setdefault("engagement_time_msec", 1)
            event_id = e.get("event_id") or str(uuid.uuid4())
            payload["events"].append(
                {"name": name, "params": params, "event_id": event_id}
            )

        endpoint = GA4_DEBUG if self.debug else GA4_COLLECT
        resp = requests.post(
            endpoint,
            params={"measurement_id": self.mid, "api_secret": self.secret},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json() if self.debug else {"status": "ok"}
