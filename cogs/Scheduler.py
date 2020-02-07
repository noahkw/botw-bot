import time
import logging
import asyncio

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


def setup(bot):
    bot.add_cog(Scheduler(bot))


class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.run_jobs.start()
        # self.active_jobs = [Job('assign_winner_role', [
        #                        661348382740054036, 207955387909931009], time.time() + 5)]
        self.jobs_collection = self.bot.config['scheduler']['jobs_collection']
        self.active_jobs = []

        # self.bot.db.add(self.jobs_collection, Job('test', ['p1', 'p2'], time.time() + 0).to_dict())
        if self.bot.loop.is_running():
            asyncio.create_task(self._ainit())
        else:
            self.bot.loop.run_until_complete(self._ainit())

    async def _ainit(self):
        self.active_jobs = [
            Job.from_dict(job.to_dict()) for job in await self.bot.db.query(
                self.jobs_collection, 'exec_time', '>', time.time())
        ]

        logger.info(f'# Initial jobs from db: {len(self.active_jobs)}')

    def cog_unload(self):
        self.run_jobs.cancel()

    @tasks.loop(seconds=10.0)
    async def run_jobs(self):
        for job in self.active_jobs:
            # print(f'job.exec_time: {job.exec_time}   time.time(): {time.time()}')
            if job.exec_time < time.time():
                await getattr(self, job.func)(*job.args)
                self.active_jobs = [
                    x for x in self.active_jobs if x is not job
                ]

    @run_jobs.before_loop
    async def before_run_jobs(self):
        logger.info('Waiting until bot ready...')
        await self.bot.wait_until_ready()

    async def add_job(self, job):
        self.active_jobs.append(job)
        await self.bot.db.add(self.jobs_collection, job.to_dict())

    async def assign_winner_role(self, guild_id, winner_id):
        logger.info('Assigning winner role.')
        guild = self.bot.get_guild(guild_id)
        winner = guild.get_member(winner_id)
        botw_winner_role = discord.utils.get(
            guild.roles,
            name=self.bot.config['biasoftheweek']['winner_role_name'])
        await winner.add_roles(botw_winner_role)


class Job:
    def __init__(self, func, args, exec_time):
        self.func = func
        self.args = args
        self.exec_time = exec_time

    def __eq__(self, other):
        if not isinstance(other, Job):
            return NotImplemented
        return self.func == other.func and self.args == other.args and self.exec_time == other.exec_time

    def to_dict(self):
        return {
            'func': self.func,
            'args': self.args,
            'exec_time': self.exec_time
        }

    @staticmethod
    def from_dict(source):
        return Job(source['func'], source['args'], source['exec_time'])

    def __str__(self):
        return f'Job: {self.func} with arguments {self.args} at {self.exec_time}'
