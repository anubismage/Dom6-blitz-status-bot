import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
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