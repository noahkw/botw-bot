import discord
from discord.ext import commands


def cmd_to_str(group=False):
    newline = "\n" if group else " "

    def actual(cmd):
        help_ = cmd.brief or cmd.help
        return f'**{cmd.name}**{newline}{help_ or "No description"}\n'

    return actual


class EmbedHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def embed(self, name=None):
        bot = self.context.bot
        heading = f" - {name}" if name else ""
        return (
            discord.Embed(description=self.get_ending_note())
            .set_author(
                name=f"{bot.user.name} Help{heading}", icon_url=bot.user.avatar_url
            )
            .set_footer(
                text=f"Made by {bot.get_user(bot.CREATOR_ID)}. Running {bot.version}."
            )
        )

    def format_help(self, text):
        return text.format(prefix=self.clean_prefix)

    async def send_cog_help(self, cog):
        name = type(cog).__name__
        await self.send_group_help(cog.bot.get_command(name.lower()))

    async def send_command_help(self, command):
        embed = self.embed(name=command.qualified_name)
        embed.add_field(
            name="Usage", value=self.get_command_signature(command), inline=False
        )
        if help_ := (command.help or command.brief):
            embed.add_field(
                name="Description", value=self.format_help(help_), inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = self.embed(name=group.qualified_name)
        embed.add_field(
            name="Usage", value=self.get_command_signature(group), inline=False
        )
        if help_ := (group.help or group.brief):
            embed.add_field(name="Description", value=help_, inline=False)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        cmds = [cmd for cmd in filtered if not isinstance(cmd, commands.Group)]

        if len(groups) > 0:
            embed.add_field(
                name="Categories",
                value=" ".join(map(cmd_to_str(group=True), groups)),
                inline=False,
            )

        embed.add_field(
            name="Subcommands", value=" ".join(map(cmd_to_str(), cmds)), inline=False
        )

        await self.get_destination().send(embed=embed)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        filtered = await self.filter_commands(bot.commands, sort=self.sort_commands)

        groups = [group for group in filtered if isinstance(group, commands.Group)]
        top_level_commands = [
            cmd for cmd in filtered if not isinstance(cmd, commands.Group)
        ]

        embed = (
            self.embed()
            .add_field(
                name="Categories",
                value=" ".join(map(cmd_to_str(group=True), groups)),
                inline=False,
            )
            .add_field(
                name="Various",
                value=" ".join(map(cmd_to_str(), top_level_commands)),
                inline=False,
            )
        )

        await self.get_destination().send(embed=embed)
