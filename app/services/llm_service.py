import os

from openrouter import OpenRouter
from app.config import settings

MODEL = settings.llm_model


def generate_answer(
    question: str,
    context: str,
) -> str:

    with OpenRouter(
        api_key=settings.openrouter_api_key
    ) as client:
        response = client.chat.send(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a codebase assistant. "
                        "Answer questions using only the "
                        "provided code context. "
                        "If the answer is not present in "
                        "the context, say you don't know."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Code Context:

{context}

Question:

{question}
""",
                },
            ],
            stream=False,
        )

    return response.choices[0].message.content