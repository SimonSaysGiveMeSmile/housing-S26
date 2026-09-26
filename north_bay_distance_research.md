# SF distance comparison and North Bay research — September 25, 2026

The comparison point is the San Francisco Ferry Building. The user requested distance to “SF / aby”; the second term remains unclear, so downtown SF is the stated default.

## Distance method

`distance_estimates.json` contains approximate driving miles from each city center to the Ferry Building. City points came from OpenStreetMap/Nominatim; the OSRM driving table returned road distances for its fastest modeled routes. Distances are rounded to whole miles for display. They are not exact property-to-door mileage or live traffic estimates. Several listings do not give an exact address, and neighborhood offsets can be material.

The one-time geocoding lookup used a single thread, identifying user agent, caching, and at least 1.1 seconds between requests in accordance with the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/). No public geocoding service is embedded in the website. Map attribution is displayed on the page. [OSRM API documentation](https://project-osrm.org/docs/v5.24.0/api/) describes the driving table distances.

| Area | Approx. driving miles to SF Ferry Building |
| --- | ---: |
| Oakland | 10 |
| Millbrae | 17 |
| San Rafael | 19 |
| Hayward | 25 |
| Novato | 29 |
| Concord | 29 |
| Palo Alto | 34 |
| Newark | 35 |
| Petaluma | 40 |
| Sunnyvale | 42 |
| Livermore | 43 |
| Antioch | 43 |
| Milpitas | 44 |
| Fairfield | 46 |
| Rohnert Park | 49 |
| Brentwood | 53 |
| Vacaville | 53 |

All existing cards now carry a city, region, distance, and a Google Maps driving link. Default sorting is closest to SF. North of SF means Marin/Sonoma; Solano has a separate northeast-Bay filter. Existing unavailable/unverified listings remain excluded by default. The North of SF preset explicitly includes unverified backups while excluding unavailable posts.

## North Bay findings

- Existing [San Rafael / China Camp Craigslist lead](https://www.craigslist.org/view/d/san-rafael-br-private-bath-for-one/3Pi2NykzWn3KsMp3AxBjEk): $1,325 including advertised utilities, private bathroom, unfurnished, off-street parking. Monthly lease and September 29 need confirmation. Original URL returned HTTP 200 on this pass. The city-center distance underestimates or overestimates the actual trip depending on the exact address; no precise property commute is claimed.
- Added [southern Novato Furnished Finder room](https://www.furnishedfinder.com/property/306547_1): $1,200 including utilities, furnished, private bathroom, onsite parking, one-month minimum. $100 cleaning and $400 refundable deposit. **Calendar December 10, 2025**, so this is an unverified backup, not current confirmed inventory. Three advertiser photos added.
- [San Rafael SpareRoom $1,250](https://www.spareroom.com/rooms-for-rent/marin_county/san_rafael/102960541): not accepting applications; excluded.
- [San Rafael Furnished Finder $1,400](https://www.furnishedfinder.com/property/989838_1): shared bathroom and 12-month minimum; excluded.
- [San Anselmo $1,450](https://www.furnishedfinder.com/property/842080_1): shared bathroom, three-month minimum, December start; excluded.
- [Petaluma garden suite $1,400](https://www.furnishedfinder.com/property/403908_1): private bath and one-month minimum, but November 30 availability; excluded for dates.
- [Petaluma room 615224_1](https://www.furnishedfinder.com/property/615224_1): latest page says October 31; description adds $200 utilities to $1,300 rent despite an included-utilities badge. Too late for the requested start.
- [Rohnert Park $1,300 casita](https://www.furnishedfinder.com/property/859869_1): September 30 but three-month minimum; excluded for lease length.
- [Rohnert Park $1,200 master room](https://www.furnishedfinder.com/property/1018164_1): promising public search title, but detail access failed. No verified lease terms; not added as a match.

No host has confirmed September 29 and no messages were sent. The practical North Bay priority remains San Rafael first, then verify the older Novato lead before relying on it.
