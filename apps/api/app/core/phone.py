import phonenumbers

DEFAULT_REGION = "LB"


def normalize_phone(raw: str, region: str = DEFAULT_REGION) -> str | None:
    """Return E.164 for a valid number (default region Lebanon), else None."""
    raw = raw.strip()
    if not raw or len(raw) > 32:
        return None
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return str(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
