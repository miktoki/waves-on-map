import math
import sys
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from date_utils import to_oslo

############################################################
# Oceanforecast - Ocean forecasts for points at sea in Northwestern Europe
# Delivers wave and sea forecast in standard MET Forecast GeoJSON format.

# The forecast is based on multiple wave and sea models. For more information on models and parameters, see the Oceanforecast data model documentation.

# Requests outside the model area will get a 422 response. For requests inside the model but on land away from the coast, you will get a GeoJSON document with an error message. For requests near the coast, the system will "snap" to the nearest ocean point so that the coordinates in the GeoJSON might be different from the URL.
# Wave direction

# Version 0.9 followed oceanographic convention instead of meteorological convention, meaning that the value indicates where the waves are moving, not where they are coming from.

# In the 2.0 JSON version, this is now changed to the more common meteorological convention for waves, while currents still use oceanographic convention. This is indicated in the variable names, sea_surface_wave_from_direction and sea_water_to_direction.

############################################################
# Locationforecast - Weather forecast for a specified place
# DESCRIPTION

# This service delivers a full weather forecast for one location, that is, a forecast with several parameters for a nine-day period.
# JSON format and variables

# Version 2.0 defaults to JSON format for data. For an explanation of the various variables, see the Datamodel documentation. The JSON format is described in the General Forecast Format documentation.
# XML format

# For those who want to continue using their existing clients with a minimum of changes, you can also continue using the old XML format. This must be accessed via the classic method, like this:

#     https://api.met.no/weatherapi/locationforecast/2.0/classic?lat=59.93&lon=10.72&altitude=90

# Note that the msi parameter is now called altitude in 2.0.

# The XML format is considered legacy, and as similar to 1.9 as possible except for additional time periods and the XML Schema URI. Future enhancements will primarily be added to the JSON format.

# Also, some elements will be removed when version 1.9 is terminated, including the following elements:

#     <temperatureProbability unit="probabilitycode" value="0"/>
#     <windProbability unit="probabilitycode" value="0"/>
#     <symbolProbability unit="probabilitycode" value="1"/>

# Weather icons

# Along with the new JSON format we also have a new set of weather icons, in PNG, SVG and PDF formats. They can be downloaded from GitHub.

# The filename (minus extension) corresponds to the symbol_code in the JSON format, including variations for day, night and polar day. This means there is no need for calculations or fetching data from the Sunrise service in order to present the correct weather icons. This has also been added to the XML as an attribute code to the symbol element:

#     <symbol id="PartlyCloud" number="3" code="partlycloudy_day"></symbol>

# Note: There is a typing error in lightssleetshowersandthunder and lightssnowshowersandthunder (extra "s" after "light"). Unfortunately, correcting this would mean breaking existing applications, so it has been postponed to the next version of weathericon/locationforecast.
# Wind symbols

# Wind direction denote where the wind is coming from, where 0° is north, 90° east, etc. For GUI applications use we suggest using arrows, like these:

# ⬇   0° (north)
# ⬅  90° (east)
# ⬆ 180° (south)
# ➡ 270° (west)

# UV index
# The new format also includes UV radiation forecasts per location, to replace the old graphical UVforecast product. For those wanting UV maps these can be downloaded directly from CAMS.
############################################################


def fromisoformat_z(dt_str: str) -> datetime:
    """Parse ISO 8601 datetime string ending in 'Z'"""
    # this is not necessary in Python 3.11+
    if sys.version_info >= (3, 11):
        return datetime.fromisoformat(dt_str)
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(f"{dt_str[:-1]}+00:00")
    return datetime.fromisoformat(dt_str)


class Geometry(BaseModel):
    type: str
    coordinates: list[float]


class WaveUnits(BaseModel):
    sea_surface_wave_from_direction: str
    sea_surface_wave_height: str
    sea_water_speed: str
    sea_water_temperature: str
    sea_water_to_direction: str


class WeatherUnits(BaseModel):
    air_pressure_at_sea_level: str
    air_temperature: str
    cloud_area_fraction: str
    relative_humidity: str
    wind_from_direction: str
    wind_speed: str
    precipitation_amount: str


class WeatherMeta(BaseModel):
    updated_at: datetime
    units: WeatherUnits


class WaveMeta(BaseModel):
    updated_at: datetime
    units: WaveUnits


class WeatherData(BaseModel):
    air_pressure_at_sea_level: float
    air_temperature: float
    cloud_area_fraction: float
    relative_humidity: float
    wind_from_direction: float
    wind_speed: float
    precipitation_amount: float
    symbol_code: str | None = None
    time: datetime
    time_window: Literal["1h", "6h", "12h"]

    @model_validator(mode="before")
    def flatten_data(cls, values):
        instant = values["data"]["instant"]["details"]
        if "air_temperature" not in instant:
            raise ValueError("Invalid data for WeatherData")
        time = fromisoformat_z(values["time"])
        time_window = (
            "1h"
            if "next_1_hours" in values["data"]
            else "6h"
            if "next_6_hours" in values["data"]
            else "12h"
        )
        next_hours = values["data"].get(
            "next_1_hours",
            values["data"].get(
                "next_6_hours", values["data"].get("next_12_hours", None)
            ),
        )

        return {
            "time": time,
            "air_pressure_at_sea_level": instant["air_pressure_at_sea_level"],
            "air_temperature": instant["air_temperature"],
            "cloud_area_fraction": instant["cloud_area_fraction"],
            "relative_humidity": instant["relative_humidity"],
            "wind_from_direction": instant["wind_from_direction"],
            "wind_speed": instant["wind_speed"],
            "precipitation_amount": (
                next_hours["details"]["precipitation_amount"]
                if next_hours is not None and "details" in next_hours
                else math.nan
            ),
            "symbol_code": (
                next_hours["summary"]["symbol_code"] if next_hours is not None else None
            ),
            "time_window": time_window,
        }


class WaveData(BaseModel):
    sea_surface_wave_from_direction: float
    sea_surface_wave_height: float
    sea_water_speed: float
    sea_water_temperature: float
    sea_water_to_direction: float
    time: datetime

    @model_validator(mode="before")
    def flatten_data(cls, values):
        instant = values["data"]["instant"]["details"]
        if "sea_surface_wave_height" not in instant:
            raise ValueError("Invalid data for WaveData")

        time = fromisoformat_z(values["time"].replace("Z", "+00:00"))
        return {
            "time": time,
            "sea_surface_wave_from_direction": instant[
                "sea_surface_wave_from_direction"
            ],
            "sea_surface_wave_height": instant["sea_surface_wave_height"],
            "sea_water_speed": instant["sea_water_speed"],
            "sea_water_temperature": instant["sea_water_temperature"],
            "sea_water_to_direction": instant["sea_water_to_direction"],
        }

    @property
    def compact(self):
        return {
            key.replace("sea_", "").replace("surface_", "").replace("water_", ""): value
            for key, value in self.model_dump().items()
        }

    @property
    def local_compact(self):
        ret = self.compact
        ret["time"] = to_oslo(self.time)
        return ret


class WeatherProps(BaseModel):
    meta: WeatherMeta
    timeseries: list[WeatherData]


class WeatherInfo(BaseModel):
    type: str  # = Field(alias="type")
    geometry: Geometry
    properties: WeatherProps

    @property
    def data(self):
        return self.properties.timeseries

    @property
    def meta(self):
        return self.properties.meta

    # @property
    # def sample_time(self):
    #     return [ts.time for ts in self.properties.timeseries]


class WaveProps(WeatherProps):
    meta: WaveMeta
    timeseries: list[WaveData]


class WaveInfo(BaseModel):
    type: str  # = Field(alias="type")
    geometry: Geometry
    properties: WaveProps

    @property
    def data(self):
        return self.properties.timeseries

    @property
    def meta(self):
        return self.properties.meta

    # @property
    # def sample_time(self):
    #     return [ts.time for ts in self.properties.timeseries]
