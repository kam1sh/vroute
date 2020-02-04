from datetime import datetime
import typing as ty
import logging

import asyncpg

from .routing import Manager

log = logging.getLogger(__name__)


EXISTS = "SELECT EXISTS (SELECT net FROM networks WHERE net=$1)"


class NetworkingService:
    conn: asyncpg.Connection

    def __init__(self, settings: ty.Mapping):
        self.settings = settings
        self.conn = None

    async def connect(self):
        self.conn = await asyncpg.connect(
            host=self.settings["host"],
            user=self.settings["user"],
            password=self.settings["password"],
            database=self.settings["database"],
        )

    async def close(self):
        await self.conn.close()

    async def __aenter__(self):
        await self.connect()

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def load_networks(self, file: ty.Iterable[str]) -> ty.Tuple[int, int]:
        """
        Loads networks from file into the database,
        returns how many added and how many already exists.
        """
        async with self:
            return await self._load_networks(file)

    async def _load_networks(self, file: ty.Iterable[str]) -> ty.Tuple[int, int]:
        count, exists = 0, 0
        now = datetime.now()
        for network in file:
            network = network.rstrip()
            net_exists = await self.conn.fetchval(EXISTS, network)
            if net_exists:
                log.debug("%s exists", network)
                exists += 1
                continue
            await self.conn.execute(
                "INSERT INTO networks (net, updated) VALUES ($1, NULL);", network
            )
            count += 1
        return count, exists

    async def update(self, manager: Manager):
        now = datetime.now()
        async with self:
            for network in manager.current():
                await self.conn.execute(
                    f"UPDATE networks SET added_{manager.name} = true, updated = $2 WHERE net = $1",
                    network.with_netmask(),
                    now,
                )
            await self.conn.execute(
                f"UPDATE networks SET added_{manager.name} = false WHERE updated != $1",
                now,
            )

    async def export(self, manager: Manager):
        async with self:
            async with self.conn.transaction(isolation="serializable"):
                async for record in self.conn.cursor(
                    f"SELECT net FROM networks WHERE added_{manager.name} = false;"
                ):
                    network = record["net"]
                    manager.add(str(network))
                    await self.conn.execute(
                        f"UPDATE networks SET added_{manager.name} = true WHERE net = $1",
                        network,
                    )
