import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

mensagem = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    messages=[
        {
            "role": "user",
            "content": "Responda em uma frase: o que é o Fear & Greed Index e como ele afeta o Bitcoin?"
        }
    ]
)

print(mensagem.content[0].text)