# botw-bot  ![Docker](https://github.com/noahkw/botw-bot/workflows/Docker/badge.svg?branch=master)
Originally a Discord bot for organizing * of the week challenges, now more of a general purpose bot.

Current modules:
- Bias of the Week
- Emoji utilities
- Fun
- Gfycat
- Instagram
- Mirroring
- Profiles
- Reminders
- Settings
- Tags
- Trolling
- Utilities
- Weather
- Wolfram Alpha

For an overview of all commands inside each module, see https://github.com/noahkw/botw-bot/wiki.

## Setup (docker)
Clone the repo: `git clone git@github.com:noahkw/botw-bot.git`

Pull the docker image: `docker pull docker.pkg.github.com/noahkw/botw-bot/botw-bot:latest`

Rename `conf.ini.sample` to `conf.ini` and change it according to your use case.
Most of the defaults should be fine, but make sure to enter your **token**,
**server id** for the whitelist, **Wolfram Alpha app id**, **OpenWeatherMap app id**,
**Instagram cookie file path**, **Gfycat client id and secret**,
and the path to your **firebase key file**.

Replace `{CLONE_DIR}` with the absolute path of the cloned repo in `docker-compose.yml`.

Start the bot as a daemon: `docker-compose up -d`
