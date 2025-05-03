import discord
from google import genai

PROMPT_FILENAME = "prompt.txt"

DISCORD_BOT_TOKEN = 'MTM2Nzk5NDA0OTA1OTA5ODcxNw.G-sm5x.bc3Lvyk6Z1gwZD30UwhiMpgBH0erhdF3XM_-7M'
GEMINI_API_KEY = 'AIzaSyBONGjbfYmFfLd_HPnnQiw8XpA4rZlulMs'

client = genai.Client(api_key=GEMINI_API_KEY)
chat = client.chats.create(model="gemini-2.0-flash")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

user_question_history = {} # To store questions and answers for each user

async def generate_prompt(prompt):
    try:
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating question: {e}")
        return "Sorry, I couldn't generate a question right now."

async def first_prompt(file_path):
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

    #await channel.send("GO!")

async def get_preference_summary(history):
    try:
        response = chat.send_message(
            contents=[f"Based on the following questions and answers: {history}, what can you infer about the user's preferences?"]
        )
        return response.text
    except Exception as e:
        print(f"Error generating preference summary: {e}")
        return "Sorry, I couldn't determine your preferences right now."

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!ask'):
        user_id = message.author.id
        user_question_history[user_id] = []
        await first_prompt(PROMPT_FILENAME)
        first_question = await generate_prompt("GO!")
        user_question_history[user_id].append({"question": first_question, "answer": None})
        await message.channel.send(first_question)

    elif message.author.id in user_question_history and user_question_history[message.author.id][-1]["answer"] is None:
        user_answer = message.content
        user_id = message.author.id
        user_question_history[user_id][-1]["answer"] = user_answer

        #if len(user_question_history[user_id]) < 3: # Example: Ask 3 questions
        previous_question = user_question_history[user_id][-1]["question"]
        next_prompt = f"The user answered '{user_answer}' to the question '{previous_question}'. Ask a brief follow-up question to understand their preferences better."
        next_question = await generate_prompt(next_prompt)
        user_question_history[user_id].append({"question": next_question, "answer": None})
        await message.channel.send(next_question)
        """
        else:
            history_text = ""
            for item in user_question_history[user_id]:
                history_text += f"Q: {item['question']}, A: {item['answer']}\n"
            preferences = await get_preference_summary(history_text)
            await message.channel.send(f"Based on our conversation, your preferences seem to be: {preferences}")
            del user_question_history[user_id] # Reset for the next interaction
        """

# Replace 'YOUR_DISCORD_BOT_TOKEN' with your actual Discord bot token
client.run(DISCORD_BOT_TOKEN)