import json
import logging
import urllib.request
import urllib.error
import datetime

logger = logging.getLogger(__name__)

# The user's Discord Webhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1485272931205648606/joQ2aK6ADchkwALHDIRzBn5BOvJ8VKeb25BSZ3LqLY3pIYW68I3SyKibZ0P4R1T8lgXq"

def send_sure_shot_alert(game_mode: str, period: str, pred_data: dict, bet_plan: dict):
    """
    Send an embedded rich message to Discord alerting the server about a Sure Shot.
    """
    try:
        color_val = 0x2e8b57 if "Green" in pred_data.get('color', '') else 0xdc143c
        if "Violet" in pred_data.get('color', ''):
            color_val = 0x800080
            
        embed = {
            "title": "🎯 NEW SURE SHOT ALERT!",
            "description": f"**FlankyOp AI** has detected a high-confidence signal for **{game_mode.replace('_', ' ')}** period **{period[-8:]}**.",
            "color": color_val,
            "fields": [
                {
                    "name": "🔮 Target Prediction",
                    "value": f"**Number:** {str(pred_data.get('number', '?'))}\n**Size:** {str(pred_data.get('size', '?'))}\n**Color:** {str(pred_data.get('color', '?'))}",
                    "inline": True
                },
                {
                    "name": "⚙️ AI Confidence",
                    "value": f"**{str(pred_data.get('confidence', '--'))}%**",
                    "inline": True
                },
                {
                    "name": "📊 Detected Pattern",
                    "value": str(pred_data.get('pattern') or 'None'),
                    "inline": False
                },
                {
                    "name": "💰 Suggested Action",
                    "value": f"**Bet Type:** {str(bet_plan.get('type', 'Unknown'))}\n**Total Outlay:** Rs {str(bet_plan.get('outlay', 0))}",
                    "inline": False
                }
            ],
            "footer": {
                "text": "BDG Predictor System • Automated Alert",
                "icon_url": "https://i.imgur.com/8Q4sD8Q.png"
            },
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        payload = {
            "content": "@everyone 🔥 Auto-Bet System found a new opportunity!",
            "embeds": [embed]
        }
        
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL, 
            data=json.dumps(payload).encode("utf-8"), 
            headers={"Content-Type": "application/json", "User-Agent": "BDG-Bot/1.0"}
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 204):
                logger.info("Successfully sent Discord Webhook for period %s", period)
            else:
                logger.warning("Discord Webhook returned status %s", response.status)
                
    except Exception as e:
        logger.error("Failed to send Discord Webhook: %s", e)

