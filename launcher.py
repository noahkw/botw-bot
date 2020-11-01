import asyncio
import configparser
import logging
import sys

import click as click
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from botwbot import BotwBot
from models.base import Base


def setup():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    )
    logger.addHandler(handler)

    config = configparser.ConfigParser()
    config.read("conf.ini")
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


@db.command(
    short_help="run a migration from the migrations folder", options_metavar="[options]"
)
@click.argument("number", nargs=1, metavar="[number]")
def migration(number):
    logger, config, creds = setup()

    loop = asyncio.get_event_loop()
    pool = create_engine(loop, logger, creds)

    with open(rf"migrations/schema_{number}.sql", "r") as f:
        query = f.read()

    loop.run_until_complete(pool.execute(query))
    print(f"migration {number} was completed successfully.")
    logger.info(f"migration {number} was completed successfully.")


@db.command(short_help="migrate to SQLalchemy", options_metavar="[options]")
@click.argument("files", nargs=-1, metavar="[files]")
def initial_migration(files):
    pass


if __name__ == "__main__":
    main()
