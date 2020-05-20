# botw-bot
Originally a Discord bot for organizing * of the week challenges, now more of a general purpose bot.

Current modules:
- Bias of the Week
- Emoji utilities
- Tags
- Trolling
- Utilities
- Wolfram Alpha

For an overview of all commands inside each module, see https://github.com/noahkw/botw-bot/wiki.

## Setup (docker)
Clone the repo: `git clone git@github.com:noahkw/botw-bot.git` 

Pull the docker image: `docker pull docker.pkg.github.com/noahkw/botw-bot/botw-bot:latest`

Rename `conf.ini.sample` to `conf.ini` and change it to according to your use case.
Most of the defaults should be fine, but make sure to enter your **token**, **server id** for the whitelist, **Wolfram Alpha app id**, and the path to your **firebase key file**.

Start the bot as a daemon: `docker-compose up -d`
