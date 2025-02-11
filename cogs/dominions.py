import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from status.capture_status import extract_status_data

# Here we name the cog and create a new class for the cog.

class PlayerSelectView(discord.ui.View):
    def __init__(self, bot, game_id, nation_name, guild):
        super().__init__()
        self.bot = bot
        self.game_id = game_id
        self.nation_name = nation_name

        # Create the select menu
        select = discord.ui.Select(
            placeholder="Select a player",
            min_values=1,
            max_values=1,
            options=[
                        discord.SelectOption(
                            label=member.display_name,
                            value=str(member.id),
                            description=f"@{member.name}"
                        ) for member in guild.members if not member.bot
                    ][:25]  # Discord has a limit of 25 options
        )

        async def select_callback(interaction: discord.Interaction):
            user_id = select.values[0]
            user = interaction.guild.get_member(int(user_id))

            # Get the Dominions cog instance
            dominions_cog = self.bot.get_cog('dominions')
            if dominions_cog is None:
                await interaction.response.send_message(
                    "Error: Could not access registration system.",
                    ephemeral=True
                )
                return

            # Register the player
            if self.game_id not in dominions_cog.registered_players:
                dominions_cog.registered_players[self.game_id] = {}
            dominions_cog.registered_players[self.game_id][self.nation_name] = user.mention

            # Send confirmation embed
            confirm_embed = discord.Embed(
                title="Registration Successful!",
                color=0x2ecc71
            )
            confirm_embed.add_field(name="Game ID", value=self.game_id, inline=True)
            confirm_embed.add_field(name="Nation", value=self.nation_name, inline=True)
            confirm_embed.add_field(name="Player", value=user.mention, inline=True)

            await interaction.response.edit_message(
                content="Registration complete!",
                embed=confirm_embed,
                view=None
            )

        select.callback = select_callback
        self.add_item(select)

class Dominions(commands.Cog, name="dominions"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.watch_tasks = {}
        self.current_status = {}
        self.registered_players = {}
        self.custom_turn_message = "Your Game is ready for the next turn pretenders!"

    # Here you can just add your own commands, you'll always need to provide "self" as first parameter.

    @commands.hybrid_command(
        name="details",
        description="Fetches the status of a Dominions game by ID.",
    )
    async def details(self, context: Context, game_id: str) -> None:
        """
        Fetches the status of a Dominions game by ID.

        :param context: The application command context.
        :param game_id: The ID of the Dominions game.
        """
        async with aiohttp.ClientSession() as session:
            url = f"https://beta.blitzserver.net/game/{game_id}#status"
            async with session.get(url) as request:
                if request.status == 200:
                    data = await request.text()
                    lobby_name, players_data, game_info = extract_status_data(data)
                    
                    embed = discord.Embed(title=f'Lobby: {lobby_name}', color=0xD75BF4)
                    if 'status' in game_info:
                        embed.add_field(name="Game Status", value=game_info['status'], inline=False)
                    if 'address' in game_info:
                        embed.add_field(name="Game Address", value=game_info['address'], inline=False)
                    if 'next_turn' in game_info:
                        embed.add_field(name="Next Turn", value=game_info['next_turn'], inline=False)
                    
                    status_emojis = {
                        "submitted": ":ballot_box_with_check:",
                        "unsubmitted": ":x:",
                        "computer": ":desktop:",
                        "unfinished": ":warning:",
                        "dead": ":headstone:"
                    }
                    
                    players_status = "\n".join([f"{status_emojis.get(player.get('status', 'Unknown').lower(), ':question:')}: {player.get('nation_name', 'Unknown')} {self.registered_players.get(game_id, {}).get(player.get('nation_name', 'Unknown'), '')}" for player in players_data])
                    embed.add_field(name="**Players**", value=players_status, inline=False)
                else:
                    embed = discord.Embed(
                        title="Error!",
                        description="There is something wrong with the API, please try again later",
                        color=0xE02B2B,
                    )
                await context.send(embed=embed)



    class RegistrationModal(discord.ui.Modal):
        def __init__(self, bot) -> None:
            super().__init__(title="Dominions Player Registration")
            self.bot = bot

            self.game_id = discord.ui.TextInput(
                label="Game ID",
                placeholder="Enter the game ID (e.g., 123456)",
                min_length=1,
                max_length=10,
                required=True
            )
            self.add_item(self.game_id)

            self.nation_name = discord.ui.TextInput(
                label="Nation Name",
                placeholder="Enter your nation name (e.g., Ulm)",
                min_length=1,
                max_length=50,
                required=True
            )
            self.add_item(self.nation_name)

        async def on_submit(self, interaction: discord.Interaction):
            # Create the select menu view
            view = PlayerSelectView(
                self.bot,
                self.game_id.value,
                self.nation_name.value,
                interaction.guild
            )
            await interaction.response.send_message(
                "Please select the player:",
                view=view,
                ephemeral=True
            )

    @commands.hybrid_command(
        name="register",
        description="Opens a registration form for a Dominions game player.",
    )
    async def register(self, context: Context) -> None:
        """
        Opens a modal registration form for a Dominions game player.
        
        :param context: The application command context.
        """
        if context.interaction:
            modal = self.RegistrationModal(self.bot)
            await context.interaction.response.send_modal(modal)
        else:
            # For text command, send a message directing users to use slash command
            await context.send("Please use the slash command `/register` to open the registration form.")

    @commands.hybrid_command(
        name="watch",
        description="Watches the status of a Dominions game by ID.",
    )
    async def watch(self, context: Context, game_id: str) -> None:
        """
        Watches the status of a Dominions game by ID.

        :param context: The application command context.
        :param game_id: The ID of the Dominions game.
        """
        if game_id in self.watch_tasks:
            await context.send(f"Already watching game {game_id}.")
            return

        async def watch_task():
            async with aiohttp.ClientSession() as session:
                url = f"https://beta.blitzserver.net/game/{game_id}#status"
                while True:
                    async with session.get(url) as request:
                        if request.status != 200:
                            await context.send(f"Stopped watching game {game_id} due to request error.")
                            break
                        data = await request.text()
                        lobby_name, players_data, game_info = extract_status_data(data)
                        new_status = game_info.get('status', 'Unknown')
                        if new_status == 'Unknown' or 'Won' in new_status:
                            await context.send(f"Stopped watching game {game_id} due to game status: {new_status}.")
                            break
                        if game_id not in self.current_status:
                            self.current_status[game_id] = new_status
                        if new_status != self.current_status[game_id]:
                            self.current_status[game_id] = new_status
                            embed = discord.Embed(title=f'Lobby: {lobby_name}', color=0xD75BF4)
                            embed.add_field(name="Game Status", value=new_status, inline=False)
                            if 'address' in game_info:
                                embed.add_field(name="Game Address", value=game_info['address'], inline=False)
                            if 'next_turn' in game_info:
                                embed.add_field(name="Next Turn", value=game_info['next_turn'], inline=False)
                        
                            # Get the mentions of registered players
                            mentions = " ".join([mention for nation, mention in self.registered_players.get(game_id, {}).items()])
                            if not mentions:
                                mentions = "@here"
                            await context.send(content=self.custom_turn_message + mentions, embed=embed)
                    await asyncio.sleep(60)

        task = self.bot.loop.create_task(watch_task())
        self.watch_tasks[game_id] = task
        await context.send(f"Started watching game {game_id}.")

    @commands.hybrid_command(
        name="unwatch",
        description="Stops watching the status of a Dominions game by ID.",
    )
    async def unwatch(self, context: Context, game_id: str) -> None:
        """
        Stops watching the status of a Dominions game by ID.

        :param context: The application command context.
        :param game_id: The ID of the Dominions game.
        """
        task = self.watch_tasks.pop(game_id, None)
        if task:
            task.cancel()
            self.current_status.pop(game_id, None)
            await context.send(f"Stopped watching game {game_id}.")
        else:
            await context.send(f"Not watching game {game_id}.")
        
    @commands.hybrid_command(
    name="turn_message",
    description="Sets a custom turn message for a Dominions game by ID.",
    with_app_command=True
    )
    async def turn_message(self, context: Context, message: str) -> None:
        """
        Sets a custom turn message for a Dominions game
        :param context: The application command context.

        :param message: The custom turn message.
        """
        self.custom_turn_message = message
        await context.send(f"Custom turn message set to: {message}")


# And then we finally add the cog to the bot so that it can load, unload, reload and use its content.
async def setup(bot) -> None:
    await bot.add_cog(Dominions(bot))
