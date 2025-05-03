from src.attraction import Attraction
from src.city import City
from src.flight import Flight
from src.traveller import Traveller

def get_cheapest_flight(origin, destination):
    # todo
    return Flight(origin, destination, 200, 3.5, 15.0)

def average_score(travellers: list, city):
    total_score = 0.0
    for traveller in travellers:
        flight = get_cheapest_flight(traveller.home_destination, city.location)
        total_score += traveller.score_city(flight, city)
    return total_score / len(travellers)


### Test data:
preferences = { # from 0 to 1 -> scored using prompt engineering
    # SUM to 1
    Attraction.HISTORICAL: 0.7,
    Attraction.ENTERTAINMENT: 0,
    Attraction.FOOD: 0,
    Attraction.SHOPPING: 0.3,
    Attraction.PARKS: 0,
    Attraction.ARTS: 0,
    Attraction.ADVENTURE: 0,
    Attraction.WELLNESS: 0
}

city_attractions = { # from 0 to 1 -> calculated from database
    # SUM to 1
    Attraction.HISTORICAL: 0.7,
    Attraction.ENTERTAINMENT: 0,
    Attraction.FOOD: 0,
    Attraction.SHOPPING: 0.3,
    Attraction.PARKS: 0,
    Attraction.ARTS: 0,
    Attraction.ADVENTURE: 0,
    Attraction.WELLNESS: 0
}

if __name__ == "__main__":
    test_city = City('Athens', 100, '1234', city_attractions)
    test_traveller = Traveller('Lucía', 500, preferences, 'Madrid', '1234')
    test_flight = Flight('Madrid', 'Athens', 150, 3.5, 0.5)
    print(
        test_traveller.score_city(test_city, test_flight)
    )