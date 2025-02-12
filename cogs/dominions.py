import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from status.capture_status import extract_status_data
from views.PlayerSelectView import PlayerSelectView
import os
import json
from datetime import datetime
# Here we name the cog and create a new class for the cog.

class Dominions(commands.Cog, name="dominions"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.data_folder = "data"
        # Create data folder if it doesn't exist
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        # Load saved data
        self.watch_tasks = {}  # Can't load tasks directly
        self.current_status = self.load_dict("current_status.json")
        self.registered_players = self.load_dict("registered_players.json")
        self.custom_turn_message = "Your Game is ready for the next turn pretenders!"
        
        # Start auto-save task
        self.auto_save.start()

    def save_dict(self, data: dict, filename: str) -> None:
        """Save dictionary to a JSON file."""
        filepath = os.path.join(self.data_folder, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving {filename}: {str(e)}")

    def load_dict(self, filename: str) -> dict:
        """Load dictionary from a JSON file."""
        filepath = os.path.join(self.data_folder, filename)
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding {filename}, starting with empty dict")
            return {}

    def save_all_data(self):
        """Save all dictionaries to disk."""
        # Don't save watch_tasks as they can't be serialized
        self.save_dict(self.current_status, "current_status.json")
        self.save_dict(self.registered_players, "registered_players.json")
        print(f"Data auto-saved at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    @tasks.loop(minutes=5)
    async def auto_save(self):
        """Auto-save task that runs every 5 minutes."""
        self.save_all_data()

    def cog_unload(self):
        """Called when the cog is unloaded."""
        self.auto_save.cancel()
        self.save_all_data()  # Save one last time when unloading

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
                        "dead": ":headstone:",
                        "Unknown": ":question:",
                        "remove pretender": ":skull:"
                    }
                    
                    # Count players by status
                    status_counts = {
                        "submitted": 0,
                        "unsubmitted": 0,
                        "computer": 0,
                        "unfinished": 0,
                        "dead": 0
                    }

                    # Create player list excluding computer and dead nations
                    player_list = []
                    for player in players_data:
                        status = player.get('status', 'Unknown').lower()
                        status_counts[status] = status_counts.get(status, 0) + 1
                        
                        # Only add to player list if not computer or dead
                        if status not in ['computer', 'dead']:
                            nation_name = player.get('nation_name', 'Unknown')
                            player_mention = self.registered_players.get(game_id, {}).get(nation_name, '')
                            player_list.append(f"{status_emojis.get(status, ':question:')} {nation_name} {player_mention}")

                    # Create status summary
                    status_summary = []
                    for status, count in status_counts.items():
                        if count > 0:
                            status_summary.append(f"{status_emojis[status]} {count}")
                    
                    embed.add_field(name="**Status Summary**", value=" | ".join(status_summary), inline=False)
                    
                    if player_list:
                        embed.add_field(name="**Active Players**", value="\n".join(player_list), inline=False)
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
                            self.watch_tasks.pop(game_id, None)
                            self.current_status.pop(game_id, None)
                            break
                        data = await request.text()
                        lobby_name, players_data, game_info = extract_status_data(data)
                        new_status = game_info.get('status', 'Unknown')
                        if new_status == 'Unknown' or 'Won' in new_status:
                            await context.send(f"Stopped watching game {game_id} due to game status: {new_status}.")
                            self.watch_tasks.pop(game_id, None)
                            self.current_status.pop(game_id, None)
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

    @commands.hybrid_command(
        name="show_watching",
        description="Shows a list of games currently being watched.",
    )
    async def show_watching(self, context: Context) -> None:
        """
        Shows a list of games currently being watched.

        :param context: The application command context.
        """
        if not self.watch_tasks:
            await context.send("No games are currently being watched.")
            return

        embed = discord.Embed(
            title="Currently Watched Games",
            color=0xD75BF4,
            description="\n".join([f"• Game ID: {game_id}" for game_id in self.watch_tasks.keys()])
        )
        await context.send(embed=embed)


# And then we finally add the cog to the bot so that it can load, unload, reload and use its content.
async def setup(bot) -> None:
    await bot.add_cog(Dominions(bot))
