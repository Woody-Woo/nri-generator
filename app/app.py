from pathlib import Path
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
import openai
import requests
import os

OPENAI_API_KEY = "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"
IMAGE_FOLDER = Path.cwd().joinpath("images")

app = Flask(__name__)

def init_app():
    openai.api_key = OPENAI_API_KEY
    Path(IMAGE_FOLDER).mkdir(parents=True, exist_ok=True)

def load_history(filename="conversation_history.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            lines = file.read().splitlines()

            result = []

            for x in lines:
                spliteed = x.split("|||")
                if len(spliteed) == 2:
                    result.append((spliteed[0], spliteed[1]))
                else:
                    result.append((spliteed[0], ""))
            return result
        
    except FileNotFoundError:
        return []

def save_history(history, filename="conversation_history.txt"):
    with open(filename, "w", encoding="utf-8") as file:
        file.write('\n'.join('|||'.join(item) for item in history))

def download_image(url, filename, image_folder=IMAGE_FOLDER):
    response = requests.get(url)
    image_path = os.path.join(image_folder, filename) 
    with open(image_path, "wb") as f:
        f.write(response.content)

    from PIL import Image

    # Открываем изображение в формате RGB
    image = Image.open(image_path).convert('RGB')

    # Преобразуем изображение в формат RGBA
    image_rgba = image.convert('RGBA')

    # Сохраняем изображение в формате RGBA
    image_rgba.save(image_path)

def conversation_history_to_messages(conversation_history):
    messages = []

    for x, _ in conversation_history:
        if x.startswith("user:"):
            messages.append({"role": "user", "content": x[5:]})
        elif x.startswith("assistant:"):
            messages.append({"role": "assistant", "content": x[10:]})
        elif x.startswith("system:"):
            messages.append({"role": "system", "content": x[8:]})

    return messages

def create_master_ai_response(conversation_history):

    messages = conversation_history_to_messages(conversation_history)

    master_system_messages = [{"role": "system", "content": load_master_ai()}]

    master_ai_response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=master_system_messages + messages,
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.5,
    ).choices[0]['message'].content.strip()

    return master_ai_response

def create_image_ai_response(conversation_history):

    history_one_message = "\n".join(x[0] for x in conversation_history[-10:]).replace("user:", "Герой:").replace("assistant:", "Мастер истории:").replace("system:", "")
    
    ai_chat = load_history("image_ai.txt")
    
    hero_descriptions =  load_hero_description() #"Главный герой выглядит как молодой рыжеволосый хоббит. На нём надеты те предметы которые есть у него в инвентаре. Он в чёрной рубашке и шортах."

    ai_chat = [(x[0].format(hero_description=hero_descriptions, history_one_message=history_one_message), x[1]) for x in ai_chat]
    
    prompt_for_get_image = conversation_history_to_messages(ai_chat)

    image_system_messages = [{"role": "system", "content": load_image_ai()}]

    image_ai_response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=image_system_messages + prompt_for_get_image,
        max_tokens=250,
        n=1,
        stop=None,
        temperature=0.5,
    ).choices[0]['message'].content.strip()

    return image_ai_response

def create_simplifier_ai_response(conversation_history):
    history_one_message = "\n".join(x[0] for x in conversation_history)
    prompt_for_get_image = [
        {
            "role": "user",
            "content": f"У меня есть вот такая история, запомни её: \n ``` \n {history_one_message} \n ``` \n",
        },
        {"role": "assistant", "content": "Запомнила "},
        {
            "role": "user",
            "content": "Убери всю воду из этой истории. Но оставь все факты.",
        },
    ]

    simplifier_system_messages = [{"role": "system", "content": "Ты помошник, который убирает лишнее из текста."}]

    simplifier_ai_response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=simplifier_system_messages + prompt_for_get_image,
        max_tokens=2000,
        n=1,
        stop=None,
        temperature=0.5,
    ).choices[0]['message'].content.strip()

    return simplifier_ai_response


last_hero_image_path = ""

def load_hero_description():
    try:
        with open("hero_description.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""

def save_hero_description(description):
    with open("hero_description.txt", "w", encoding="utf-8") as file:
        file.write(description)

def generate_image(prompt):
    
    global last_hero_image_path
    img_response = openai.Image.create(
        prompt= prompt + " The image should resemble a medieval book illustration.",
        n=1,
        size="256x256",
        # image=open(Path.joinpath(IMAGE_FOLDER, last_hero_image_path), "rb"),
    )

    return img_response

@app.route("/generate_image", methods=["POST"])
def generate_hero():
    global last_hero_image_path
    prompt = 'Cartoon fantasy style: hero'
    img_response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="256x256",
    )
    
    img_filename = f"{uuid.uuid4()}.png"
    
    last_hero_image_path = img_filename
    download_image(img_response['data'][0]['url'], img_filename)

    return jsonify(img_url=img_filename)

@app.route("/")
def index():
    conversation_history = load_history()
    history_summary = "" # create_simplifier_ai_response(conversation_history)
    hero_description = load_hero_description()
    return render_template("index.html", conversation_history=conversation_history, history_summary=history_summary, hero_description=hero_description)


@app.route('/image/<path:img_path>')
def image(img_path):
    try:
        return send_from_directory(IMAGE_FOLDER, img_path)
    except Exception as e:
        print(e)
        return "404"

@app.route("/engine")
def engines():
    engine_list = openai.Engine.list()
    return render_template("engines.html", engines=engine_list["data"])

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form["user_input"]
    hero_description = request.form["hero_description"]
    save_hero_description(hero_description)
    conversation_history = load_history()

    if len(conversation_history) > 15:
        prehistory = create_simplifier_ai_response(conversation_history[:7])
        conversation_history = [("assistant:" + prehistory, "")] + conversation_history[7:]


    conversation_history.append((f"user: {user_input}", ""))

    master_ai_response = create_master_ai_response(conversation_history)

    image_ai_response = create_image_ai_response(conversation_history)
    
    img_response = generate_image(image_ai_response)

    img_filename = f"{uuid.uuid4()}.png"

    download_image(img_response['data'][0]['url'], img_filename)

    conversation_history.append((f"assistant: {master_ai_response}", img_filename))

    save_history(conversation_history)

    print("User input:", user_input)
    print("Master AI response:", master_ai_response)
    print("Image AI response:", image_ai_response)

    return jsonify(ai_response=master_ai_response, img_url=img_filename,history_summary="")

def load_master_ai(filename="master_ai.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""

def load_image_ai(filename="image_ai.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""

if __name__ == "__main__":
    init_app()
    app.run(debug=False)

