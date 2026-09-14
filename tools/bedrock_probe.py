"""One-shot Bedrock readiness probe.

Tells you which of the things that look alike is actually wrong - credentials
missing, credentials malformed, the login session expired, model access not
granted, or a region/model mismatch. Each has a different fix.

Three credential routes are supported, checked in the order botocore uses:

  A. Bedrock API key   - a bearer token in AWS_BEARER_TOKEN_BEDROCK
  B. aws login session - a `login_session` in ~/.aws/config (new AWS experience);
                         needs `botocore[crt]` installed for boto3 to read it
  C. IAM access keys   - aws_access_key_id / aws_secret_access_key

    python tools/bedrock_probe.py
    python tools/bedrock_probe.py --region ap-south-1 --profile junxaws

Never prints the secret key. Read-only: makes a single tiny inference call.
"""

from __future__ import annotations

import argparse
import configparser
import os
import sys
from pathlib import Path

CRED_PATH = Path.home() / ".aws" / "credentials"
CONFIG_PATH = Path.home() / ".aws" / "config"
BEARER_ENV = "AWS_BEARER_TOKEN_BEDROCK"

PLACEHOLDER = ("PASTE_YOUR", "YOUR_KEY", "AWS_ACCESS_KEY_ID_HERE")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


def read_bearer_token() -> str | None:
    """The Bedrock API key path: a bearer token in an env var, no IAM keys.

    Azure-OpenAI-style. Simpler, but short-term keys expire with the console
    session (max 12h) and long-term ones are for exploration only. If this is
    set it takes precedence, mirroring botocore's own behaviour.
    """
    token = (os.environ.get(BEARER_ENV) or "").strip()
    if not token:
        return None
    ok(f"{BEARER_ENV} set ({len(token)} chars, "
       f"prefix {token.split('-')[0]!r})")
    return token


def find_login_profiles() -> list[str]:
    """Profiles backed by `aws login` rather than static keys.

    `aws login` writes `login_session = arn:...` into the profile's section of
    ~/.aws/config and puts NOTHING in ~/.aws/credentials. A probe that only
    reads the credentials file therefore reports "not configured" for a
    perfectly working session - so this route has to be checked explicitly.
    """
    if not CONFIG_PATH.exists():
        return []
    cp = configparser.ConfigParser()
    try:
        cp.read(CONFIG_PATH)
    except configparser.Error:
        return []
    found = []
    for section in cp.sections():
        if "login_session" in cp[section]:
            # sections are named "[profile foo]" (or bare "[default]")
            name = section.split("profile ", 1)[-1] if section.startswith("profile ") \
                else section
            found.append(name)
    return found


def check_login_profile(profile: str, region: str) -> bool:
    """Confirm a login-session profile can actually produce credentials."""
    try:
        import boto3
    except ImportError as exc:
        fail(f"boto3 is not installed: {exc}")
        return False
    try:
        sess = boto3.Session(profile_name=profile, region_name=region)
        who = sess.client("sts").get_caller_identity()
        ok(f"login session profile {profile!r} works - "
           f"account {who['Account']}  arn {who['Arn']}")
        return True
    except Exception as exc:
        name = type(exc).__name__
        fail(f"{name}: {str(exc)[:200]}")
        low = str(exc).lower()
        if "crt" in low or "missing dependency" in low:
            print()
            print("  -> boto3 cannot read `aws login` credentials without the CRT")
            print("     extra. Install it:")
            print('       pip install "botocore[crt]"')
        elif "expired" in low or "invalid" in low or "grant" in low:
            print()
            print("  -> The login session has expired. The token file still sitting")
            print("     in ~/.aws/login/cache/ does NOT mean it is valid.")
            print("     Re-authenticate (must run in a real terminal, and the")
            print("     process needs to be able to WRITE to ~/.aws/):")
            print(f"       aws login --region {region} --profile {profile}")
        return False


def read_creds() -> tuple[str, str] | None:
    if not CRED_PATH.exists():
        fail(f"{CRED_PATH} does not exist")
        return None
    cp = configparser.ConfigParser()
    try:
        cp.read(CRED_PATH)
    except configparser.Error as exc:
        fail(f"{CRED_PATH} is not valid INI: {exc}")
        return None
    if "default" not in cp:
        fail(f"{CRED_PATH} has no [default] section")
        return None
    key_id = cp["default"].get("aws_access_key_id", "").strip()
    secret = cp["default"].get("aws_secret_access_key", "").strip()

    if not key_id or not secret:
        fail("access key id or secret is empty")
        return None
    if any(p in key_id.upper() for p in PLACEHOLDER) or \
       any(p in secret.upper() for p in PLACEHOLDER):
        fail("the file still contains the placeholder text - paste your real keys")
        return None
    if not key_id.upper().startswith("AKIA") and not key_id.upper().startswith("ASIA"):
        print(f"  warn  access key id does not start with AKIA/ASIA "
              f"(starts with {key_id[:4]}...) - may still be fine")
    ok(f"credentials present: {key_id[:4]}...{key_id[-4:]} (secret hidden, "
       f"{len(secret)} chars)")
    return key_id, secret


def check_region(region: str) -> None:
    cp = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        cp.read(CONFIG_PATH)
    configured = cp["default"].get("region", "") if "default" in cp else ""
    if configured:
        ok(f"region in ~/.aws/config: {configured}")
        if configured != region:
            print(f"  warn  probing {region} but config says {configured}")
    else:
        print(f"  warn  no region in ~/.aws/config; using {region} from the flag")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-west-2")
    ap.add_argument("--profile", default="",
                    help="AWS profile to use (needed for `aws login` sessions)")
    ap.add_argument("--model", default="",
                    help="override the model id (default: what agent.py uses)")
    args = ap.parse_args()

    print("Bedrock readiness probe")
    print("-" * 70)

    # Imported here rather than per-branch: the bearer-token path skips the STS
    # step, so a branch-local import left boto3 undefined for it.
    try:
        import boto3
        import json as _json
    except ImportError as exc:
        fail(f"boto3 is not installed: {exc}")
        print("  pip install -r requirements.txt")
        return 1

    print("\n1. credentials")
    token = read_bearer_token()
    creds = None
    login_ok = False
    profile = args.profile

    if token:
        print("      using the Bedrock API key (bearer token) path; other routes ignored")
        ok("credentials present via bearer token")
    else:
        # Route B: an `aws login` session. This leaves ~/.aws/credentials empty,
        # so it MUST be checked before concluding nothing is configured.
        if not profile:
            found = find_login_profiles()
            if found:
                profile = found[0]
                if len(found) > 1:
                    print(f"  note  {len(found)} login profiles found: {', '.join(found)}")
                    print(f"        probing {profile!r}; use --profile to pick another")
        if profile and profile in find_login_profiles():
            print(f"      route: aws login session (profile {profile!r})")
            login_ok = check_login_profile(profile, args.region)
            if not login_ok:
                return 1
        else:
            creds = read_creds()
            if creds is None:
                print()
                print("No credential route is configured. Pick one:")
                print()
                print(f"  A. Bedrock API key (simplest) - generate one in the Bedrock")
                print(f"     console under API keys, then set:")
                print(f'       export {BEARER_ENV}="<key>"      (macOS/Linux/bash)')
                print(f'       setx {BEARER_ENV} "<key>"        (Windows, new shell)')
                print()
                print(f"  B. aws login session (new AWS experience) - run:")
                print(f"       aws login --region {args.region} --profile <name>")
                print(f"     then pass --profile <name> here. Requires `botocore[crt]`.")
                print()
                print(f"  C. IAM access keys - edit {CRED_PATH}")
                print("     and paste aws_access_key_id / aws_secret_access_key.")
                return 1

    print("\n2. region")
    check_region(args.region)

    print("\n3. identity (STS)")
    if token:
        # STS does not accept bearer tokens - it is a SigV4 service. Skipping is
        # correct, not a gap: the inference call below is the real test.
        print("      skipped - STS does not accept bearer tokens; step 4 is the")
        print("      real test of whether the key works.")
    elif login_ok:
        # Already verified by check_login_profile above.
        print("      already verified in step 1 via the login session.")
    else:
        key_id, secret = creds
        try:
            sts = boto3.client(
                "sts", region_name=args.region,
                aws_access_key_id=key_id, aws_secret_access_key=secret)
            who = sts.get_caller_identity()
            ok(f"account {who['Account']}  arn {who['Arn']}")
        except Exception as exc:
            fail(f"{type(exc).__name__}: {str(exc)[:200]}")
            print("\n  The keys are present but not usable. Usual causes: keys were")
            print("  revoked, the IAM user lacks permissions, or the machine clock")
            print("  is off (signature errors).")
            return 1

    print("\n4. model access + a real inference")
    model_id = args.model
    if not model_id:
        # Ask Strands what it will actually use rather than hardcoding an id
        # that drifts when the SDK updates its default.
        try:
            from strands.models.bedrock import DEFAULT_BEDROCK_MODEL_ID
            model_id = DEFAULT_BEDROCK_MODEL_ID
            source = "Strands default"
        except Exception:
            from strands.models import BedrockModel
            model_id = BedrockModel._get_default_model_with_warning(args.region)
            source = "Strands resolver"
    else:
        source = "flag"
    print(f"  ...   model: {model_id}  ({source})")

    try:
        if login_ok:
            # Let the session resolve its own credentials; passing explicit keys
            # would force SigV4 and bypass the login provider entirely.
            rt = boto3.Session(profile_name=profile,
                               region_name=args.region).client("bedrock-runtime")
        elif token:
            # The key is already in the environment, so the default chain finds
            # it. Do not pass explicit keys, or SigV4 would be used instead.
            rt = boto3.client("bedrock-runtime", region_name=args.region)
        else:
            rt = boto3.client(
                "bedrock-runtime", region_name=args.region,
                aws_access_key_id=key_id, aws_secret_access_key=secret)
        body = _json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        })
        resp = rt.invoke_model(modelId=model_id, body=body)
        payload = json.loads(resp["body"].read())
        text = "".join(b.get("text", "") for b in payload.get("content", []))
        ok(f"model replied: {text.strip()[:60]!r}")
    except Exception as exc:
        name = type(exc).__name__
        fail(f"{name}: {str(exc)[:220]}")
        low = str(exc).lower()
        print()
        if "invalid api key format" in low:
            print("  -> The key is malformed. Bedrock API keys must start with a")
            print("     specific prefix. Copy the whole key, with no whitespace or")
            print("     stray quotes, when setting the environment variable.")
        elif "being verified" in low or "operation not allowed" in low:
            print("  -> The ACCOUNT is still being verified, not a config problem.")
            print("     New AWS-experience accounts cannot invoke Bedrock until")
            print("     verification completes (AWS says under 2 hours). Credentials,")
            print("     region and model id are all fine - control-plane calls like")
            print("     list_foundation_models succeed. WAIT and re-run; do not")
            print("     re-request model access or switch regions, neither will help.")
        elif "accessdenied" in low or "not authorized" in low:
            print("  -> Model access is not granted for this model in this region.")
            print("     Console -> Bedrock -> Model access -> Modify -> tick Anthropic")
            print("     Claude -> submit. Approval is usually immediate.")
        elif "validationexception" in low and "model" in low:
            print("  -> The model id is not available in this region. Try")
            print("     --region us-east-1, or list what is available:")
            print("     python tools/bedrock_probe.py --model <other-id>")
        elif "could not connect" in low or "endpoint" in low:
            print("  -> Network problem reaching the Bedrock endpoint.")
        else:
            print("  -> Unexpected. The message above is the real one.")
        return 1

    print("\n" + "-" * 70)
    print("Ready. Run the real agent with:")
    if profile and login_ok:
        print(f'  AWS_PROFILE={profile} python -m nuskha.cli ask "what should atorvastatin 10mg cost?"')
    else:
        print('  python -m nuskha.cli ask "what should atorvastatin 10mg cost?"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
