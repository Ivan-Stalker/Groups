import asyncio
import logging
import time
import os
import random
from datetime import datetime
from telethon import TelegramClient, errors
import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_result(group_url, status, error_msg=""):
    timestamp = datetime.now().strftime("%H:%M")
    with open("logs.txt", "a", encoding='utf-8') as f:
        f.write(f"{timestamp} {group_url} {status} {error_msg}\n")

async def send_message_to_group(client, group_url, message_text):
    try:
        # Get entity directly from the link/username
        await client.send_message(group_url, message_text)
        logging.info(f"Successfully sent message to {group_url}")
        log_result(group_url, "OK")
    except errors.FloodWaitError as e:
        logging.error(f"FloodWaitError: Must wait for {e.seconds} seconds")
        log_result(group_url, "ERROR", f"FloodWait ({e.seconds}s)")
        raise e # Re-raise to trigger the 1-hour wait logic
    except Exception as e:
        logging.error(f"Failed to send message to {group_url}: {e}")
        log_result(group_url, "ERROR", str(e))

async def mailing_cycle(client, groups, message_text):
    while True:
        try:
            # Ensure client is connected before sending
            if not client.is_connected():
                logging.info("Client disconnected. Attempting to reconnect...")
                await client.connect()
                logging.info("Reconnected successfully.")

            logging.info("Starting new mailing cycle...")
            tasks = []
            for group in groups:
                tasks.append(send_message_to_group(client, group.strip(), message_text))
            
            # Send simultaneously to all groups
            await asyncio.gather(*tasks)
            
            # Random wait between 30 seconds and 3 minutes (180s)
            wait_time = random.randint(30, 180)
            logging.info(f"Cycle complete. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            
        except (errors.FloodWaitError, errors.RPCError, ConnectionError) as e:
            logging.error(f"Critical error encountered: {e}. Stopping for 1 hour.")
            await asyncio.sleep(3600)  # Wait 1 hour as per TZ
            logging.info("Restarting mailing cycle after 1 hour wait.")
            # Try to reconnect after the long wait
            try:
                if not client.is_connected():
                    await client.connect()
            except Exception as re_e:
                logging.error(f"Failed to reconnect after pause: {re_e}")
                
        except Exception as e:
            if "disconnected" in str(e).lower():
                logging.error(f"Connection lost: {e}. Waiting 60 seconds before reconnection attempt.")
            else:
                logging.error(f"Unexpected error: {e}. Waiting 60 seconds before retry.")
            await asyncio.sleep(60)

async def main():
    if not os.path.exists("groups.txt"):
        logging.error("groups.txt not found!")
        return
    if not os.path.exists("message.txt"):
        logging.error("message.txt not found!")
        return

    with open("groups.txt", "r", encoding='utf-8') as f:
        groups = [line.strip() for line in f if line.strip()]

    with open("message.txt", "r", encoding='utf-8') as f:
        message_text = f.read().strip()

    if not groups:
        logging.error("No groups found in groups.txt")
        return

    client = TelegramClient('anon_session', config.API_ID, config.API_HASH)

    try:
        await client.start()
        logging.info("Telegram client started successfully.")
        await mailing_cycle(client, groups, message_text)
    except Exception as e:
        logging.error(f"Failed to start Telegram client: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
