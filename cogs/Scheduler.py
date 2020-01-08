from discord.ext import commands, tasks
import discord
import asyncio
import time


def setup(bot):
    bot.add_cog(Scheduler(bot))


class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.run_jobs.start()
        # self.active_jobs = [Job('assign_winner_role', [
        #                        661348382740054036, 207955387909931009], time.time() + 5)]
        self.active_jobs = []

    def cog_unload(self):
        self.run_jobs.cancel()

    @tasks.loop(seconds=10.0)
    async def run_jobs(self):
        for job in self.active_jobs:
            # print(f'job.exec_time: {job.exec_time}   time.time(): {time.time()}')
            if job.exec_time < time.time():
                await getattr(self, job.func)(*job.params)
                self.active_jobs = [
                    x for x in self.active_jobs if x is not job]

    @run_jobs.before_loop
    async def before_run_jobs(self):
        print('waiting...')
        await self.bot.wait_until_ready()

    async def add_job(self, job):
        self.active_jobs.append(job)

    async def assign_winner_role(self, guild_id, winner_id):
        print('assigning')
        guild = self.bot.get_guild(guild_id)
        winner = guild.get_member(winner_id)
        botw_winner_role = discord.utils.get(
            guild.roles, name=self.bot.config['biasoftheweek']['winner_role_name'])
        await winner.add_roles(botw_winner_role)


class Job:
    def __init__(self, func, params, exec_time):
        self.func = func
        self.params = params
        self.exec_time = exec_time

    def __eq__(self, other):
        if not isinstance(other, Job):
            return NotImplemented
        return self.func == other.func and self.params == other.params and self.exec_time == other.exec_time
