import asyncio


async def main() -> None:
    """Run the NeuroFlow background worker."""
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())