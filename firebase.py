import asyncio
import json
import time
from argparse import ArgumentParser
from configparser import ConfigParser

from DataStore import FirebaseDataStore


async def backup():
    collections = [('tags', 'tags_collection'),
                   ('reminders', 'reminders_collection'),
                   ('biasoftheweek', 'past_winners_collection'),
                   ('biasoftheweek', 'idols_collection'),
                   ('profiles', 'profiles_collection'),
                   ('settings', 'settings_collection'),
                   ('mirroring', 'mirrors_collection')]

    now = int(time.time())

    for collection in collections:
        module, coll = collection
        objs = [obj.to_dict() for obj in await db.get(config[module][coll])]
        with open(f'{module}.{coll}.{now}.backup', 'w+') as f:
            f.write(json.dumps(objs, sort_keys=True, indent=4))


def transfer_initial_tags(guild_id):
    # Transfers ALL tags to the given guild id. Only use this when migrating from a build where tags were global
    tags = db.db.collection('tags').stream()
    ids = []
    for tag in tags:
        print(tag.to_dict())
        ids.append(tag.id)

    for _id in ids:
        db.db.collection('tags').document(_id).update({'guild': guild_id})


if __name__ == '__main__':
    config = ConfigParser()
    config.read('conf.ini')
    loop = asyncio.get_event_loop()
    db = FirebaseDataStore(config['firebase']['key_file'], config['firebase']['db_name'], loop)

    parser = ArgumentParser(description='Firebase db utility script')
    parser.add_argument('operation', choices=['backup', 'transfer_all_tags'])
    args = parser.parse_args()

    if args.operation == 'backup':
        if loop.is_running():
            asyncio.create_task(backup())
        else:
            loop.run_until_complete(backup())
    elif args.operation == 'transfer_all_tags':
        transfer_initial_tags(601932891743846440)
