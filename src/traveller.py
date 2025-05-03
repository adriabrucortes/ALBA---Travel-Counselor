from src.city import City
from src.flight import Flight


class Traveller:
    def __init__(self, name: str = None, budget: int = 0, interests: dict = None,
                 home_destination: str = '', home_coordinates: str = '', languages: list = None, ):
        self.name = name
        self._budget = budget
        self._languages = languages or []
        self._interests = interests or {}
        self._home_destination = home_destination
        self._home_coordinates = home_coordinates

    # Getter and Setter for budget
    @property
    def budget(self) -> int:
        return self._budget

    @budget.setter
    def budget(self, value: int):
        self._budget = value

    # Getter and Setter for languages
    @property
    def languages(self) -> list:
        return self._languages

    @languages.setter
    def languages(self, value: list):
        self._languages = value

    # Getter and Setter for interests
    @property
    def interests(self) -> dict:
        return self._interests

    @interests.setter
    def interests(self, value: dict):
        total = sum(list(value.values()))
        normalized = {k: v/total for k, v in value.items()}
        self._interests = normalized

    # Getter and Setter for home_destination
    @property
    def home_destination(self) -> str:
        return self._home_destination

    @home_destination.setter
    def home_destination(self, value: str):
        self._home_destination = value

    # Getter and Setter for home_coordinates
    @property
    def home_coordinates(self) -> str:
        return self._home_coordinates

    @home_coordinates.setter
    def home_coordinates(self, value: str):
        self._home_coordinates = value

    # Scoring based on profile
    def score_cost(self, city: City, flight: Flight):
        return (city.cost_of_living + flight.cost)/self.budget # cost_of_living * days????

    def score_attractions(self, city: City):
        total = 0
        for attraction, rating in city.attractions.items():
            total += self.interests[attraction] * rating # normalized?? ranking??
        return total

    def score_city(self, city: City, flight: Flight):
        weights = [0.8, 0.1, 0.1] # dynamic? static for now
        cost = 1 - self.score_cost(city, flight) # max = 1 - minimize
        attractions = self.score_attractions(city) # max
        footprint = 1 - flight.carbon_footprint # max

        # full cost function for this traveller
        return weights[0]*cost + weights[1]*attractions + weights[2]*footprint
