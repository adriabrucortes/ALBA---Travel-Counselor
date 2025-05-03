class City:
    def __init__(self, name: str, cost_of_living: float = 0.0, location: str = '', attractions: dict = None):
        self._name = name
        self._cost_of_living = cost_of_living
        self._location = location
        self._attractions = attractions or {}

    # Getter and Setter for name
    @property
    def name(self) -> float:
        return self.name

    @name.setter
    def name(self, value: float):
        self._name = value

    # Getter and Setter for cost_of_living
    @property
    def cost_of_living(self) -> float:
        return self._cost_of_living

    @cost_of_living.setter
    def cost_of_living(self, value: float):
        self._cost_of_living = value

    # Getter and Setter for location
    @property
    def location(self) -> str:
        return self._location

    @location.setter
    def location(self, value: str):
        self._location = value

    # Getter and Setter for attractions
    @property
    def attractions(self) -> dict:
        return self._attractions

    @attractions.setter
    def attractions(self, value: dict):
        self._attractions = value