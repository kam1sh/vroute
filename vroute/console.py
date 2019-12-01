"""Click stuff"""
import asyncio
import logging
import time

import click

from . import VRoute, __version__
from .services import NetworkingService
from .util import WindowIterator


levels = [logging.WARNING, logging.INFO, logging.DEBUG]
pass_app = click.make_pass_decorator(VRoute)

# moved info function so we can mock app in tests
def get_vroute():
    app = VRoute()
    app.read_config()
    return app


@click.group()
@click.version_option(__version__, prog_name="vroute")
@click.pass_context
def cli(ctx):
    ctx.obj = get_vroute()

@cli.command("load-networks")
@click.argument("file", type=click.File("r"))
@pass_app
def load_networks(app, file):
    try:
        psql_config = app.cfg["postgresql"]
    except KeyError as exc:
        click.echo(f"Failed to configure: \n{exc}")
        return
    service = NetworkingService(psql_config)

    count, exists = asyncio.run(
        service.load_networks(file)
    )
    click.echo(f"Added {count} routes in database.")
    click.echo(f"{exists} routes skipped.")

# @cli.command()
# @pass_app
# def show(app):
#     response = app.request("get", "/")
#     if response.status_code == 204:
#         click.echo("No hosts added yet.")
#         return
#     json = response.json()
#     for host, data in json.items():
#         comment = data.get("comment")
#         comment = (" - " + comment) if comment else ""
#         click.echo(host + comment)
#         addrs = WindowIterator(data["addrs"])
#         if addrs.has_any:
#             for addr in addrs:
#                 symbol = "├──" if not addrs.last else "└──"
#                 click.echo(f" {symbol} {addr}")
#         else:
#             click.echo(" └── No addresses resolved yet.")


# @cli.command()
# @click.argument("host")
# @pass_app
# def remove(app, host):
#     response = app.request("post", "/rm", json={"host": host}, check_resp=False)
#     if response.status_code == 404:
#         click.echo(response.json()["error"])
#         return 1
#     if response.status_code == 204:
#         click.echo(f"Host {host} removed from database.")


@cli.command()
@pass_app
def sync(app):
    start = time.time()
    json = app.request("post", "/sync").json()
    elapsed = time.time() - start
    added, skipped = json["added"], json["skipped"]
    click.echo(f"Added {added} routes, skipped {skipped} in {elapsed:.2f} seconds")
    if "full" in json:
        click.echo("RouterOS synced successfully.")


# @cli.command()
# @click.confirmation_option(prompt="Do you want to remove outdated routes?")
# @pass_app
# def purge(app):
#     response = app.request("post", "/purge")
#     json = response.json()
#     print(json)
#     click.echo(f"Removed {json['removed']} routes.")
#     click.echo(f"Removed {json['removed_ros']} routes in RouterOS.")


@cli.command()
@click.option("-v", "--verbose", count=True)
@click.option("--nocoro", is_flag=True, help="Disable coroutines")
@pass_app
def serve(app, verbose, nocoro):
    level = levels[min(verbose, 2)]
    log = logging.getLogger("vroute")
    log.setLevel(level)
    logging.basicConfig(level=level)
    app.load_db()
    with app:
        webapp = get_webapp(app, coroutines=not nocoro)
        app.serve(webapp=webapp)


def main():
    cli()  # pylint:disable=E1120
