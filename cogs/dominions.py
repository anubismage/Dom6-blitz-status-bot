import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from status.capture_status import extract_status_data

# Here we name the cog and create a new class for the cog.
class Dominions(commands.Cog, name="dominions"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.watch_tasks = {}
        self.current_status = {}

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
                    
                    players_status = "\n".join([f"{status_emojis.get(player.get('status', 'Unknown').lower(), ':question:')}: {player.get('nation_name', 'Unknown')}" for player in players_data])
                    embed.add_field(name="**Players**", value=players_status, inline=False)
                else:
                    embed = discord.Embed(
                        title="Error!",
                        description="There is something wrong with the API, please try again later",
                        color=0xE02B2B,
                    )
                await context.send(embed=embed)

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
                            
                            status_emojis = {
                                "submitted": ":ballot_box_with_check:",
                                "unsubmitted": ":x:",
                                "computer": ":desktop:",
                                "unfinished": ":warning:",
                                "dead": ":headstone:"
                            }
                            
                            players_status = "\n".join([f"{status_emojis.get(player.get('status', 'Unknown').lower(), ':question:')}: {player.get('nation_name', 'Unknown')}" for player in players_data])
                            embed.add_field(name="**Players**", value=players_status, inline=False)
                            await context.send(content="@here", embed=embed)
                    await asyncio.sleep(180)  # Wait for 3 minutes

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

# And then we finally add the cog to the bot so that it can load, unload, reload and use its content.
async def setup(bot) -> None:
    await bot.add_cog(Dominions(bot))
