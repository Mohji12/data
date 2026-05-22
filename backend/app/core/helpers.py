import re
import random

def get_vimeo_video_id_from_url(url: str) -> str:
    """
    Extracts the Vimeo video ID from various forms of Vimeo URLs.
    Ported from PHP `getVimeoVideoIdFromUrl`.
    """
    pattern = r"^https?:\/\/(?:www\.|player\.)?vimeo.com\/(?:channels\/(?:\w+\/)?|groups\/([^\/]*)\/videos\/|album\/(\d+)\/video\/|video\/|)(\d+)(?:$|\/|\?)(?:[?]?.*)$"
    match = re.search(pattern, url, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(3)
    return ""

def generate_random_password(length: int = 8) -> str:
    """
    Generates a random password of a given length.
    Ported from PHP `generate_random_Password`.
    """
    alphabet = "abcdefghijklmnopqrstuwxyz0123456789"
    return ''.join(random.choice(alphabet) for _ in range(length))

def generate_coupon_code(length: int = 8) -> str:
    """
    Generates a random uppercase alphanumeric coupon code.
    Ported from PHP `generate_coupon_code`.
    """
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(random.choice(alphabet) for _ in range(length))
