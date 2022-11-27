import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)


class ExceededMaximumRetries(Exception):
    def __init__(self, url, tries):
        super().__init__(
            f"Exceeded the maximum number of retries ({tries}) fetching '{url}'"
        )
        self.url = url
        self.tries = tries


class _RetryException(Exception):
    pass


class RetryingSession:
    DELAY_BASE = 2
    TIMEOUT = 10

    def __init__(self, max_tries, method, url, *args, **kwargs):
        self.max_tries = max_tries
        self.method = method
        self.url = url
        self.args = args
        self.kwargs = kwargs
        self.context_manager = None
        self.last_exception = None

    async def on_retry(self):
        """Override to specify behavior on the first retry attempt."""
        pass

    async def _do_request(self):
        try:
            self.context_manager = self.method(self.url, *self.args, **self.kwargs)

            resp = await asyncio.wait_for(
                self.context_manager.__aenter__(), timeout=self.TIMEOUT
            )

            if resp and (resp.status < 200 or resp.status >= 300):
                logger.info(
                    "Requesting URL '%s' failed with status code %d",
                    self.url,
                    resp.status,
                )
                raise _RetryException

            return resp
        except Exception as e:
            self.last_exception = e
            raise _RetryException from e

    async def __aenter__(self):
        for current_try in range(self.max_tries):
            try:
                return await self._do_request()
            except _RetryException:
                if current_try == 0 and self.on_retry is not None:
                    asyncio.create_task(self.on_retry())

                if current_try < self.max_tries - 1:
                    delay = self.DELAY_BASE**current_try
                    logger.info(
                        "Waiting %d seconds before retrying '%s'", delay, self.url
                    )
                    await asyncio.sleep(delay)
        else:
            if self.last_exception:
                raise ExceededMaximumRetries(
                    self.url, self.max_tries
                ) from self.last_exception
            else:
                raise ExceededMaximumRetries(self.url, self.max_tries)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.context_manager.__aexit__(exc_type, exc_val, exc_tb)


class ReactingRetryingSession(RetryingSession):
    def __init__(
        self, max_tries, method, url, *args, message=None, emoji=None, **kwargs
    ):
        super().__init__(max_tries, method, url, *args, **kwargs)

        self.message = message
        self.emoji = emoji

    async def on_retry(self):
        if self.message is not None:
            await self.message.add_reaction(self.emoji)


async def _test():
    session = aiohttp.ClientSession()
    params = headers = {}
    url = "https://httpstat.us/300"

    try:
        async with RetryingSession(
            3, session.get, url, params=params, headers=headers
        ) as response:
            data = await response.read()
            print(data)
    except ExceededMaximumRetries:
        logger.exception("Exceeded maximum retries: ")
        print("F")

    await session.close()


if __name__ == "__main__":
    asyncio.run(_test())
