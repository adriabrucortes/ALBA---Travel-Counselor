import discord
from google import genai
import asyncio
import re
from typing import Dict, List

PROMPT_FILENAME = "prompt.txt"

DISCORD_BOT_TOKEN = 'MTM2Nzk5NDA0OTA1OTA5ODcxNw.G-sm5x.bc3Lvyk6Z1gwZD30UwhiMpgBH0erhdF3XM_-7M'
GEMINI_API_KEY = 'AIzaSyBXKpZrBkFrXZNDoLCIaW-n5mY5AqauXcE'

genai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
discord_client = discord.Client(intents=intents)

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

travelers: Dict[int, Traveler] = {}
users_to_ask: List[int] = []
chats: Dict[int, genai.chats.Chat] = {}
trip_started: bool = False
start_trip_message: discord.Message = None

def get_traveler_preference_attributes(traveler_class):
    """
    Returns a list of preference attribute names from the Traveler class,
    excluding those that start with an underscore.
    """
    preference_attributes = []
    temp_traveler = traveler_class(_user_id=0, _username="")
    excluded_attributes = ['deal_breakers', 'deal_makers']
    for attr_name in temp_traveler.__dict__:
        if not attr_name.startswith('_') and attr_name not in excluded_attributes and not callable(getattr(temp_traveler, attr_name)):
            preference_attributes.append(attr_name)
    return preference_attributes

async def generate_prompt(chat_session: genai.chats.Chat, prompt: str) -> str:
    try:
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating question: {e}")
        return "Sorry, I couldn't generate a question right now."

async def first_prompt(chat_session: genai.chats.Chat, file_path: str):
    try:
        with open(file_path, 'r') as file:
            initial_prompt_content = file.read()
    except FileNotFoundError:
        await generate_prompt(chat_session, f"Error: File not found at '{file_path}'")
        return

    preference_attributes = get_traveler_preference_attributes(Traveler)

    aspects_text = "Aspects:\n"
    for attr in preference_attributes:
        aspects_text += f"- {attr}\n"

    full_prompt = f"{initial_prompt_content}\n\n{aspects_text}\n\n"
    
    await generate_prompt(chat_session, full_prompt)

    sentences = [s.strip() + '.' for s in initial_prompt_content.split('.') if s.strip()]

    await generate_prompt(chat_session, "I'm going to send you a series of instructions you need to understand and you must not reply until I say GO!")

    for sentence in sentences:
        await generate_prompt(chat_session, sentence)


def parse_single_preference(ai_output: str) -> Dict[str, any]:
    #data = {}
    lines = ai_output.strip().split("\n")
    #username_line = lines[0].strip().rstrip(":")
    user_data = {}
    deal_breakers = None
    deal_makers = None
    for line in lines[1:]:
        line = line.strip()
        if line.startswith("DEAL_BREAKERS:"):
            deal_breakers_text = line.split(":", 1)[1].strip()
            deal_breakers = [deal_breakers_text]
        elif line.startswith("DEAL_MAKERS:"):
            deal_makers_text = line.split(":", 1)[1].strip()
            deal_makers = [deal_makers_text]
        elif "," in line and not line.startswith("DEAL_BREAKERS:") and not line.startswith("DEAL_MAKERS:"):
            aspect, value = map(str.strip, line.split(','))
            user_data[aspect] = value
    return {"aspects": user_data, "deal_breakers": deal_breakers if deal_breakers is not None else [], "deal_makers": deal_makers if deal_makers is not None else []}

async def ask_next_question(_user_id: int, latest_answer: str = ""):
    global travelers, chats, users_to_ask, start_trip_message

    if _user_id not in chats:
        print(f"Error: Chat session not found for user {travelers[_user_id]._username}")
        return None

    chat_session = chats[_user_id]
    traveler = travelers[_user_id]

    if latest_answer:
        prompt = f"The user answered '{latest_answer}'. Ask a brief follow-up question to understand their preferences better. Respond with 'DONE!' followed by the user's preferences if you have enough information."
        traveler._conversation_history.append({"role": "user", "content": latest_answer})
    else:
        prompt = "GO!"
        await first_prompt(chat_session, PROMPT_FILENAME)
        traveler._conversation_history.append({"role": "model", "content": "Instructions sent."})

    ai_response = await generate_prompt(chat_session, prompt)
    traveler._conversation_history.append({"role": "model", "content": ai_response})

    user = discord_client.get_user(_user_id)
    if user and "DONE!" not in ai_response:
        await user.send(ai_response)

    if "DONE!" in ai_response:
        await user.send("Thanks! I've got all I need.")
        traveler._done = True
        parts = ai_response.split("DONE!", 1)
        preferences_text = parts[1].strip()
        if preferences_text:
            print(f"Received DONE! for {traveler._username}:\n{preferences_text}")
            preferences = parse_single_preference(f"{traveler._username}:\n{preferences_text}")

            for attr_name in dir(traveler):
                if not attr_name.startswith('_'):
                    if attr_name in preferences['aspects']:
                        value = preferences['aspects'][attr_name]
                        # Attempt to convert to int if the attribute is expected to be a number
                        if isinstance(getattr(traveler, attr_name), int) and value.isdigit():
                            setattr(traveler, attr_name, int(value))
                        else:
                            setattr(traveler, attr_name, value)
                    elif attr_name in ['deal_breakers', 'deal_makers'] and preferences.get(attr_name):
                        setattr(traveler, attr_name, preferences[attr_name])
                        
            print(f"Saved preferences for {traveler._username}:\n{traveler}")
            del chats[_user_id]
            if _user_id in users_to_ask:
                users_to_ask.remove(_user_id)
                
            if not users_to_ask and start_trip_message:
                await start_trip_message.channel.send("All users have finished their preference gathering.")
                await trigger_dummy_procedure()
                
            elif users_to_ask: # Start next user in sequential mode
                genai_client = genai.Client(api_key=GEMINI_API_KEY) # Restart chat
                await asyncio.sleep(60) # Introduce 1 minute delay
                if users_to_ask:
                    next_user_id = users_to_ask[0]
                    chats[next_user_id] = genai_client.chats.create(model="gemini-2.0-flash")
                    await ask_next_question(next_user_id)
        return None
    else:
        return ai_response
        
async def trigger_dummy_procedure():
    print("\n--- Triggering Dummy Procedure with Traveler Data ---")
    # In a real scenario, you would process the 'travelers' data here
    global users_to_ask, trip_started, travelers, chats, start_trip_message
    users_to_ask = []
    trip_started = False
    travelers = {}
    chats = {}
    start_trip_message = None
    
    for _username, traveler in travelers.items():
        print(f"Traveler ID: {traveler._user_id}, Username: {traveler._username}")
        print(f"  Budget: {traveler.cheap}")
        print(f"  History: {traveler.history}")
        print(f"  Environmental Impact: {traveler.environmental_impact}")
        print(f"  Food: {traveler.food}")
        print(f"  Deal Breakers: {traveler.deal_breakers}")
        print(f"  Deal Makers: {traveler.deal_makers}")
        print("--------------------------------------------------")

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')

@discord_client.event
async def on_message(message):
    global users_to_ask, trip_started, travelers, chats, start_trip_message

    if message.author == discord_client.user:
        return

    if message.content.startswith('!add_user'):
        if not trip_started:
            usernames = message.content.split()[1:]
            for _username in usernames:
                member = discord.utils.get(message.guild.members, name=_username)
                if member and member.id not in users_to_ask:
                    users_to_ask.append(member.id)
                    travelers[member.id] = Traveler(member.id, member.name)
                    await message.channel.send(f"User '{_username}' added to the trip.")
                elif not member:
                    await message.channel.send(f"User '{_username}' not found in this server.")
                elif member.id in users_to_ask:
                    await message.channel.send(f"User '{_username}' is already added to the trip.")
        else:
            await message.channel.send("Cannot add users after the trip has started. Use '!start_trip' to begin.")

    elif message.content.startswith('!start_trip'):
        if users_to_ask:
            trip_started = True
            start_trip_message = message
            await message.channel.send(f"Starting preference gathering from users.")
            if users_to_ask:
                first_user_id = users_to_ask[0]
                chats[first_user_id] = genai_client.chats.create(model="gemini-2.0-flash")
                await ask_next_question(first_user_id)
        else:
            await message.channel.send("Please add users to the trip using '!add_user' before starting.")
            
    elif message.author.id in travelers and trip_started and message.author.id in chats:
        _user_id = message.author.id
        answer = message.content
        next_question = await ask_next_question(_user_id, answer)
        if next_question is None:
            if _user_id in travelers: # Add this check
                print(f"Conversation finished for {travelers[_user_id]._username}")
            else:
                print(f"Conversation finished for user ID {_user_id}, but not in travelers anymore.") # For debugging

discord_client.run(DISCORD_BOT_TOKEN)