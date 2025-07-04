#!/usr/bin/env python3
"""
pip3 install garth requests garminconnect

export EMAIL=<your garmin email>
export PASSWORD=<your garmin password>

"""
import datetime
import json
import logging
import os
import base64
from openai import OpenAI
from getpass import getpass

import requests
from garth.exc import GarthHTTPError

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from dotenv import load_dotenv

from notion_client import Client

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables if defined
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PG_ID = os.getenv("PG_ID")
DB_ID = os.getenv("DB_ID")
email = os.getenv("EMAIL")
password = os.getenv("PASSWORD")
tokenstore = os.getenv("GARMINTOKENS") or "~/.garminconnect"
tokenstore_base64 = os.getenv("GARMINTOKENS_BASE64") or "~/.garminconnect_base64"
api = None

clientOpenai = OpenAI()


def write_text(client, PG_ID, text, type):
    client.blocks.children.append(
        block_id=PG_ID,
        children=[
            {
                "object": "block",
                "type": type,
                type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": text
                            }
                        }]
                }
            }
        ]
    )


def write_row(client, database_id, effect, date, distance, steps, sleep):
    client.pages.create(
        **{
            "parent": {
                "database_id": database_id
            },
            "properties": {
                "effect": {'title': [{'text': {'content': effect}}]},
                "date": {'date': {'start': date}},
                "steps": {'number': steps},
                "distance": {'number': distance},
                "sleep": {'number': sleep}
            }
        }
    )


def get_credentials():
    """Get user credentials."""

    email = input("Login e-mail: ")
    password = getpass("Enter password: ")

    return email, password


def save_tokens_to_env(garmin):
    """Save tokens to environment variable as base64."""
    try:
        # Get token data
        token_data = garmin.garth.dumps()
        # Encode to base64
        token_base64 = base64.b64encode(token_data.encode()).decode()
        # In a real deployment, you'd want to save this securely
        # For now, we'll just log it (remove in production)
        logger.info("Tokens saved (would be stored in environment)")
        return token_base64
    except Exception as e:
        logger.error(f"Failed to save tokens: {e}")
        return None


def load_tokens_from_env():
    """Load tokens from environment variable."""
    try:
        token_base64 = os.getenv("GARMINTOKENS_BASE64")
        if not token_base64:
            return None
        
        # Decode from base64
        token_data = base64.b64decode(token_base64).decode()
        return token_data
    except Exception as e:
        logger.error(f"Failed to load tokens from environment: {e}")
        return None


def init_api(email, password):
    """Initialize Garmin API with your credentials."""

    try:
        # First try to load tokens from environment (for serverless)
        token_data = load_tokens_from_env()
        if token_data:
            print("Trying to login using tokens from environment...")
            garmin = Garmin()
            garmin.garth.loads(token_data)
            # Test the token
            try:
                garmin.get_user_profile()
                return garmin
            except Exception as e:
                logger.warning(f"Stored tokens expired: {e}")
        
        # Fallback to file-based tokens
        print(
            f"Trying to login to Garmin Connect using token data from "
            f"directory '{tokenstore}'..."
        )
        garmin = Garmin()
        garmin.login(tokenstore)

    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        # Session is expired. You'll need to log in again
        print(
            "Login tokens not present, login with your Garmin Connect "
            "credentials to generate them.\n"
            f"They will be stored in '{tokenstore}' for future use.\n"
        )
        try:
            # Ask for credentials if not set as environment variables
            if not email or not password:
                email, password = get_credentials()

            garmin = Garmin(
                email=email, password=password, is_cn=False, return_on_mfa=True
            )
            result1, result2 = garmin.login()
            if result1 == "needs_mfa":  # MFA is required
                mfa_code = input("MFA one-time code: ")
                garmin.resume_login(result2, mfa_code)

            # Save Oauth1 and Oauth2 token files to directory for next login
            garmin.garth.dump(tokenstore)
            print(
                f"Oauth tokens stored in '{tokenstore}' directory "
                f"for future use.\n"
            )
            
            # Also save to environment format
            save_tokens_to_env(garmin)

            # Re-login Garmin API with tokens
            garmin.login(tokenstore)
        except (
            FileNotFoundError,
            GarthHTTPError,
            GarminConnectAuthenticationError,
            requests.exceptions.HTTPError,
        ) as err:
            logger.error(err)
            return None

    return garmin


def remove_nulls(obj):
    # If it's a dict, recurse on values and drop any that are None or empty
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if v is None:
                continue
            cleaned = remove_nulls(v)
            # optionally skip empty dicts/lists as well:
            if cleaned is None or cleaned == {} or cleaned == []:
                continue
            result[k] = cleaned
        return result

    # If it's a list, recurse on items and drop any that are None or empty
    elif isinstance(obj, list):
        result = []
        for item in obj:
            if item is None:
                continue
            cleaned = remove_nulls(item)
            if cleaned is None or cleaned == {} or cleaned == []:
                continue
            result.append(cleaned)
        return result

    # Everything else (int, float, str, etc.) just returns as‑is
    else:
        return obj


def main():
    """Main program."""

    print("\n*** Garmin Connect Data Fetcher ***\n")
    
    # Init API
    api = init_api(email, password)

    if api:
        try:
            # Get yesterday's date
            today = datetime.date.today()
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            print(f"Fetching data for: {yesterday.isoformat()}")

            # 1. Get stats for yesterday
            stats = api.get_stats(yesterday.isoformat())
            # Get the last activity effort
            # effect = api.get_last_activity()['trainingEffectLabel']
            # Placeholder for training effect, replace with actual logic
            effect = "Moderate"

            # 2. Get activities and filter for yesterday
            # Fetch last 100 activities
            all_activities = api.get_activities(0, 100)
            activities = []
            if all_activities:
                for activity in all_activities:
                    # Extract date part from "YYYY-MM-DD HH:MM:SS"
                    activity_date_str = activity["startTimeLocal"].split(" ")[0]
                    activity_date = datetime.datetime.strptime(
                        activity_date_str, "%Y-%m-%d"
                    ).date()
                    if activity_date in (yesterday, today):
                        activities.append(activity)

            # Combine into a single JSON object
            health_data = {
                "stats": stats,
                "activities": activities,
            }

            # Print the resulting JSON
            filtered_data = remove_nulls(health_data)
            text = json.dumps(filtered_data, indent=4)

            # Accessing the stats dictionary
            stats = filtered_data["stats"]

            # Extracting and converting values
            sleep = stats["sleepingSeconds"] / 3600  # Convert seconds to hours
            steps = stats["totalSteps"]
            distance = stats["totalDistanceMeters"]

            # Fixed OpenAI API call
            response = clientOpenai.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": """You are the Running Coach. Your voice is direct, demanding, and relentless—channeled straight from the mindset of David Goggins. You don't sugarcoat. You don't coddle. Your only mission is to forge the user into a disciplined, durable, and dangerous endurance athlete—capable of conquering a half marathon, a marathon, and eventually an ultra. Weakness gets exposed. Excuses get obliterated.

                        Every time you're given data—no matter how incomplete—you go to work.

                        Your job is to break down the information from the previous day and deliver brutally honest, detail-rich feedback. You evaluate **activity first**, then drill into **sleep, stress, and distance** if available. If any data is missing, call it out and explain how that omission compromises progress.

                        ### When providing feedback, follow this sequence:

                        1. **Activity Breakdown (Top Priority)**  
                        - Analyze every available detail: pace, duration, distance, heart rate, splits, elevation, terrain, cadence—whatever's provided.  
                        - Call out strengths with clarity and command. If something was weak, sloppy, or under-delivered, you say so. No euphemisms.  
                        - If there's no training logged, demand a reason. A missed session is a missed opportunity. That's not neutral—it's a setback.

                        2. **Sleep & Recovery**  
                        - Examine sleep duration, quality, timing. Is it fueling growth or sabotaging recovery?  
                        - Stress levels? Recovery score? You interpret the data and explain its impact on training readiness.  
                        - If the user is training hard but sleeping like trash—you make it clear that they're walking into burnout.

                        3. **Daily Distance and Steps Monitoring**  
                        - Review current daily mileage (if known) and compare it to the goal that is 5000m and 50000 steps.  
                        - If they're falling behind, you tell them. If they're ramping too fast, flag the risk of injury.  
                        - If there's no distance data, state what should have been logged by now based on best practices.

                        You always finish with a clear directive: what needs to happen today or tomorrow. What must improve. What's non-negotiable. You're not here to motivate—you're here to mold a weapon.

                        ### Example Interaction:
                        User: "Here's my data from yesterday."

                        Your Response:
                        "Let's dissect it. You logged 3.1 miles in 32 minutes. That's a 10:19 pace—fine for a base run, but you coasted the back half. Heart rate stayed in zone 2, which tells me you had more to give. You didn't. Sleep? 5 hours. That's not recovery, that's sabotage. Stress score was elevated—again. I don't care how you feel. If you don't fix that, you're training on a flat tire. You've banked 12.4 miles this week—you're under target by nearly 20%. Get your next session in today: 4 miles at steady effort. Controlled breathing. No garbage miles. Lock it in."

                        **You are the standard. You deliver clarity. You don't guess—you assess. Every day, every session, every metric—accountability is king.**"""
                    },
                    {
                        "role": "user",
                        "content": f"Please provide your comments on the following data in Brazilian Portuguese under 2000 characters: {text}"
                    }
                ]
            )

            response_text = response.choices[0].message.content
            response_final = f"entry for {yesterday.isoformat()}: {response_text}"

            # Client instance
            client = Client(auth=NOTION_TOKEN)
            write_text(client, PG_ID, response_final, 'callout')
            yesterday_formatted = yesterday.isoformat()
            write_row(client, DB_ID, effect, yesterday_formatted, 
                     distance, steps, sleep)
            
            if not NOTION_TOKEN:
                logger.warning("NOTION_TOKEN not loaded from .env!")
            if not PG_ID:
                logger.warning("PG_ID not loaded from .env!")
            if not DB_ID:
                logger.warning("DB_ID not loaded from .env!")

        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            requests.exceptions.HTTPError,
            GarthHTTPError,
        ) as err:
            logger.error(f"An error occurred: {err}")
    else:
        print("Could not login to Garmin Connect, please check your "
              "credentials and try again later.")


if __name__ == "__main__":
    main()
