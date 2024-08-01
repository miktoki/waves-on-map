#!/bin/bash

URL="https://api.met.no/weatherapi/oceanforecast/2.0/complete"
AGENT=mbolger/1.0
DST=ocean_data.json
LAT=59.861046
LON=10.751105
wget --header="User-Agent: ${AGENT}" "${URL}?lat=${LAT}&lon=${LON}" -O $DST