class Flight:
    def __init__(self, origin, destination, cost: float = 0.0, duration: float = 0.0, carbon_footprint: float = 0.0):
        self._origin = origin
        self._destination = destination
        self._cost = cost
        self._duration = duration
        self._carbon_footprint = carbon_footprint

    # Getter and Setter for cost
    @property
    def cost(self) -> float:
        return self._cost

    @cost.setter
    def cost(self, value: float):
        self._cost = value

    # Getter and Setter for duration
    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, value: float):
        self._duration = value

    # Getter and Setter for carbon_footprint
    @property
    def carbon_footprint(self) -> float:
        return self._carbon_footprint

    @carbon_footprint.setter
    def carbon_footprint(self, value: float):
        self._carbon_footprint = value