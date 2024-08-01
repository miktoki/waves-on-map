import logging
import os
from typing import Literal

import requests

from waves_on_map.models import WaveInfo, WeatherInfo

LOG_LEVEL = os.getenv("MET_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("met_fetch")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
try:
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
except Exception:  # pragma: no cover
    logger.setLevel(logging.INFO)


def fetch_met_weather(
    lat: float,
    lon: float,
    source: Literal["oceanforecast", "locationforecast"],
    variant: Literal["complete", "compact"],
    version="2.0",
):
    url = f"https://api.met.no/weatherapi/{source}/{version}/{variant}?lat={lat}&lon={lon}"
    logger.debug(
        "fetch_met_weather start src=%s variant=%s lat=%.5f lon=%.5f url=%s",
        source,
        variant,
        lat,
        lon,
        url,
    )
    resp = requests.get(url, headers={"User-Agent": "mbolger/1.0"})
    logger.debug(
        "fetch_met_weather done status=%s ok=%s size=%sB",
        resp.status_code,
        resp.ok,
        len(resp.content or b""),
    )
    if resp.ok:
        info_cls = WeatherInfo if source == "locationforecast" else WaveInfo
        try:
            data = resp.json()
        except Exception as e:  # pragma: no cover
            logger.warning(
                "fetch_met_weather json decode error src=%s status=%s err=%s snippet=%r",
                source,
                resp.status_code,
                e,
                resp.text[:160],
            )
            raise
        logger.debug(
            "fetch_met_weather parse_success class=%s keys=%s",
            info_cls.__name__,
            list(data.keys())[:8],
        )
        return info_cls(**data)
    else:
        logger.warning(
            "fetch_met_weather failure status=%s reason=%s snippet=%r",
            resp.status_code,
            resp.reason,
            resp.text[:200],
        )
        raise Exception(f"{resp.status_code} {resp.reason}")


def fetch_waves(lat: float, lon: float) -> WaveInfo:
    # with open("ocean_data_minimal.json", "r") as f:
    #     data = json.load(f)
    # print("DATA:::\n", json.dumps(data, indent=4))
    # return WaveInfo(**data)
    return fetch_met_weather(lat, lon, "oceanforecast", "complete")  # type: ignore


def fetch_forecast(lat, lon) -> WeatherInfo:
    return fetch_met_weather(lat, lon, "locationforecast", "compact")  # type: ignore


if __name__ == "__main__":
    lat = 59.8739721
    lon = 10.7449325
    wi = fetch_forecast(lat, lon)

    print(wi.sample_time)
