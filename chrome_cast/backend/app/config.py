import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("SHOWMEONCE_DATA_DIR", Path(__file__).resolve().parent.parent / "data" / "recordings"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Clé optionnelle pour protéger l'endpoint d'upload (header X-ShowMeOnce-Key)
SHOWMEONCE_API_KEY = os.getenv("SHOWMEONCE_API_KEY", "")

GLADIA_API_KEY = os.getenv("GLADIA_API_KEY", "")
GLADIA_BASE_URL = os.getenv("GLADIA_BASE_URL", "https://api.gladia.io/v2")
GLADIA_LANGUAGES = [l.strip() for l in os.getenv("GLADIA_LANGUAGES", "fr,en").split(",") if l.strip()]
GLADIA_SUMMARIZE = os.getenv("GLADIA_SUMMARIZE", "true").lower() == "true"

HAI_API_KEY = os.getenv("HAI_API_KEY", "")
HAI_BASE_URL = os.getenv("HAI_BASE_URL", "https://agp.eu.hcompany.ai/api/v2")
HAI_DEFAULT_AGENT = os.getenv("HAI_DEFAULT_AGENT", "h/web-surfer-flash")
HAI_SKILL_NAMESPACE = os.getenv("HAI_SKILL_NAMESPACE", "")  # ex: "acme" → skills "acme/show-me-once-xxx"

# Connexion aux sites (Stripe, Shopify…) dans le navigateur cloud de H :
# - HAI_VAULT_ID : vault H (identifiants + TOTP) lié au navigateur de l'agent
# - HAI_USE_DEFAULT_PROFILE : réutilise ton profil navigateur par défaut (cookies conservés d'une session à l'autre)
# - HAI_BROWSER_PROFILE_ID : profil navigateur uploadé (prioritaire sur le profil par défaut)
HAI_VAULT_ID = os.getenv("HAI_VAULT_ID", "")
HAI_USE_DEFAULT_PROFILE = os.getenv("HAI_USE_DEFAULT_PROFILE", "true").lower() == "true"
HAI_BROWSER_PROFILE_ID = os.getenv("HAI_BROWSER_PROFILE_ID", "")
