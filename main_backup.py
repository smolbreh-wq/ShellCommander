import os
import discord
from discord.ext import commands
import asyncio
from keep_alive import keep_alive

# ---------- CONFIG ----------
# Bot configurations: {token_env_name: prefix}
BOT_CONFIGS = {
    "TOKEN": "$",           # Main bot with $ prefix
    "TOKEN2": "!",          # Second bot with ! prefix  
    "TOKEN3": "?",          # Third bot with ? prefix
    # Add more bots as needed: "TOKEN4": "&", etc.
}

ALLOWED_USERS = [
    1096838620712804405, 1348330851263315968, 1388657253451698306  # replace with your Discord user ID (int)
    # Add more user IDs here as needed
]
MIN_DELAY = 0.5   # seconds
MAX_AMOUNT = 20

# Global variables to track spam tasks and stop flags for all bots
spam_tasks = {}
stop_flags = {}
bots = {}
emergency_stop = False
# ---------------------------

def create_bot(prefix: str, bot_name: str):
    """Create a bot instance with the given prefix"""
    bot = commands.Bot(command_prefix=prefix)
    
    @bot.event
    async def on_ready():
        print(f"✅ {bot_name} logged in as {bot.user} (ID: {bot.user.id})")
        print(f"Bot is ready and listening for commands with prefix '{prefix}'")
        print(f"Authorized users: {ALLOWED_USERS}")

    @bot.check
    async def is_allowed(ctx):
        """Global check to ensure only authorized users can use bot commands"""
        is_authorized = ctx.author.id in ALLOWED_USERS
        # Silently ignore unauthorized users - no response message
        return is_authorized

    @bot.command()
    async def send(ctx, message: str, delay: float, amount: int):
        """
        Send a message multiple times with a specified delay between each message.
        
        Usage: {prefix}send [message] [delay] [amount]
        Example: {prefix}send "Hello World" 1.0 5
        
        Parameters:
        - message: The message to send (use quotes for multi-word messages)
        - delay: Delay in seconds between messages (minimum 0.5 seconds)
        - amount: Number of times to send the message (1-20)
        """
        try:
            # Validate delay parameter
            if delay < MIN_DELAY:
                try:
                    await ctx.author.send(f"⚠️ Delay must be at least {MIN_DELAY} seconds to prevent rate limiting.")
                except:
                    pass
                return
            
            # Validate amount parameter
            if amount < 1 or amount > MAX_AMOUNT:
                try:
                    await ctx.author.send(f"⚠️ Amount must be between 1 and {MAX_AMOUNT} messages.")
                except:
                    pass
                return
            
            # Validate message length (Discord has a 2000 character limit)
            if len(message) > 2000:
                try:
                    await ctx.author.send("⚠️ Message is too long. Discord messages must be 2000 characters or less.")
                except:
                    pass
                return

            # Delete the invoking command message to keep chat clean
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            except Exception:
                pass

            # Create a stop flag for this user
            user_id = ctx.author.id
            stop_flags[user_id] = False
            
            # Send the repeated messages
            for i in range(amount):
                # Check if user requested to stop or emergency stop activated
                if stop_flags.get(user_id, False) or emergency_stop:
                    # Send stop notification to user's DM
                    try:
                        if emergency_stop:
                            await ctx.author.send(f"🚨 Emergency stop activated. Message sending stopped after {i} messages.")
                        else:
                            await ctx.author.send(f"🛑 Message sending stopped after {i} messages.")
                    except:
                        pass
                    break
                    
                try:
                    await ctx.send(message)
                    # Don't sleep after the last message
                    if i < amount - 1:
                        await asyncio.sleep(delay)
                except discord.HTTPException as e:
                    # Send error to user's DM
                    try:
                        await ctx.author.send(f"⚠️ Discord API error occurred: {e}")
                    except:
                        pass
                    break
                except Exception as e:
                    # Send error to user's DM
                    try:
                        await ctx.author.send(f"⚠️ Unexpected error occurred: {e}")
                    except:
                        pass
                    break
            
            # Clean up the stop flag
            stop_flags.pop(user_id, None)

        except ValueError:
            try:
                await ctx.author.send(f"⚠️ Invalid parameters. Please use: `{prefix}send [message] [delay] [amount]`\nExample: `{prefix}send \"Hello\" 1.0 5`")
            except:
                pass
        except Exception as e:
            try:
                await ctx.author.send(f"⚠️ Error processing command: {e}")
            except:
                pass

    @bot.command()
    async def stop(ctx):
        """
        Stop any ongoing message sending for the user.
        
        Usage: {prefix}stop
        """
        user_id = ctx.author.id
        
        # Stop regular send command
        if user_id in stop_flags:
            stop_flags[user_id] = True
            try:
                await ctx.author.send("🛑 Stopping message sending...")
            except:
                pass
        
        # Stop spam command for this specific bot
        spam_key = f"{prefix}_{user_id}"
        if spam_key in spam_tasks:
            spam_tasks[spam_key].cancel()
            spam_tasks.pop(spam_key, None)
            try:
                await ctx.author.send(f"🛑 Spam sending stopped on {prefix} bot.")
            except:
                pass
        
        if user_id not in stop_flags and spam_key not in spam_tasks:
            try:
                await ctx.author.send(f"ℹ️ No active message sending to stop on {prefix} bot.")
            except:
                pass

    async def spam_loop(ctx, message: str, delay: float):
        """Continuous spam loop that can be stopped"""
        global emergency_stop
        count = 0
        try:
            while True:
                if emergency_stop:
                    try:
                        await ctx.author.send(f"🚨 Emergency stop activated. Spam stopped after {count} messages.")
                    except:
                        pass
                    break
                await ctx.send(message)
                count += 1
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            try:
                await ctx.author.send(f"🛑 Spam stopped after {count} messages.")
            except:
                pass
            raise

    @bot.command()
    async def spm(ctx, action: str, message: str = None, delay: float = 1.0):
        """
        Continuous spam command with start/stop functionality.
        
        Usage: {prefix}spm start [message] [delay]
               {prefix}spm stop
        
        Examples:
        {prefix}spm start "Hello" 1.0
        {prefix}spm stop
        """
        user_id = ctx.author.id
        
        if action.lower() == "start":
            if not message:
                try:
                    await ctx.author.send(f"⚠️ Please provide a message to spam.\nUsage: `{prefix}spm start \"message\" [delay]`")
                except:
                    pass
                return
                
            if delay < MIN_DELAY:
                try:
                    await ctx.author.send(f"⚠️ Delay must be at least {MIN_DELAY} seconds.")
                except:
                    pass
                return
            
            # Create unique key for this bot and user combination
            spam_key = f"{prefix}_{user_id}"
            
            # Stop any existing spam for this user on this specific bot
            if spam_key in spam_tasks:
                spam_tasks[spam_key].cancel()
                spam_tasks.pop(spam_key, None)
            
            # Delete the command message
            try:
                await ctx.message.delete()
            except Exception:
                pass
            
            # Start the spam task - notify user via DM
            try:
                await ctx.author.send(f"🚀 Starting spam on {prefix} bot: '{message}' with {delay}s delay. Use `{prefix}stop` or `{prefix}spm stop` to stop.")
            except:
                pass
            
            task = asyncio.create_task(spam_loop(ctx, message, delay))
            spam_tasks[spam_key] = task
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            finally:
                spam_tasks.pop(spam_key, None)
        
        elif action.lower() == "stop":
            spam_key = f"{prefix}_{user_id}"
            if spam_key in spam_tasks:
                spam_tasks[spam_key].cancel()
                spam_tasks.pop(spam_key, None)
                try:
                    await ctx.author.send(f"🛑 Spam stopped on {prefix} bot.")
                except:
                    pass
            else:
                try:
                    await ctx.author.send(f"ℹ️ No active spam to stop on {prefix} bot.")
                except:
                    pass
        
        else:
            try:
                await ctx.author.send(f"⚠️ Invalid action. Use `start` or `stop`.\nExample: `{prefix}spm start \"message\" 1.0`")
            except:
                pass

    @bot.command()
    async def help_bot(ctx):
        """Display help information about bot commands"""
        help_message = f"""🤖 **Discord Bot Help** (Prefix: {prefix})
Available commands for authorized users:

**`{prefix}send [message] [delay] [amount]`**
Send a message multiple times with delay
• message: Text to send (use quotes for spaces)
• delay: Seconds between messages (min {MIN_DELAY})
• amount: Number of repetitions (max {MAX_AMOUNT})
Example: `{prefix}send "Hello World" 1.0 3`

**`{prefix}spm start [message] [delay]`**
Start continuous spam (infinite messages until stopped)
• message: Text to spam (use quotes for spaces)
• delay: Seconds between messages (min {MIN_DELAY})
Example: `{prefix}spm start "Spam message" 0.5`

**`{prefix}spm stop`**
Stop continuous spam

**`{prefix}stop`**
Stop any active message sending (works for both send and spm)

**`>stopall`**
🚨 EMERGENCY STOP - Immediately stops ALL bots and commands
(Works with any bot, uses > prefix instead of {prefix})

**Safety Features**
• Minimum delay: {MIN_DELAY} seconds
• User authorization required
• Individual stop controls per user
• Emergency stop for all bots
• Automatic command cleanup

Bot is running 24/7 on Replit with keep-alive monitoring"""
        
        await ctx.send(help_message)

    @bot.event
    async def on_message(message):
        """Handle emergency stopall command and regular commands"""
        global emergency_stop
        
        # Check for emergency stopall command
        if message.content == ">stopall" and message.author.id in ALLOWED_USERS:
            emergency_stop = True
            
            # Cancel all active spam tasks
            for spam_key, task in list(spam_tasks.items()):
                task.cancel()
                spam_tasks.pop(spam_key, None)
            
            # Set all stop flags
            for user_id in list(stop_flags.keys()):
                stop_flags[user_id] = True
            
            try:
                await message.author.send("🚨 EMERGENCY STOP ACTIVATED - All bots stopped!")
            except:
                pass
            
            # Reset emergency stop after a brief moment to allow for new commands
            await asyncio.sleep(1)
            emergency_stop = False
            return
        
        # Process normal commands
        await bot.process_commands(message)

    @bot.event
    async def on_command_error(ctx, error):
        """Handle command errors gracefully"""
        if isinstance(error, commands.CheckFailure):
            # Silently ignore authorization failures - no response to unauthorized users
            return
        elif isinstance(error, commands.CommandNotFound):
            # Only respond to command not found if user is authorized
            if ctx.author.id in ALLOWED_USERS:
                try:
                    await ctx.author.send(f"⚠️ Unknown command. Use `{prefix}help_bot` for available commands.")
                except:
                    pass
        elif isinstance(error, commands.MissingRequiredArgument):
            # Only respond to missing arguments if user is authorized
            if ctx.author.id in ALLOWED_USERS:
                try:
                    await ctx.author.send(f"⚠️ Missing required arguments. Use `{prefix}help_bot` for command usage.")
                except:
                    pass
        elif isinstance(error, commands.BadArgument):
            # Only respond to bad arguments if user is authorized
            if ctx.author.id in ALLOWED_USERS:
                try:
                    await ctx.author.send(f"⚠️ Invalid argument type. Use `{prefix}help_bot` for command usage.")
                except:
                    pass
        else:
            # Only respond to general errors if user is authorized
            if ctx.author.id in ALLOWED_USERS:
                try:
                    await ctx.author.send(f"⚠️ An error occurred: {error}")
                except:
                    pass
            print(f"Unhandled error in {bot_name}: {error}")

    return bot

async def run_multiple_bots():
    """Run multiple bot instances simultaneously"""
    print("🤖 Discord Multi-Bot System Starting...")
    print("=" * 50)
    
    # Check which tokens are available
    print("Configured bots:")
    available_tokens = []
    for token_env, prefix in BOT_CONFIGS.items():
        token = os.getenv(token_env)
        if token:
            print(f"  {prefix} prefix - {token_env}: ✅ Ready")
            available_tokens.append((token_env, prefix, token))
        else:
            print(f"  {prefix} prefix - {token_env}: ❌ Missing")
    
    print("=" * 50)
    
    if not available_tokens:
        print("❌ No valid tokens found! Please add TOKEN environment variables.")
        return
    
    # Start keep_alive server
    keep_alive()
    
    # Create and start all available bots
    tasks = []
    for token_env, prefix, token in available_tokens:
        bot_name = f"Bot-{prefix}"
        print(f"🚀 Starting bot with prefix '{prefix}' using {token_env}")
        
        bot = create_bot(prefix, bot_name)
        bots[prefix] = bot
        
        # Start each bot as a separate task
        task = asyncio.create_task(bot.start(token))
        tasks.append(task)
    
    # Skip missing tokens
    for token_env, prefix in BOT_CONFIGS.items():
        if not os.getenv(token_env):
            print(f"⚠️ {token_env} not found in environment variables, skipping bot with prefix '{prefix}'")
    
    # Wait for all bots to run
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"❌ Error running bots: {e}")

if __name__ == "__main__":
    asyncio.run(run_multiple_bots())