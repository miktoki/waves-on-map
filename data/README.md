Downloaded Norge-L.topojson and Kommuner-L.topojson from https://github.com/robhop/fylker-og-kommuner/blob/main/


```bash
# instal cli command to get subset of topojson
npm install -g mapshaper

# get subset of topojson based on filter
mapshaper /home/mikaelt/Documents/unsinn/weather/data/Kommuner-L.topojson \
  -filter 'name === "Oslo" || name === "Nesodden"' \
  -o /home/mikaelt/Documents/unsinn/weather/data/Kommuner-L-Oslo-Nesodden.topojson
```
