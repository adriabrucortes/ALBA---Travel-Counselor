import discord
from google import genai
import re
from typing import Dict, List

parallel_mode: bool = False

PROMPT_FILENAME = "prompt.txt"

DISCORD_BOT_TOKEN = 'MTM2Nzk5NDA0OTA1OTA5ODcxNw.G-sm5x.bc3Lvyk6Z1gwZD30UwhiMpgBH0erhdF3XM_-7M'
GEMINI_API_KEY = 'AIzaSyBXKpZrBkFrXZNDoLCIaW-n5mY5AqauXcE'

genai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
discord_client = discord.Client(intents=intents)

class Traveler:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.budget: int = None
        self.history: int = None
        self.environmental_impact: int = None
        self.food: int = None
        self.deal_breakers: List[str] = []
        self.deal_makers: List[str] = []
        self.conversation_history: List[Dict[str, str]] = []
        self.done: bool = False

    def __str__(self):
        output = f"{self.username}:\n"
        if self.budget is not None:
            output += f" budget, {self.budget}\n"
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

    sentences = [s.strip() + '.' for s in initial_prompt_content.split('.') if s.strip()]

    await generate_prompt(chat_session, "I'm going to send you a series of instructions you need to understand and you must not reply until I say GO!")

    for sentence in sentences:
        await generate_prompt(chat_session, sentence)


def parse_single_preference(ai_output: str) -> Dict[str, any]:
    data = {}
    lines = ai_output.strip().split("\n")
    username_line = lines[0].strip().rstrip(":")
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

async def ask_next_question(user_id: int, latest_answer: str = ""):
    global travelers, chats, users_to_ask, start_trip_message, parallel_mode

    if user_id not in chats:
        print(f"Error: Chat session not found for user {travelers[user_id].username}")
        return None

    chat_session = chats[user_id]
    traveler = travelers[user_id]

    if latest_answer:
        prompt = f"The user answered '{latest_answer}'. Ask a brief follow-up question to understand their preferences better. Respond with 'DONE!' followed by the user's preferences if you have enough information."
        traveler.conversation_history.append({"role": "user", "content": latest_answer})
    else:
        prompt = "GO!"
        await first_prompt(chat_session, PROMPT_FILENAME)
        traveler.conversation_history.append({"role": "model", "content": "Instructions sent."})
        prompt = "GO!" # The actual first question

    ai_response = await generate_prompt(chat_session, prompt)
    traveler.conversation_history.append({"role": "model", "content": ai_response})

    user = discord_client.get_user(user_id)
    if user:
        await user.send(ai_response)

    if "DONE!" in ai_response:
        traveler.done = True
        parts = ai_response.split("DONE!", 1)
        preferences_text = parts[1].strip()
        if preferences_text:
            print(f"Received DONE! for {traveler.username}:\n{preferences_text}")
            preferences = parse_single_preference(f"{traveler.username}:\n{preferences_text}")
            traveler.budget = int(preferences['aspects'].get('budget', None)) if preferences['aspects'].get('budget') else None
            traveler.history = int(preferences['aspects'].get('history', None)) if preferences['aspects'].get('history') else None
            traveler.environmental_impact = int(preferences['aspects'].get('environmental_impact', None)) if preferences['aspects'].get('environmental_impact') else None
            traveler.food = int(preferences['aspects'].get('food', None)) if preferences['aspects'].get('food') else None
            traveler.deal_breakers = preferences['deal_breakers']
            traveler.deal_makers = preferences['deal_makers']
            print(f"Saved preferences for {traveler.username}:\n{traveler}")
            del chats[user_id]
            if user_id in users_to_ask:
                users_to_ask.remove(user_id)
            if not users_to_ask and start_trip_message:
                await start_trip_message.channel.send("All users have finished their preference gathering.")
                await trigger_dummy_procedure()
            elif not parallel_mode and users_to_ask: # Start next user in sequential mode
                genai_client = genai.Client(api_key=GEMINI_API_KEY) # Restart chat
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
    
    for username, traveler in travelers.items():
        print(f"Traveler ID: {traveler.user_id}, Username: {traveler.username}")
        print(f"  Budget: {traveler.budget}")
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
    global parallel_mode, users_to_ask, trip_started, travelers, chats, start_trip_message

    if message.author == discord_client.user:
        return

    if message.content.startswith('!add_user'):
        if not trip_started:
            usernames = message.content.split()[1:]
            for username in usernames:
                member = discord.utils.get(message.guild.members, name=username)
                if member and member.id not in users_to_ask:
                    users_to_ask.append(member.id)
                    travelers[member.id] = Traveler(member.id, member.name)
                    await message.channel.send(f"User '{username}' added to the trip.")
                elif not member:
                    await message.channel.send(f"User '{username}' not found in this server.")
                elif member.id in users_to_ask:
                    await message.channel.send(f"User '{username}' is already added to the trip.")
        else:
            await message.channel.send("Cannot add users after the trip has started. Use '!start_trip' to begin.")

    elif message.content.startswith('!set_mode'):
        mode = message.content.split()[1].lower()
        if mode == 'parallel':
            parallel_mode = True
            await message.channel.send("Set to parallel mode (asking all users concurrently).")
        elif mode == 'sequential':
            parallel_mode = False
            await message.channel.send("Set to sequential mode (asking one user at a time).")
        else:
            await message.channel.send("Invalid mode. Use 'parallel' or 'sequential'.")

    elif message.content.startswith('!start_trip'):
        if users_to_ask:
            trip_started = True
            start_trip_message = message
            await message.channel.send(f"Starting preference gathering in {'parallel' if parallel_mode else 'sequential'} mode.")
            if parallel_mode:
                chats = {user_id: genai_client.chats.create(model="gemini-2.0-flash") for user_id in users_to_ask}
                for user_id in users_to_ask:
                    await ask_next_question(user_id)
            else:
                if users_to_ask:
                    genai_client = genai.Client(api_key=GEMINI_API_KEY) # Restart chat
                    first_user_id = users_to_ask[0]
                    chats[first_user_id] = genai_client.chats.create(model="gemini-2.0-flash")
                    await ask_next_question(first_user_id)
        else:
            await message.channel.send("Please add users to the trip using '!add_user' before starting.")
            
    elif message.author.id in travelers and trip_started and message.author.id in chats:
        user_id = message.author.id
        answer = message.content
        next_question = await ask_next_question(user_id, answer)
        if next_question is None:
            if user_id in travelers: # Add this check
                print(f"Conversation finished for {travelers[user_id].username}")
            else:
                print(f"Conversation finished for user ID {user_id}, but not in travelers anymore.") # For debugging

discord_client.run(DISCORD_BOT_TOKEN)