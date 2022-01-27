import asyncio
import logging
import subprocess
import sys

import click as click
import yaml
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from botwbot import BotwBot
from models.base import Base


def load_config(config_file):
    with open(config_file, "r") as stream:
        config = yaml.safe_load(stream)

    return config


def setup():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    )
    logger.addHandler(handler)

    # disable some spammy logs
    logging.getLogger("discord.gateway").setLevel(logging.WARN)
    logging.getLogger("discord.client").setLevel(logging.WARN)

    config = load_config("config.yml")
    postgres = config["postgres"]

    return logger, config, postgres


def create_engine(logger, connection_string):
    try:
        engine = create_async_engine(connection_string)
        session = sessionmaker(bind=engine, class_=AsyncSession)
        return engine, session
    except Exception as e:
        click.echo(e, file=sys.stderr)
        click.echo("Could not set up PostgreSQL. Exiting.", file=sys.stderr)
        logger.exception("Could not set up PostgreSQL. Exiting.")


async def init_db(engine):
    async with engine.begin() as conn:
        # TODO: don't drop_all in prod
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def run_bot():
    logger, config, creds = setup()

    loop = asyncio.get_event_loop()

    engine, session = create_engine(logger, creds["connection_string"])

    loop.run_until_complete(init_db(engine))
    botw_bot = BotwBot(config)

    botw_bot.engine = engine
    botw_bot.Session = session
    botw_bot.run()

    logger.info("Cleaning up")


@click.group(invoke_without_command=True, options_metavar="[options]")
@click.pass_context
def main(ctx):
    """Launches the bot."""
    if ctx.invoked_subcommand is None:
        run_bot()


@main.group(short_help="database utility", options_metavar="[options]")
def db():
    pass


@db.command(short_help="migrate the database")
def migrate():
    click.echo("running migrations")
    subprocess.run(["alembic", "upgrade", "head"])


if __name__ == "__main__":
    main()
