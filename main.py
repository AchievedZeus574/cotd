import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import asyncpraw
import randoms #used for other functions 
from random import choice
import asyncio
import configparser
from datetime import date, datetime, timedelta
import re

def get_day_from_log(log_file= "CotD_Log.log"):
    try:
        with open (log_file, "r") as log:
            lines= [line.strip() for line in log if line.strip()]
            if not lines:
                return 1 #default to 1 if no log
            last_line= lines[-1]
            match= re.search (r"Day:\s*(\d+)", last_line)
            if match:
                return int(match.group(1))+1
    except FileNotFoundError:
        print(f"{log_file} not found. Starting from Day 1.")
        return 1 #Default to 1 if log doesn't exist
    except Exception as e:
        print(f"Error reading {log_file}: {e}")
        return 1 #Default to 1 on error

#load .env variables
load_dotenv()
CotD_Day= get_day_from_log()

#load config file
config= configparser.ConfigParser()
config.read('config.ini')

#get settings from config.ini
SubList= config.get("bot_settings", "SUBREDDIT_LIST", fallback="cats, cat").split(",")
CotD_CiD= int(os.getenv('TARGET_CHANNEL_ID'))
PostTime= int(config.get("bot_settings", "POST_HOUR", fallback= 12))
LogLevel = getattr(logging, config.get('bot_settings', 'LOG_LEVEL', fallback='WARNING').upper(), logging.WARNING)
AllowedRole= config.get("bot_settings", "COTD_ROLE")

#enable logging for pycord
logger = logging.getLogger('discord')
logger.setLevel(LogLevel)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

#enable logging for CotD autopost and increment counter
CotD_Log= "CotD_Log.log"
def CotD_Logging(CotDinfo):
    global CotD_Day
    with open("CotD_Log.log", "a") as log:
        log.write(f'Date: {date.today()}, Subreddit: {CotDinfo.subreddit.display_name}, Post ID: {CotDinfo.id}, Day: {CotD_Day}\n')
    CotD_Day+= 1

#grab information for async praw
reddit= asyncpraw.Reddit(
    client_id= os.getenv('REDDIT_CLIENT_ID'),
    client_secret= os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent= os.getenv('REDDIT_USER_AGENT')
)

async def fetch_subs():
    subreddit_list= []
    async for subreddit in reddit.subreddits.popular(limit= 100):
        subreddit_list.append(subreddit.display_name)
    return subreddit_list

#grab random image from reddit specified by command
async def post_grab(sub):
    try:
        subreddit= await reddit.subreddit(sub)
        posts= [
            post async for post in subreddit.hot(limit=25)
            if post.url.endswith(('.jpg', '.png', '.jpeg', '.mp4'))
        ]
        if posts:
            random_post= choice(posts)
            return random_post
        else:
            return f"No image posts found in r/{sub}."
    except Exception as e:
        return f"An error occured {str(e)}"

#post CotD in channel of choosing and log it
post_lock= asyncio.Lock()
async def Post_CotD(CiD= CotD_CiD):
    async with post_lock:
        try:
            CotD_channel= bot.get_channel(CiD)
            if CotD_channel is None:
                print("Channel not found.")
                return
            #get post from reddit and send it
            post= await post_grab(choice(SubList))
            await CotD_channel.send(f'Cat of the Day {CotD_Day}: {post.title} \n{post.url}')
            CotD_Logging(post)
        except ValueError:
            print(f'Invalid Channel ID')
        except Exception as e:
            print(f'Error: {e}')

#schedule the CotD Post to run once a day at PostTime
autopost_task= None
async def autopost():
    while True:
        now= datetime.now()
        TargetTime= now.replace(hour=PostTime, minute=0, second=0, microsecond=0)
        if now >= TargetTime:
            TargetTime+= timedelta(days= 1)
        delay= (TargetTime- now).total_seconds()
        await asyncio.sleep(delay)
        try:
            await Post_CotD()
        except Exception as e:
            logger.error(f'Error in autpost: {e}')

#create bot and get it ready on startup
bot= discord.Bot()

@bot.event
async def on_ready():
    global autopost_task
    global SUBREDDIT_LIST
    print(f'{bot.user} ready')
    await bot.sync_commands()
    SUBREDDIT_LIST = await fetch_subs()
    if autopost_task is None or autopost_task.done():
        autopost_task= bot.loop.create_task(autopost())

#commands for bot
@bot.slash_command(name="hello", description="say hi to Jeff")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey, "+ randoms.aliase()+ "!")

@bot.slash_command(name="1line", description="Spit out a random one liner")
async def one_liner(ctx: discord.ApplicationContext):
    await ctx.respond(randoms.one_line())

@bot.slash_command(name="4liase", description="Give a random aliase")
async def four_liase(ctx: discord.ApplicationContext):
    await ctx.respond(randoms.aliase())

async def subreddit_autocomplete(ctx: discord.AutocompleteContext):
    # Filter subreddit list based on the current input
    matches = [sub for sub in SUBREDDIT_LIST if ctx.value.lower() in sub.lower()]
    return matches[:25]  # Limit the suggestions to 25

@bot.slash_command(name="sub_refresh", description= "Refresh top subreddits")
async def refresh(ctx: discord.ApplicationContext):
    global SUBREDDIT_LIST
    SUBREDDIT_LIST= await fetch_subs()

@bot.slash_command(name="random", description="Grab random image from best of a SubReddit of your choosing")
async def random(
    ctx, 
    subreddit: discord.Option(str, "Enter a subreddit", autocomplete= subreddit_autocomplete)):
    await ctx.defer()
    result= await post_grab(subreddit)
    if isinstance(result, str):
        await ctx.followup.send(result)
    else:
        await ctx.followup.send(f'{result.title}\n{result.url}')

@bot.slash_command(name="triggerpost", description="Trigger posting of CotD")
#@commands.has_role(AllowedRole)
async def CotDM(ctx):
    print (f'Interaction recieved: {ctx.interaction.id}')
    await ctx.defer(ephemeral= True)
    try:
        await Post_CotD()
        await ctx.followup.send(f"Posted in <#{CotD_CiD}>")
    except discord.errors.NotFound:
        print (f'Unknown interaction: {ctx.interaction.id}')
        await ctx.followup.send ("Interaction timed out.")
    except Exception as e:
        logger.error(f"Error in /triggerpost: {e}")
        await ctx.followup.send(f"Error: {e}")

#run the bot
bot.run(os.getenv('TOKEN'))