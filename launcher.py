import asyncio
import configparser
import json
import logging
import sys

import asyncpg
import click as click
import pendulum

from botwbot import BotwBot


def setup():
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(filename='botw-bot.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    config = configparser.ConfigParser()
    config.read('conf.ini')
    postgres = config['postgres']

    pg_creds = {
        'user': postgres['user'],
        'password': postgres['password'],
        'database': postgres['db'],
        'host': postgres['host']
    }

    return logger, config, pg_creds


def create_pool(loop, logger, creds):
    try:
        pool = loop.run_until_complete(asyncpg.create_pool(**creds))
        return pool
    except Exception as e:
        click.echo('Could not set up PostgreSQL. Exiting.', file=sys.stderr)
        logger.exception('Could not set up PostgreSQL. Exiting.')
        return


def run_bot():
    logger, config, creds = setup()

    loop = asyncio.get_event_loop()
    pool = create_pool(loop, logger, creds)

    botw_bot = BotwBot(config)
    botw_bot.pool = pool
    botw_bot.run()

    logger.info('Cleaning up')


@click.group(invoke_without_command=True, options_metavar='[options]')
@click.pass_context
def main(ctx):
    """Launches the bot."""
    loop = asyncio.get_event_loop()
    if ctx.invoked_subcommand is None:
        run_bot()


@main.group(short_help='database utility', options_metavar='[options]')
def db():
    pass


@db.command(short_help='migrate to postgres', options_metavar='[options]')
@click.argument('files', nargs=-1, metavar='[files]')
def initial_migration(files):
    logger, config, creds = setup()

    loop = asyncio.get_event_loop()
    pool = create_pool(loop, logger, creds)

    nominations_json = [filename for filename in files if 'nominations' in filename]
    past_winners_json = [filename for filename in files if 'past_winners' in filename]
    mirrors_json = [filename for filename in files if 'mirrors' in filename]
    reminders_json = [filename for filename in files if 'reminders' in filename]
    settings_json = [filename for filename in files if 'settings' in filename]
    tags_json = [filename for filename in files if 'tags' in filename]

    async def migrate_nominations():
        print(f'migrating {nominations_json}')
        logger.info(f'migrating {nominations_json}')

        with open(nominations_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM botw_nominations
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'botw_nominations already has rows. skipping.')
            logger.info(f'botw_nominations already has rows. skipping.')
            return

        tuples = []
        for nomination in data:
            tuples.append((nomination['guild'], nomination['idol']['group'], nomination['idol']['name'],
                           nomination['member']))

        query = """INSERT INTO botw_nominations (guild, idol_group, idol_name, member)
                   VALUES ($1, $2, $3, $4);"""
        await pool.executemany(query, tuples)

    async def migrate_past_winners():
        print(f'migrating {past_winners_json}')
        logger.info(f'migrating {past_winners_json}')

        with open(past_winners_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM botw_winners
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'botw_winners already has rows. skipping.')
            logger.info(f'botw_winners already has rows. skipping.')
            return

        tuples = []
        for winner in data:
            tuples.append((winner['guild'], pendulum.from_timestamp(winner['timestamp']), winner['idol']['group'],
                           winner['idol']['name'], winner['member']))

        query = """INSERT INTO botw_winners (guild, date, idol_group, idol_name, member) 
                   VALUES ($1, $2, $3, $4, $5);"""
        await pool.executemany(query, tuples)

    async def migrate_mirrors():
        print(f'migrating {mirrors_json}')
        logger.info(f'migrating {mirrors_json}')

        with open(mirrors_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM mirrors
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'mirrors already has rows. skipping.')
            logger.info(f'mirrors already has rows. skipping.')
            return

        tuples = []
        for mirror in data:
            tuples.append((mirror['dest'], mirror['enabled'], mirror['origin'], mirror['webhook']))

        query = """INSERT INTO mirrors (destination, enabled, origin, webhook)
                   VALUES ($1, $2, $3, $4);"""
        await pool.executemany(query, tuples)

    async def migrate_reminders():
        print(f'migrating {reminders_json}')
        logger.info(f'migrating {reminders_json}')

        with open(reminders_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM reminders
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'reminders already has rows. skipping.')
            logger.info(f'reminders already has rows. skipping.')
            return

        tuples = []
        for reminder in data:
            tuples.append((reminder['content'], pendulum.from_timestamp(reminder['created']),
                           reminder['done'], pendulum.from_timestamp(reminder['due']),
                           reminder['user']))

        query = """INSERT INTO reminders (content, created, done, due, "user") 
                   VALUES ($1, $2, $3, $4, $5);"""
        await pool.executemany(query, tuples)

    async def migrate_settings():
        print(f'migrating {settings_json}')
        logger.info(f'migrating {settings_json}')

        with open(settings_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM botw_settings FULL JOIN emoji_settings ON TRUE
                                      FULL JOIN greeters ON TRUE 
                                      FULL JOIN prefixes ON TRUE
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'botw_settings, emoji_settings, greeters, prefixes already has rows. skipping.')
            logger.info(f'botw_settings, emoji_settings, greeters, prefixes already has rows. skipping.')
            return

        tuples_botw_settings = []
        tuples_emoji_settings = []
        tuples_greeters = []
        tuples_prefixes = []

        for settings in data:
            if 'botw_channel' in settings:
                tuples_botw_settings.append((settings['botw_channel'], settings['botw_enabled'],
                                             settings['botw_nominations_channel'], settings['botw_state'],
                                             settings['botw_winner_changes'] if 'botw_winner_changes' in settings
                                             else False, settings['guild']))
            if 'emoji_channel' in settings and settings['emoji_channel']:
                tuples_emoji_settings.append((settings['guild'], settings['emoji_channel']))

            if 'join_greeter' in settings and settings['join_greeter']['channel']:
                tuples_greeters.append((settings['join_greeter']['channel'], settings['guild'],
                                        settings['join_greeter']['template'], 'join'))

            if 'leave_greeter' in settings and settings['leave_greeter']['channel']:
                tuples_greeters.append((settings['leave_greeter']['channel'], settings['guild'],
                                        settings['leave_greeter']['template'], 'leave'))

            if 'prefix' in settings and settings['prefix']:
                tuples_prefixes.append((settings['guild'], settings['prefix']))

        query_botw = """INSERT INTO botw_settings (botw_channel, enabled, nominations_channel, 
                                                   state, winner_changes, guild) 
                        VALUES ($1, $2, $3, $4, $5, $6);"""
        await pool.executemany(query_botw, tuples_botw_settings)

        query_emoji = """INSERT INTO emoji_settings (guild, emoji_channel) 
                         VALUES ($1, $2);"""
        await pool.executemany(query_emoji, tuples_emoji_settings)

        query_greeters = """INSERT INTO greeters (channel, guild, template, type) 
                            VALUES ($1, $2, $3, $4);"""
        await pool.executemany(query_greeters, tuples_greeters)

        query_prefixes = """INSERT INTO prefixes (guild, prefix)
                            VALUES ($1, $2);"""
        await pool.executemany(query_prefixes, tuples_prefixes)

    async def migrate_tags():
        print(f'migrating {tags_json}')
        logger.info(f'migrating {tags_json}')

        with open(tags_json[0]) as f:
            data = json.load(f)

        query = """SELECT *
                   FROM tags
                   LIMIT 1;"""
        row = await pool.fetchval(query)
        if row:
            print(f'tags already has rows. skipping.')
            logger.info(f'tags already has rows. skipping.')
            return

        tuples = []
        for tag in data:
            in_msg = True if (tag['in_msg_trigger'] == 'true') or (tag['in_msg_trigger'] is True) else False
            tuples.append((pendulum.from_timestamp(tag['creation_date']), tag['creator'], tag['guild'],
                           in_msg, tag['reaction'], tag['trigger'], tag['use_count']))

        query = """INSERT INTO tags (date, creator, guild, in_msg, reaction, trigger, use_count) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7);"""
        await pool.executemany(query, tuples)

    if nominations_json:
        loop.run_until_complete(migrate_nominations())

    if past_winners_json:
        loop.run_until_complete(migrate_past_winners())

    if mirrors_json:
        loop.run_until_complete(migrate_mirrors())

    if reminders_json:
        loop.run_until_complete(migrate_reminders())

    if settings_json:
        loop.run_until_complete(migrate_settings())

    if tags_json:
        loop.run_until_complete(migrate_tags())


if __name__ == '__main__':
    main()
