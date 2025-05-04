import requests
from pydantic import BaseModel, ValidationError

indicative_flight_endpoint = "https://partners.api.skyscanner.net/apiservices/v3/flights/indicative/search"

class MinPrice(BaseModel):
    amount: str


class FlightData(BaseModel):
    minPrice: MinPrice


def create_payload(origin_iata: str, destination_iata: str, date_range: dict, currency: str, market: str):
    return {
        "query": {
            "currency": "%s" % currency,
            "locale": "en-GB",
            "market": "%s" % market,
            "queryLegs": [
                { # outbound
                    "originPlace": {
                        "queryPlace": {
                            "iata": "%s" % origin_iata
                        }
                    },
                    "destinationPlace": {
                        "queryPlace": {
                            "iata": "%s" % destination_iata
                        }
                    },
                    "date_range": {
                        "startDate": {
                            "year": date_range['start_year'],
                            "month": date_range['start_month']
                        },
                        "endDate": {
                            "year": date_range['start_year'],
                            "month": date_range['start_month']
                        }
                    }
                },
                { # return
                    "originPlace": {
                        "queryPlace": {
                            "iata": "%s" % destination_iata
                        }
                    },
                    "destinationPlace": {
                        "queryPlace": {
                            "iata": "%s" % origin_iata
                        }
                    },
                    "date_range": {
                        "startDate": {
                            "year": date_range['end_year'],
                            "month": date_range['end_month']
                        },
                        "endDate": {
                            "year": date_range['end_year'],
                            "month": date_range['end_month']
                        }
                    }
                }
            ]
        }
    }


def send_request(origin_iata: str, destination_iata: str, date_range: dict, currency: str, market: str, api_key: str):
    headers = { "x-api-key": api_key }

    # Create the request payload
    payload = create_payload(origin_iata, destination_iata, date_range, currency, market)

    try:
        # Send the POST request
        response = requests.post(indicative_flight_endpoint, headers=headers, json=payload)

        # Check if the response is successful (status code 200)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Request failed with status code {response.status_code}")
            print(response.text)
            return None
    except requests.exceptions.RequestException as e:
        print("An error occurred while making the request")
        return None


def get_lowest_price(raw_response): # returns -1 if no flights
    quotes = raw_response['content']['results']['quotes']
    prices = []

    for quote, content in quotes.items():
        try:
            parsed_data = FlightData.model_validate(content)
            price = parsed_data.minPrice.amount
            prices.append(price)
        except ValidationError as e:
            print("Validation Error:", e)

    if len(prices) == 0:
        return 1000000000
    else:
        return min(prices)


# gemini gives us iatas and date range
def search_cheapest_flights(origin_iata: str, destination_iata: str, date_range: dict, api_key: str):
    resp = send_request(origin_iata, destination_iata, date_range, "EUR", "ES", api_key)
    if resp:
        return get_lowest_price(resp)
    else:
        return 10000000000


if __name__ == "__main__":
    origin_iata = "CPT"
    destination_iata = "BCN"
    date_range = {"start_month": 8, "start_year": 2025, "end_month": 9, "end_year": 2025}
    cheapest = search_cheapest_flights(origin_iata, destination_iata, date_range)

    print(cheapest)
