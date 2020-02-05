"""Click stuff"""
import asyncio
import logging
import time

import click

from . import VRoute, __version__


levels = [logging.WARNING, logging.INFO, logging.DEBUG]
pass_app = click.make_pass_decorator(VRoute)

# moved info function so we can mock app in tests
def get_vroute(cfg_file=None) -> VRoute:
    app = VRoute()
    app.read_config(file=cfg_file)
    return app


@click.group()
@click.option("--config", help="Configuration file")
@click.option("-v", "--verbose", count=True)
@click.version_option(__version__, prog_name="vroute")
@click.pass_context
def cli(ctx, config, verbose):
    level = levels[min(verbose, 2)]
    log = logging.getLogger("vroute")
    log.setLevel(level)
    logging.basicConfig(level=level)
    try:
        ctx.obj = get_vroute(cfg_file=config)
    except KeyError as exc:
        click.echo(f"Failed to configure: \n{exc}")
        ctx.exit(1)
    ctx.obj.connect()


@cli.command("load-networks")
@click.argument("file", type=click.File("r"))
@pass_app
def load_networks(app, file):
    exclude = set(app.cfg.get("exclude"))
    count, exists = asyncio.run(
        app.network_service.load_networks(
            filter(lambda x: x.strip() not in exclude, file)
        )
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


@cli.command()
@pass_app
def sync(app: VRoute):
    for mgr in app.managers:
        start = time.time()
        asyncio.run(app.network_service.export(mgr))
        elapsed = time.time() - start
        click.echo(f"Added {mgr.name} routes in {elapsed:.2f} seconds.")
        mgr.disconnect()


def main():
    cli()  # pylint:disable=E1120
