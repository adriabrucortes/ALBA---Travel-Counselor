import discord
from google import genai
import re
from typing import Dict, List

PROMPT_FILENAME = "prompt.txt"

DISCORD_BOT_TOKEN = 'MTM2Nzk5NDA0OTA1OTA5ODcxNw.G-sm5x.bc3Lvyk6Z1gwZD30UwhiMpgBH0erhdF3XM_-7M'
GEMINI_API_KEY = 'AIzaSyBONGjbfYmFfLd_HPnnQiw8XpA4rZlulMs'

client = genai.Client(api_key=GEMINI_API_KEY)
chat = client.chats.create(model="gemini-2.0-flash")

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

    def __str__(self):
        output = f"{self.username}:\n"
        if self.budget is not None:
            output += f"budget, {self.budget}\n"
        if self.history is not None:
            output += f"history, {self.history}\n"
        if self.environmental_impact is not None:
            output += f"environmental_impact, {self.environmental_impact}\n"
        if self.food is not None:
            output += f"food, {self.food}\n"
        if self.deal_breakers:
            output += f"DEAL_BREAKERS: {', '.join(self.deal_breakers)}.\n"
        if self.deal_makers:
            output += f"DEAL_MAKERS: {', '.join(self.deal_makers)}.\n"
        return output.strip()

travelers: Dict[int, Traveler] = {}
users_to_ask: List[int] = []
current_question: str = None
responses: Dict[int, str] = {}
trip_started: bool = False

async def generate_prompt(prompt: str) -> str:
    try:
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating question: {e}")
        return "Sorry, I couldn't generate a question right now."

async def first_prompt(file_path: str):
    try:
        with open(file_path, 'r') as file:
            initial_prompt_content = file.read()
    except FileNotFoundError:
        await generate_prompt(f"Error: File not found at '{file_path}'")
        return

    sentences = [s.strip() + '.' for s in initial_prompt_content.split('.') if s.strip()]

    await generate_prompt("I'm going to send you a series of instructions you need to understand and you must not reply until I say GO!")

    for sentence in sentences:
        await generate_prompt(sentence)

def parse_preferences(ai_output: str) -> Dict[str, Dict[str, any]]:
    data = {}
    parts = ai_output.split("DONE!", 1)[1].strip()
    user_blocks = parts.strip().split("\n\n")
    for user_block in user_blocks:
        if not user_block.strip():
            continue
        lines = user_block.strip().split("\n")
        username = lines[0].strip().rstrip(":")
        user_data = {}
        deal_breakers = []
        deal_makers = []
        current_section = None
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("DEAL_BREAKERS:"):
                current_section = "DEAL_BREAKERS"
            elif line.startswith("DEAL_MAKERS:"):
                current_section = "DEAL_MAKERS"
            elif ":" not in line and current_section == "DEAL_BREAKERS":
                deal_breakers.append(line.strip())
            elif ":" not in line and current_section == "DEAL_MAKERS":
                deal_makers.append(line.strip())
            elif "," in line and current_section is None:
                aspect, value = map(str.strip, line.split(','))
                user_data[aspect] = value
        data[username] = {"aspects": user_data, "deal_breakers": deal_breakers, "deal_makers": deal_makers}
    return data

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')

@discord_client.event
async def on_message(message):
    global users_to_ask, current_question, responses, trip_started, travelers  # Add 'travelers' here

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

    elif message.content.startswith('!start_trip'):
        if users_to_ask:
            trip_started = True
            responses = {user_id: None for user_id in users_to_ask}
            await first_prompt(PROMPT_FILENAME)
            current_question = await generate_prompt("GO!")
            await message.channel.send(current_question)
            for user_id in users_to_ask:
                user = discord_client.get_user(user_id)
                if user:
                    await user.send(current_question)
        else:
            await message.channel.send("Please add users to the trip using '!add_user' before starting.")

    elif current_question and message.author.id in users_to_ask and responses[message.author.id] is None:
        responses[message.author.id] = message.content
        print(f"Received response from {message.author.name}: {message.content}")

        if all(response is not None for response in responses.values()):
            print("All users have responded to the current question.")
            ai_input = "DONE!\n\n"
            for user_id in users_to_ask:
                traveler = travelers[user_id]
                if responses[user_id]:
                    ai_input += f"{traveler.username}:\n"
                    ai_input += f"{responses[user_id]}\n\n"

            preferences_data = parse_preferences(ai_input)
            for user_id, data in preferences_data.items():
                if user_id in travelers:
                    traveler = travelers[user_id]
                    if 'budget' in data['aspects']:
                        traveler.budget = int(data['aspects']['budget'])
                    if 'history' in data['aspects']:
                        traveler.history = int(data['aspects']['history'])
                    if 'environmental_impact' in data['aspects']:
                        traveler.environmental_impact = int(data['aspects']['environmental_impact'])
                    if 'food' in data['aspects']:
                        traveler.food = int(data['aspects']['food'])
                    traveler.deal_breakers = data['deal_breakers']
                    traveler.deal_makers = data['deal_makers']

            print("Parsed preferences:")
            for user_id, traveler in travelers.items():
                print(traveler)

            await message.channel.send("I have gathered the initial preferences from everyone. Processing...")
            # You can add further logic here to process the travelers' data
            users_to_ask = []
            current_question = None
            responses = {}
            travelers = {}  # Reset for the next trip
            trip_started = False

discord_client.run(DISCORD_BOT_TOKEN)