# botw-bot  ![Docker](https://github.com/noahkw/botw-bot/workflows/Docker/badge.svg?branch=master)
Originally a Discord bot for organizing * of the week challenges, now more of a general purpose bot.

Current modules:
- Bias of the Week
- Card game utilities
- Emoji utilities
- Fun
- Gfycat
- Greeters
- Instagram
- Main
- Mirroring
- Profiles
- Reminders
- Roles
- Tags
- Trolling
- Url shortener
- Utilities
- Weather
- Wolfram Alpha

For an overview of all commands inside each module, see https://github.com/noahkw/botw-bot/wiki.

## Setup (docker)
Clone the repo: `git clone git@github.com:noahkw/botw-bot.git`.

Pull the docker image: `docker pull docker.pkg.github.com/noahkw/botw-bot/botw-bot:latest`.

Then create a *.env* file in the directory next to the *docker-compose.yml*.
An example *.env* might look as follows:

```
BOTW_BOT_CLONE_DIR=/opt/botw-bot
BOTW_BOT_PG_DATA_DIR=/opt/botw-botw-pg
BOTW_BOT_PG_PW=PW_HERE
```

- *BOTW_BOT_CLONE_DIR* should be the absolute path of the directory that you cloned this repository to
- *BOTW_BOT_PG_DATA_DIR* should point to the directory where the postgres container will store its data
- *BOTW_BOT_PG_PW* is the password used to authenticate with the postgres instance

Rename `config.yml.sample` to `config.yml` and change it according to your use case.
Most of the defaults should be fine, but make sure to enter your **discord token**,
**database connection string** (use the same password as in the *.env* file you just created),
**Wolfram Alpha app id**, **OpenWeatherMap app id**, **Instagram cookie file path**,
**Gfycat client id and secret**, and your **bit.ly access token**.

Start the bot as a daemon: `docker-compose up -d`.
