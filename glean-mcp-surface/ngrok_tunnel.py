"""
Standalone ngrok tunnel starter for OAuth callback redirect URI.

Usage:
  python ngrok_tunnel.py <NGROK_AUTH_TOKEN> [PORT]

Or via environment variables:
  NGROK_AUTH_TOKEN=xxx python ngrok_tunnel.py

Default port: 8081 (must match the port oauth_chat_app.py runs on)

This starts a NEW ngrok agent process (isolated from any existing ngrok
sessions / custom-domain tunnels you may already have running).
"""

import os
import sys
import time
import tempfile

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def start_tunnel(auth_token: str, port: int) -> None:
    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print("ERROR: pyngrok is not installed.")
        print("Run:  pip install pyngrok")
        sys.exit(1)

    # Use a separate config file so this agent doesn't interfere with any
    # already-running ngrok process (e.g. your existing custom-domain tunnel).
    config_path = os.path.join(tempfile.gettempdir(), "ngrok_oauth_tunnel.yml")

    pyngrok_config = conf.PyngrokConfig(
        auth_token=auth_token,
        config_path=config_path,
        # Use a different API port to avoid clashing with the default 4040
        ngrok_version="v3",
    )

    print(f"\nStarting ngrok tunnel → localhost:{port} ...")
    try:
        tunnel = ngrok.connect(port, "http", pyngrok_config=pyngrok_config)
    except Exception as e:
        print(f"ERROR: Failed to start tunnel: {e}")
        sys.exit(1)

    public_url = tunnel.public_url
    # pyngrok may return http; ngrok usually upgrades to https
    if public_url.startswith("http://"):
        public_url = "https://" + public_url[len("http://"):]

    callback_url = f"{public_url}/callback"

    print("\n" + "=" * 65)
    print(f"  ngrok tunnel is live!")
    print(f"")
    print(f"  Public URL  :  {public_url}")
    print(f"  Callback URI:  {callback_url}")
    print("=" * 65)
    print("\nNext steps:")
    print(f"  1. Go to Google Cloud Console → APIs & Services → Credentials")
    print(f"     → your OAuth 2.0 Client → add this Authorized Redirect URI:")
    print(f"     {callback_url}")
    print(f"\n  2. Start the chat app with the redirect URI set:")
    print(f"     REDIRECT_URI={callback_url} python oauth_chat_app.py")
    print(f"\n  3. Open http://localhost:8081 in your browser.")
    print(f"\nPress Ctrl+C to stop the tunnel.\n")

    try:
        proc = ngrok.get_ngrok_process(pyngrok_config=pyngrok_config)
        proc.proc.wait()
    except KeyboardInterrupt:
        print("\nStopping tunnel...")
        ngrok.kill(pyngrok_config=pyngrok_config)
        print("Tunnel stopped.")


def main():
    auth_token = None
    port = 8081

    # Parse args / env
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        auth_token = args[0]
        if len(args) > 1:
            try:
                port = int(args[1])
            except ValueError:
                print(
                    f"WARNING: Invalid port '{args[1]}', using default {port}")

    if not auth_token:
        auth_token = os.environ.get("NGROK_AUTH_TOKEN")

    if not auth_token:
        print("Usage:")
        print("  python ngrok_tunnel.py <NGROK_AUTH_TOKEN> [PORT]")
        print("\nOr set the environment variable:")
        print("  export NGROK_AUTH_TOKEN=your_token_here")
        print("  python ngrok_tunnel.py")
        sys.exit(1)

    start_tunnel(auth_token, port)


if __name__ == "__main__":
    main()
