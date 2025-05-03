import discord
from google import genai
import asyncio
import re
from typing import Dict, List, Set, Optional

PROMPT_FILENAME = "prompt.txt"

DISCORD_BOT_TOKEN = 'MTM2Nzk5NDA0OTA1OTA5ODcxNw.G-sm5x.bc3Lvyk6Z1gwZD30UwhiMpgBH0erhdF3XM_-7M'  # Keep this as an environment variable

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
discord_client = discord.Client(intents=intents)
genai_clients: Dict[int, genai.Client] = {}  # Store genai clients per guild
guild_api_keys: Dict[int, Dict[str, str]] = {}  # Store API keys per guild

# Per-guild state management
guild_travelers: Dict[int, Dict[int, "Traveler"]] = {}  # guild_id -> {user_id -> Traveler}
guild_users_to_ask: Dict[int, List[int]] = {}  # guild_id -> [user_id]
guild_chats: Dict[int, Dict[int, genai.chats.Chat]] = {}  # guild_id -> {user_id -> Chat}
guild_city_suggestions: Dict[int, List[str]] = {}  # guild_id -> [city]
guild_trip_started: Dict[int, bool] = {}  # guild_id -> True/False
guild_start_trip_message: Dict[int, Optional[discord.Message]] = {}  # guild_id -> Message
guild_poll_message: Dict[int, Optional[discord.Message]] = {}  # guild_id -> Message
guild_voted_users: Dict[int, Set[int]] = {}  # guild_id -> {user_id}

class Traveler:
    def __init__(self, _user_id: int, _username: str):
        self._user_id = _user_id
        self._username = _username
        self.origin: Dict[str, str] = {"Country": None, "City": None}
        self.cheap: int = None
        self.history: int = None
        self.environmental_impact: int = None
        self.food: int = None
        self.art: int = None
        self.adventure: int = None
        self.temperature: int = None
        self.deal_breakers: List[str] = []
        self.deal_makers: List[str] = []
        self._conversation_history: List[Dict[str, str]] = []
        self._done: bool = False
        self._vote: str = None # To store the user's _vote

    def __str__(self):
        output = f"{self._username}:\n"
        if self.origin["City"] and self.origin["Country"]:
            output += f" origin, {self.origin['City']} {self.origin['Country']}\n"
        if self.cheap is not None:
            output += f" cheap, {self.cheap}\n"
        if self.history is not None:
            output += f" history, {self.history}\n"
        if self.environmental_impact is not None:
            output += f" environmental_impact, {self.environmental_impact}\n"
        if self.food is not None:
            output += f" food, {self.food}\n"
        if self.art is not None:
            output += f" art, {self.art}\n"
        if self.adventure is not None:
            output += f" adventure, {self.adventure}\n"
        if self.temperature is not None:
            output += f" temperature, {self.temperature}\n"
        if self.deal_breakers:
            output += f" DEAL_BREAKERS: {', '.join(self.deal_breakers)}.\n"
        if self.deal_makers:
            output += f" DEAL_MAKERS: {', '.join(self.deal_makers)}.\n"
        if self._vote:
            output += f" Vote: {self._vote}\n"
        return output.strip()

def get_traveler_preference_attributes(traveler_class):
    """Returns a list of preference attribute names from the Traveler class."""
    preference_attributes = []
    temp_traveler = traveler_class(_user_id=0, _username="")
    excluded_attributes = ['deal_breakers', 'deal_makers']
    for attr_name in temp_traveler.__dict__:
        if not attr_name.startswith('_') and attr_name not in excluded_attributes and not callable(getattr(temp_traveler, attr_name)):
            preference_attributes.append(attr_name)
    return preference_attributes

async def get_gemini_client(guild: discord.Guild) -> Optional[genai.Client]:
    """Retrieves or creates a Gemini client for the given guild."""
    guild_id = guild.id
    gemini_api_key = guild_api_keys.get(guild_id, {}).get('gemini_api_key')
    if gemini_api_key and guild_id not in genai_clients:
        try:
            genai_clients[guild_id] = genai.Client(api_key=gemini_api_key)
        except Exception as e:
            print(f"Error initializing Gemini client for guild {guild_id}: {e}")
            return None
    return genai_clients.get(guild_id)

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
    lines = ai_output.strip().split("\n")
    user_data = {}
    deal_breakers = None
    deal_makers = None
    origin_text = None

    for line in lines[1:]:
        line = line.strip()
        if line.startswith("origin,"):
            origin_text = line.split(",", 1)[1].strip()
        elif line.startswith("DEAL_BREAKERS:"):
            deal_breakers_text = line.split(":", 1)[1].strip()
            deal_breakers = [deal_breakers_text]
        elif line.startswith("DEAL_MAKERS:"):
            deal_makers_text = line.split(":", 1)[1].strip()
            deal_makers = [deal_makers_text]
        elif "," in line and not line.startswith("DEAL_BREAKERS:") and not line.startswith("DEAL_MAKERS:") and not line.startswith("origin,"):
            aspect, value = map(str.strip, line.split(','))
            user_data[aspect] = value

    origin_city = None
    origin_country = None
    if origin_text:
        origin_parts = origin_text.split()
        if len(origin_parts) >= 2:
            origin_city = origin_parts[0]
            origin_country = " ".join(origin_parts[1:])

    return {
        "origin": {"Country": origin_country, "City": origin_city},
        "aspects": user_data,
        "deal_breakers": deal_breakers if deal_breakers is not None else [],
        "deal_makers": deal_makers if deal_makers is not None else []
    }

async def ask_next_question(_user_id: int, guild: discord.Guild, latest_answer: str = "") -> Optional[str]:
    guild_id = guild.id
    if guild_id not in guild_chats or _user_id not in guild_chats[guild_id]:
        print(f"Error: Chat session not found for user {_user_id} in guild {guild_id}")
        return None

    chat_session = guild_chats[guild_id][_user_id]
    traveler = guild_travelers[guild_id].get(_user_id)
    if not traveler:
        print(f"Error: Traveler not found for user {_user_id} in guild {guild_id}")
        return None

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
            print(f"Received DONE! for {traveler._username} in guild {guild_id}:\n{preferences_text}")
            preferences = parse_single_preference(f"{traveler._username}:\n{preferences_text}")

            for attr_name in dir(traveler):
                if not attr_name.startswith('_'):
                    if attr_name in preferences['aspects']:
                        value = preferences['aspects'][attr_name]
                        if isinstance(getattr(traveler, attr_name), int) and value.isdigit():
                            setattr(traveler, attr_name, int(value))
                        else:
                            setattr(traveler, attr_name, value)
                    elif attr_name in ['origin', 'deal_breakers', 'deal_makers'] and preferences.get(attr_name):
                        setattr(traveler, attr_name, preferences[attr_name])

            print(f"Saved preferences for {traveler._username} in guild {guild_id}:\n{traveler}")
            if guild_id in guild_chats and _user_id in guild_chats[guild_id]:
                del guild_chats[guild_id][_user_id]
            if guild_id in guild_users_to_ask and _user_id in guild_users_to_ask[guild_id]:
                guild_users_to_ask[guild_id].remove(_user_id)

            if guild_id in guild_users_to_ask and not guild_users_to_ask[guild_id] and guild_id in guild_start_trip_message and guild_start_trip_message[guild_id]:
                await guild_start_trip_message[guild_id].channel.send("All users have finished their preference gathering.")
                await asyncio.sleep(60)
                await trigger_city_suggestion(guild_start_trip_message[guild_id].channel)

            elif guild_id in guild_users_to_ask and guild_users_to_ask[guild_id]:
                next_user_id = guild_users_to_ask[guild_id][0]
                if guild_id in guild_travelers and next_user_id in guild_travelers[guild_id] and discord_client.get_user(next_user_id) in guild.members:
                    genai_client = await get_gemini_client(guild)
                    if genai_client:
                        await asyncio.sleep(60)
                        if guild_id in guild_users_to_ask and guild_users_to_ask[guild_id]:
                            next_user_id = guild_users_to_ask[guild_id][0]
                            if guild_id not in guild_chats:
                                guild_chats[guild_id] = {}
                            guild_chats[guild_id][next_user_id] = genai_client.chats.create(model="gemini-2.0-flash")
                            await ask_next_question(next_user_id, guild)
                    else:
                        owner = guild.owner
                        if owner:
                            await owner.send(f"Gemini API key not set for server: {guild.name}. Please use '!gemini_api <KEY>' in a channel.")
        return None
    else:
        return ai_response

async def ask_cities(traveler_data: Dict[int, Traveler], guild: discord.Guild) -> Optional[List[str]]:
    guild_id = guild.id
    if not traveler_data:
        print(f"No traveler data available to suggest cities in guild {guild_id}.")
        return None

    if guild_id in guild_trip_started:
        guild_trip_started[guild_id] = False
    prompt_parts = []
    average_preferences = {}
    preference_attributes = get_traveler_preference_attributes(Traveler)

    for attr in preference_attributes:
        total = 0
        count = 0
        for traveler in traveler_data.values():
            value = getattr(traveler, attr)
            if isinstance(value, int):
                total += value
                count += 1
        if count > 0:
            average_preferences[attr] = total / count

    prompt_parts.append("Here is the information for the travelers:")
    for user_id, traveler in traveler_data.items():
        origin_str = f"Origin: {traveler.origin['City']} {traveler.origin['Country']}" if traveler.origin['City'] and traveler.origin['Country'] else "Origin not specified"
        budget_str = f"Budget preference (cheap): {traveler.cheap}" if traveler.cheap is not None else "Budget preference not specified"
        deal_breakers_str = f"Deal breakers: {', '.join(traveler.deal_breakers)}" if traveler.deal_breakers else "No deal breakers"
        deal_makers_str = f"Deal makers: {', '.join(traveler.deal_makers)}" if traveler.deal_makers else "No deal makers"

        prompt_parts.append(f"- User {traveler._username} ({origin_str}, {budget_str}, {deal_breakers_str}, {deal_makers_str})")

    prompt_parts.append("\nConsider the following average preferences across all users:")
    for aspect, avg_value in average_preferences.items():
        prompt_parts.append(f"- Average {aspect}: {avg_value}")

    prompt_parts.append("\nBased on this information, suggest 5 possible cities that would be suitable for this group of travelers. Provide only the names of the cities. Don't output anything else, just the names separated by \n without any additional formatting")

    full_prompt = "\n".join(prompt_parts)

    genai_client = await get_gemini_client(guild)
    if not genai_client:
        return None

    try:
        response = await genai_client.chats.create(model="gemini-2.0-flash").send_message(full_prompt)
        cities = [city.strip() for city in response.text.split("\n") if city.strip()]
        if guild_id not in guild_city_suggestions:
            guild_city_suggestions[guild_id] = []
        guild_city_suggestions[guild_id] = cities[:5]
        return guild_city_suggestions[guild_id]
    except Exception as e:
        print(f"Error generating city suggestions for guild {guild_id}: {e}")
        return None

async def create_city_poll(channel: discord.TextChannel, suggestions: List[str], traveler_ids: List[int]):
    guild_id = channel.guild.id
    if not suggestions:
        await channel.send("No city suggestions available to create a poll.")
        return

    global guild_poll_message, guild_voted_users
    if guild_id not in guild_voted_users:
        guild_voted_users[guild_id] = set()
    else:
        guild_voted_users[guild_id].clear()  # Reset votes for a new poll

    poll_message_content = "Please vote for your preferred city:\n"
    reactions = ["🇦", "🇧", "🇨", "🇩", "🇪"] # Up to 5 suggestions
    suggestion_emojis = dict(zip(suggestions, reactions))
    emoji_suggestion = dict(zip(reactions, suggestions))

    for i, city in enumerate(suggestions):
        poll_message_content += f"{reactions[i]} {city}\n"

    poll_msg = await channel.send(poll_message_content)
    guild_poll_message[guild_id] = poll_msg

    for reaction in reactions[:len(suggestions)]:
        await poll_msg.add_reaction(reaction)

    await channel.send(f"Travelers, please react to this message to cast your vote! Only {' '.join(f'<@{tid}>' for tid in traveler_ids)} can have their votes counted.")

async def trigger_city_suggestion(channel: discord.TextChannel):
    guild_id = channel.guild.id
    if guild_id not in guild_travelers:
        await channel.send("No travelers added for this trip.")
        return

    traveler_data = guild_travelers[guild_id]
    city_suggestions = await ask_cities(traveler_data, channel.guild)
    if city_suggestions:
        print(f"\n--- Suggested Cities for guild {guild_id}: ---")
        for i, city in enumerate(city_suggestions):
            print(f"{i+1}. {city}")
        print("------------------------")
        await create_city_poll(channel, city_suggestions, list(traveler_data.keys()))
    else:
        await channel.send("Could not generate city suggestions.")

async def process_votes(message: discord.RawReactionActionEvent):
    guild_id = message.guild_id
    user_id = message.user_id

    if guild_id not in guild_poll_message or message.message_id != guild_poll_message[guild_id].id:
        return
    if guild_id not in guild_travelers or user_id not in guild_travelers[guild_id]:
        return
    if guild_id not in guild_voted_users:
        guild_voted_users[guild_id] = set()
    if user_id in guild_voted_users[guild_id]:
        return
    if message.emoji.name not in ["🇦", "🇧", "🇨", "🇩", "🇪"]:
        return
    if guild_id not in guild_city_suggestions or not guild_city_suggestions[guild_id]:
        return

    emoji_suggestion = dict(zip(["🇦", "🇧", "🇨", "🇩", "🇪"], guild_city_suggestions[guild_id]))
    voted_city = emoji_suggestion.get(message.emoji.name)
    if voted_city:
        guild_travelers[guild_id][user_id]._vote = voted_city
        guild_voted_users[guild_id].add(user_id)
        user = discord_client.get_user(user_id)
        if user:
            await user.send(f"You have voted for '{voted_city}' in {message.guild.name}.")
        if len(guild_voted_users[guild_id]) == len(guild_travelers[guild_id]):
            await tally_votes(message.channel_id)

async def tally_votes(channel_id: int):
    channel = discord_client.get_channel(channel_id)
    if not channel or not isinstance(channel, discord.TextChannel):
        print(f"Error: Could not find text channel with ID {channel_id} to tally votes.")
        return

    guild_id = channel.guild.id
    if guild_id not in guild_travelers:
        await channel.send("No travelers for this server to tally votes.")
        return

    votes = {}
    for traveler in guild_travelers[guild_id].values():
        if traveler._vote:
            votes[traveler._vote] = votes.get(traveler._vote, 0) + 1

    if votes:
        results = "--- Poll Results ---\n"
        for city, count in sorted(votes.items(), key=lambda item: item[1], reverse=True):
            results += f"{city}: {count} votes\n"
        await channel.send(results)
    else:
        await channel.send("No votes were cast.")

@discord_client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == discord_client.user.id:
        return
    guild = discord_client.get_guild(payload.guild_id)
    if guild:
        await process_votes(payload)

@discord_client.event
async def on_ready():
    print(f'Logged in as {discord_client.user}')
    for guild in discord_client.guilds:
        guild_id = guild.id
        if guild_id not in guild_api_keys:
            guild_api_keys[guild_id] = {}
        if guild_id not in guild_travelers:
            guild_travelers[guild_id] = {}
        if guild_id not in guild_users_to_ask:
            guild_users_to_ask[guild_id] = []
        if guild_id not in guild_chats:
            guild_chats[guild_id] = {}
        if guild_id not in guild_city_suggestions:
            guild_city_suggestions[guild_id] = []
        if guild_id not in guild_trip_started:
            guild_trip_started[guild_id] = False
        if guild_id not in guild_start_trip_message:
            guild_start_trip_message[guild_id] = None
        if guild_id not in guild_poll_message:
            guild_poll_message[guild_id] = None
        if guild_id not in guild_voted_users:
            guild_voted_users[guild_id] = set()
        print(f"Initialized state for server: {guild.name} (ID: {guild_id})")

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user:
        return

    guild = message.guild
    user = message.author

    # Handle commands in server context
    if guild:
        guild_id = guild.id
        if message.content.startswith('!gemini_api'):
            api_key_parts = message.content.split()[1:]
            if api_key_parts:
                api_key = api_key_parts[0]
                guild_api_keys[guild_id]['gemini_api_key'] = api_key
                if guild_id in genai_clients:
                    del genai_clients[guild_id]
                await message.channel.send(f"Google Gemini API key registered for this server.")
            else:
                await message.channel.send("Please provide the Gemini API key after the command.")

        elif message.content.startswith('!skyscanner_api'):
            api_key_parts = message.content.split()[1:]
            if api_key_parts:
                api_key = api_key_parts[0]
                guild_api_keys[guild_id]['skyscanner_api_key'] = api_key
                await message.channel.send(f"Skyscanner API key registered for this server.")
            else:
                await message.channel.send("Please provide the Skyscanner API key after the command.")

        elif guild_id not in guild_api_keys or 'gemini_api_key' not in guild_api_keys[guild_id] and message.content.startswith('!'):
            await message.channel.send("The Gemini API key has not been set for this server. Please use '!gemini_api <KEY>'.")

        elif message.content.startswith('!add_user'):
            if not guild_trip_started.get(guild_id, False):
                usernames = message.content.split()[1:]
                if guild_id not in guild_users_to_ask:
                    guild_users_to_ask[guild_id] = []
                if guild_id not in guild_travelers:
                    guild_travelers[guild_id] = {}
                for _username in usernames:
                    member = discord.utils.get(guild.members, name=_username)
                    if member and member.id not in guild_users_to_ask[guild_id]:
                        guild_users_to_ask[guild_id].append(member.id)
                        guild_travelers[guild_id][member.id] = Traveler(member.id, member.name)
                        await message.channel.send(f"User '{_username}' added to the trip.")
                    elif not member:
                        await message.channel.send(f"User '{_username}' not found in this server.")
                    elif member.id in guild_users_to_ask[guild_id]:
                        await message.channel.send(f"User '{_username}' is already added to the trip.")
            else:
                await message.channel.send("Cannot add users after the trip has started. Use '!start_trip' to begin.")

        elif message.content.startswith('!start_trip'):
            if guild_id in guild_users_to_ask and guild_users_to_ask[guild_id]:
                guild_trip_started[guild_id] = True
                guild_start_trip_message[guild_id] = message
                await message.channel.send(f"Starting preference gathering from users.")
                first_user_id = guild_users_to_ask[guild_id][0]
                genai_client = await get_gemini_client(guild)
                if genai_client:
                    if guild_id not in guild_chats:
                        guild_chats[guild_id] = {}
                    guild_chats[guild_id][first_user_id] = genai_client.chats.create(model="gemini-2.0-flash")
                    await ask_next_question(first_user_id, guild)
                else:
                    owner = guild.owner
                    if owner:
                        await owner.send(f"Gemini API key not set for server: {guild.name}. Please use '!gemini_api <KEY>' in a channel.")
            else:
                await message.channel.send("Please add users to the trip using '!add_user' before starting.")

    # Handle direct messages to the bot
    elif not guild:
        user_id = user.id
        for g_id, travelers in guild_travelers.items():
            if user_id in travelers and guild_trip_started.get(g_id, False) and g_id in guild_chats and user_id in guild_chats[g_id]:
                answer = message.content
                found_guild = discord_client.get_guild(g_id)
                if found_guild:
                    next_question = await ask_next_question(user_id, found_guild, answer)
                    if next_question is None:
                        if user_id in guild_travelers.get(g_id, {}):
                            print(f"Conversation finished for {guild_travelers[g_id][user_id]._username} in guild {g_id} (via DM)")
                        else:
                            print(f"Conversation finished for user ID {user_id} (via DM), but not in travelers anymore in guild {g_id}.")
                    return  # Important: Exit after processing the DM
                else:
                    print(f"Error: Could not find guild with ID {g_id} for user {user_id}'s DM.")
                    return
                
discord_client.run(DISCORD_BOT_TOKEN)