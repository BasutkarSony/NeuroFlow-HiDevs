import asyncio

from providers.base import ChatMessage
from providers.openai_provider import OpenAIProvider


async def main():
    provider = OpenAIProvider(model="gpt-4o-mini")

    embeddings = await provider.embed(["hello world"])

    print("Embedding received")
    print("Embedding dimensions:", len(embeddings[0]))

    messages = [
        ChatMessage(
            role="user",
            content="Say one word",
        )
    ]

    print("Streaming response: ", end="", flush=True)

    async for token in provider.stream(messages):
        print(token, end="", flush=True)

    print()


if __name__ == "__main__":
    asyncio.run(main())