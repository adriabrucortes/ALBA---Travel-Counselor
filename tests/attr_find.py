from typing import Dict, List

def get_traveler_preference_attributes(traveler_class):
    """
    Returns a list of preference attribute names from the Traveler class,
    excluding those that start with an underscore.
    """
    preference_attributes = []
    temp_traveler = traveler_class(_user_id=0, _username="")
    excluded_attributes = ['user_id', 'username', 'conversation_history', 'done'] # These were without underscores in previous iterations
    for attr_name in temp_traveler.__dict__:
        if not attr_name.startswith('_') and attr_name not in excluded_attributes and not callable(getattr(temp_traveler, attr_name)):
            preference_attributes.append(attr_name)
    return preference_attributes

class Traveler:
    def __init__(self, _user_id: int, _username: str):
        self._user_id = _user_id
        self._username = _username
        self.cheap: int = None
        self.history: int = None
        self.environmental_impact: int = None
        self.food: int = None
        self.deal_breakers: List[str] = []
        self.deal_makers: List[str] = []
        self._conversation_history: List[Dict[str, str]] = []
        self._done: bool = False

    def __str__(self):
        output = f"{self._username}:\n"
        if self.cheap is not None:
            output += f" cheap, {self.cheap}\n"
        if self.history is not None:
            output += f" history, {self.history}\n"
        if self.environmental_impact is not None:
            output += f" environmental_impact, {self.environmental_impact}\n"
        if self.food is not None:
            output += f" food, {self.food}\n"
        if self.deal_breakers:
            output += f" DEAL_BREAKERS: {', '.join(self.deal_breakers)}.\n"
        if self.deal_makers:
            output += f" DEAL_MAKERS: {', '.join(self.deal_makers)}.\n"
        return output.strip()
    
print(get_traveler_preference_attributes(Traveler))