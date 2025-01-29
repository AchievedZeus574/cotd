import discord
from discord.ext import commands
import json
from datetime import datetime

SCHEDULE_FILE = "scheduled_posts.json"

def load_schedule():
    try:
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_schedule(schedule):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=4)

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="schedule_post", description="Schedule an image post for a specific date.")
    async def schedule_post(self, ctx, image_url: str, date: str):
        """Schedule an image to be posted on a given date (YYYY-MM-DD)."""
        try:
            datetime.strptime(date, "%Y-%m-%d")  # Validate date format
        except ValueError:
            await ctx.respond("Invalid date format! Use YYYY-MM-DD.", ephemeral=True)
            return
        
        schedule = load_schedule()
        schedule[date] = image_url
        save_schedule(schedule)
        await ctx.respond(f"Scheduled image for {date}.")

    @commands.slash_command(name="remove_scheduled", description="Remove a scheduled post.")
    async def remove_scheduled(self, ctx, date: str):
        """Remove a scheduled image post by date."""
        schedule = load_schedule()
        if date in schedule:
            del schedule[date]
            save_schedule(schedule)
            await ctx.respond(f"Removed scheduled post for {date}.")
        else:
            await ctx.respond(f"No scheduled post found for {date}.", ephemeral=True)

    async def check_scheduled_post(self, channel):
        """Checks if there's a scheduled post for today and sends it."""
        today = datetime.now().strftime("%Y-%m-%d")
        schedule = load_schedule()
        if today in schedule:
            await channel.send(schedule[today])
            del schedule[today]  # Remove after posting
            save_schedule(schedule)

# Setup function for bot
async def setup(bot: commands.Bot):
    await bot.add_cog(Schedule(bot))
