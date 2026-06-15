from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message


def generate_movie_idea(label: str, temperature=1.0):
    messages: list[MessageParam] = []

    add_user_message(messages, "Generate a one sentence movie idea.")

    answer = chat(messages, temperature=temperature)
    print(f"{label} (temp: {temperature}):\n{answer}\n")


generate_movie_idea("Low temperature", 0.0)
generate_movie_idea("Medium temperature", 0.5)
generate_movie_idea("High temperature", 1.0)
