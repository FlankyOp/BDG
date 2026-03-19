import logging
import requests
from .types import PredictionDict, PredictionBlockDict

logger = logging.getLogger(__name__)

BOT_TOKEN = '8612122832:AAH6_CNO1FQYfs60PhgaMZ-5_4K3343BNjQ'
CHAT_ID = '1308871087'

def format_prediction_message(prediction: PredictionDict) -> str:
    try:
        next_period: str = prediction.get('next_period', 'UNKNOWN')
        timestamp: str = prediction.get('timestamp', 'NOW')[:16]
        
        primary: PredictionBlockDict = prediction.get('primary_prediction', {})
        alt: PredictionBlockDict = prediction.get('alternative_prediction', {})
        backup: PredictionBlockDict = prediction.get('backup_prediction', prediction.get('strong_possibility', {}))
        
        trends: dict[str, str] = prediction.get('trend_analysis', {})
        summary: dict[str, str] = prediction.get('summary', {})

        message = '<b>◈ BDG PREDICTION ◈</b>\n'
        message += f'Period: <b>{next_period}</b>\n\n'
        
        p_num = primary.get('number', '?')
        p_conf = primary.get('accuracy', '0%')
        p_size = primary.get('size', '?')
        p_color = primary.get('color', '?')
        message += f'PRIMARY: <b>{p_num}</b> ({p_color}, {p_size}) <b>{p_conf}</b>\n'
        
        if alt:
            a_num = alt.get('number', '?')
            a_conf = alt.get('accuracy', '0%')
            a_size = alt.get('size', '?')
            a_color = alt.get('color', '?')
            message += f'ALT: {a_num} ({a_color}, {a_size}) {a_conf}\n'
        
        if backup:
            b_num = backup.get('number', '?')
            b_conf = backup.get('accuracy', '0%')
            b_size = backup.get('size', '?')
            b_color = backup.get('color', '?')
            message += f'BACKUP: {b_num} ({b_color}, {b_size}) {b_conf}\n\n'
        
        message += f'Size Pattern: {trends.get("size_pattern", "None")}\n'
        message += f'Color Pattern: {trends.get("color_pattern", "None")}\n\n'
        
        message += f'{summary.get("combined_strategy", "Play primary.")}\n\n'
        message += f'<i>Sent auto {timestamp}</i>'
        
        if len(message) > 4000:
            message = message[:4000] + '\n(truncated)'
        
        return message
    except:
        return 'Prediction send error'

def send_prediction(prediction: PredictionDict) -> bool:
    primary: PredictionBlockDict = prediction.get('primary_prediction', {})
    conf_value: float = primary.get('accuracy_value', 0.0)
    if conf_value < 0.7:
        logger.info('Low conf %.0f%% skipped Telegram', conf_value * 100)
        return False
    
    try:
        message = format_prediction_message(prediction)
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        data = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        logger.info('Telegram sent %s conf %.0f%%', prediction.get('next_period'), conf_value * 100)
        return True
    except Exception as e:
        logger.error('Telegram error %s', e)
        return False

if __name__ == '__main__':
    from predictor import Predictor
    from data_fetcher import create_sample_data
    draws = create_sample_data()
    p = Predictor(draws)
    pred = p.generate_prediction()
    print(send_prediction(pred))

