import os
from typing import Tuple

import requests
from django.contrib.auth import get_user_model


def verify_lxp_credentials(email: str, password: str) -> Tuple[bool, str]:
    """
    Validates learning email + password against LXP endpoint.
    If LXP endpoint is not configured, falls back to local auth-by-email.
    """
    lxp_verify_url = os.getenv("LXP_VERIFY_URL", "").strip()
    if lxp_verify_url:
        try:
            response = requests.post(
                lxp_verify_url,
                json={"email": email, "password": password},
                timeout=8,
            )
        except requests.RequestException:
            return False, "LXP is temporarily unavailable."

        if response.status_code == 200:
            return True, "verified"
        return False, "Invalid LXP email/password."

    # Local fallback for MVP/dev: verify against Django user with email.
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return False, "No user with this email."
    if not user.check_password(password):
        return False, "Invalid email/password."
    return True, "verified"

