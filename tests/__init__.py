import asyncio
from datetime import timedelta, datetime
from json import dumps as jsondump

import click.testing
from vroute import console, web
from vroute.models import Host, Address


class DumbFuture(asyncio.Future):
    def __init__(self, value):
        super().__init__()
        self.set_result(value)


class AnswerStub:
    def __init__(self, host, ttl, kind="A"):
        self.host = host
        self.ttl = ttl
        self.type = kind


class Helpers:
    def __init__(self, mocker, session, requests):
        self.mocker = mocker
        self.session = session
        self.requests = requests

    def add_host(self, name, *addresses, ttl=300):
        host = Host(name=name, expires=datetime.now() + timedelta(seconds=ttl))
        self.session.add(host)
        self.session.commit()
        for address in addresses:
            addr = Address()
            addr.host_id = host.id
            addr.value = address
            self.session.add(addr)
        self.session.commit()

    def mock_resolve(self, *addresses, ttl=300):
        future = asyncio.Future()
        future.set_result([AnswerStub(addr, ttl=ttl) for addr in addresses])
        self.mocker.patch.object(Host.resolver, "query")
        mock = Host.resolver.query
        mock.return_value = future

    def get(self, url, params=None):
        return self.requests.get(url, params=params)

    def post(self, url, **json):
        return self.requests.post(url, data=jsondump(json))

    def invoke(self, *args):
        runner = click.testing.CliRunner()
        return runner.invoke(console.cli, args)
