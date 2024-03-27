from aiostream import stream
import logging
from typing import AsyncIterable, TypeVar


logger = logging.getLogger("krr")


# Define a type variable for the values yielded by the async generators
T = TypeVar("T")


async def async_gen_merge(*aiters: AsyncIterable[T]) -> AsyncIterable[T]:
    combine = stream.merge(*aiters)

    async with combine.stream() as streamer:
        async for item in streamer:
            yield item

