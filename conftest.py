# Make sure pytest loads the asyncio plugin so `async def` tests run.
pytest_plugins = ("pytest_asyncio",)
