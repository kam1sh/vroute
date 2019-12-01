import typing as ty
import logging

import asyncpg


log = logging.getLogger(__name__)


class NetworkingService:
    EXISTS = "SELECT EXISTS (SELECT net FROM networks WHERE net=$1)"

    def __init__(self, settings: ty.Mapping):
        self.settings = settings
        self.conn = None

    async def __aenter__(self):
        self.conn = await asyncpg.connect(
            host=self.settings["host"],
            user=self.settings["user"],
            password=self.settings["password"],
            database=self.settings["database"]
        )

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.close()

    async def load_networks(self, file: ty.Iterable[str]) -> ty.Tuple[int, int]:
        """
        Loads networks from file into the database,
        returns how many added and how many already exists.
        """
        async with self:
            return await self._load_networks(file)

    async def _load_networks(self, file: ty.Iterable[str]) -> ty.Tuple[int, int]:
        count, exists = 0, 0
        for network in file:
            network = network.rstrip()
            net_exists = await self.conn.fetchval(self.EXISTS, network)
            if net_exists:
                log.debug("%s exists", network)
                exists += 1
                continue
            await self.conn.execute(
                "INSERT INTO networks (net, info) VALUES ($1, '{}');",
                network
            )
            count += 1
        return count, exists

    async def export(self):
        pass
