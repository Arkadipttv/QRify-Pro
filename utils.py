import re
from pathlib import Path

import qrcode
from PIL import Image, ImageColor, ImageOps


URL_RE = re.compile(
    r"^(https?://)?"
    r"((([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})|localhost)"
    r"(:\d{1,5})?"
    r"(/[^\s]*)?$"
)
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{6,19}$")


def detect_input_type(value):
    text = value.strip()
    if not text:
        return None
    if EMAIL_RE.match(text):
        return "Email"
    if PHONE_RE.match(text):
        return "Phone"
    if URL_RE.match(text) and ("." in text or text.startswith(("http://", "https://"))):
        return "URL"
    return None


def validate_input(value, input_type):
    text = value.strip()
    if not text:
        return False, "Please enter content before generating a QR code."

    if input_type == "URL":
        if not URL_RE.match(text) or ("." not in text and not text.startswith(("http://", "https://"))):
            return False, "Enter a valid URL, such as https://example.com."
    elif input_type == "Email":
        if not EMAIL_RE.match(text):
            return False, "Enter a valid email address, such as hello@example.com."
    elif input_type == "Phone":
        digit_count = len(re.sub(r"\D", "", text))
        if not PHONE_RE.match(text) or digit_count < 7 or digit_count > 20:
            return False, "Enter a valid phone number with 7 to 20 digits."
    elif input_type != "Text":
        return False, "Choose a valid input type."

    return True, ""


def build_qr_payload(value, input_type):
    text = value.strip()
    if input_type == "URL":
        if not text.startswith(("http://", "https://")):
            return f"https://{text}"
        return text
    if input_type == "Email":
        return f"mailto:{text}"
    if input_type == "Phone":
        normalized = re.sub(r"[\s().-]", "", text)
        return f"tel:{normalized}"
    return text


def generate_qr_code(payload, qr_color="#111111", bg_color="#FFFFFF", size=800, logo_path=None):
    _validate_color(qr_color, "QR color")
    _validate_color(bg_color, "Background color")
    size = _normalize_size(size)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color=qr_color, back_color=bg_color).convert("RGBA")
    image = image.resize((size, size), Image.Resampling.NEAREST)

    if logo_path:
        image = _add_center_logo(image, logo_path, bg_color)

    return image


def save_qr_image(image, file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Please save as PNG, JPG, or JPEG.")

    path.parent.mkdir(parents=True, exist_ok=True)
    if suffix in {".jpg", ".jpeg"}:
        image.convert("RGB").save(path, quality=95)
    else:
        image.save(path, "PNG")


def _add_center_logo(qr_image, logo_path, bg_color):
    path = Path(logo_path)
    if not path.exists():
        raise FileNotFoundError("Selected logo file was not found.")

    logo = Image.open(path).convert("RGBA")
    qr_size = qr_image.size[0]
    logo_size = max(48, qr_size // 5)
    logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)

    padding = max(12, qr_size // 48)
    plate_size = (logo.width + padding * 2, logo.height + padding * 2)
    plate = Image.new("RGBA", plate_size, ImageColor.getrgb(bg_color) + (255,))
    plate = ImageOps.expand(plate, border=max(2, qr_size // 160), fill=ImageColor.getrgb(bg_color) + (255,))
    plate_position = ((qr_size - plate.width) // 2, (qr_size - plate.height) // 2)
    logo_position = (
        plate_position[0] + (plate.width - logo.width) // 2,
        plate_position[1] + (plate.height - logo.height) // 2,
    )

    composed = qr_image.copy()
    composed.alpha_composite(plate, plate_position)
    composed.alpha_composite(logo, logo_position)
    return composed


def _validate_color(color, label):
    try:
        ImageColor.getrgb(color)
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid color.") from exc


def _normalize_size(size):
    try:
        normalized = int(size)
    except (TypeError, ValueError) as exc:
        raise ValueError("QR size must be a number.") from exc

    if normalized < 128 or normalized > 2400:
        raise ValueError("QR size must be between 128 and 2400 pixels.")
    return normalized
