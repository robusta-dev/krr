import asyncio
import logging
from typing import AsyncIterable, TypeVar


logger = logging.getLogger("krr")


# Define a type variable for the values yielded by the async generators
T = TypeVar("T")


def async_gen_merge(*aiters: AsyncIterable[T]) -> AsyncIterable[T]:
    queue = asyncio.Queue()
    iters_remaining = set(aiters)

    async def drain(aiter):
        try:
            async for item in aiter:
                await queue.put(item)
        except Exception:
            logger.exception(f"Error in async generator {aiter}")
            iters_remaining.discard(aiter)
            await queue.put(None)
        finally:
            iters_remaining.discard(aiter)

    async def merged():
        while iters_remaining:
            item = await queue.get()

            if item is None:
                continue

            yield item

    for aiter in aiters:
        asyncio.create_task(drain(aiter))

    return merged()
