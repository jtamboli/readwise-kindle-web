#!/opt/venv/bin/python3
import json
import os
import secrets
import sys
import requests
from urllib.parse import urljoin


def get_csrf_token(session, url):
    """Get CSRF token from login page."""
    response = session.get(url)
    response.raise_for_status()

    # Extract CSRF token from cookies
    csrf_token = session.cookies.get('csrftoken')
    if not csrf_token:
        raise ValueError("Could not find CSRF token in cookies")

    return csrf_token


def login(email, password):
    """Login to Readwise and return authenticated session."""
    session = requests.Session()

    # Set up headers to mimic browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    # Get login page to obtain CSRF token
    login_url = 'https://readwise.io/accounts/login?next=/to_reader'
    csrf_token = get_csrf_token(session, login_url)

    # Submit login form
    login_data = {
        'csrfmiddlewaretoken': csrf_token,
        'login': email,
        'password': password,
        'next': '/to_reader',
    }

    response = session.post(
        'https://readwise.io/accounts/login/',
        data=login_data,
        headers={
            'Referer': login_url,
            'Origin': 'https://readwise.io',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        allow_redirects=True
    )

    # Check if login was successful
    if response.status_code != 200:
        raise Exception(f"Login failed with status code: {response.status_code}")

    # Verify we have session cookie
    if 'rwsessionid' not in session.cookies:
        raise Exception("Login failed: No session cookie received")

    return session


def send_kindle_digest(session):
    """Trigger Kindle digest send."""
    response = session.post(
        'https://readwise.io/reader/api/send_kindle_digest/',
        headers={
            'Origin': 'https://read.readwise.io',
            'Referer': 'https://read.readwise.io/',
            'Accept': '*/*',
        }
    )

    response.raise_for_status()
    return response.json() if response.text else {}


def check_auth():
    """Verify query string token authentication for FastCGI endpoint."""
    query_string = os.environ.get('QUERY_STRING', '')
    expected_token = os.environ.get('READWISE_WEBHOOK_TOKEN', '')

    if not expected_token:
        # No token configured - deny access (secure by default)
        return False

    # Parse query string for token parameter
    for param in query_string.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            if key == 'token':
                # Use constant-time comparison to prevent timing attacks
                return secrets.compare_digest(value, expected_token)

    return False


def main():
    # Check if running as FastCGI
    is_fastcgi = 'GATEWAY_INTERFACE' in os.environ

    # For FastCGI, check auth before anything else
    if is_fastcgi and not check_auth():
        print("Status: 401 Unauthorized")
        print("Content-Type: text/html")
        print("")
        print("<html><body><h1>Unauthorized</h1><p>Invalid or missing authentication token</p></body></html>")
        sys.exit(0)

    # Read credentials from environment
    email = os.environ.get('READWISE_EMAIL', '').strip()
    password = os.environ.get('READWISE_PASSWORD', '').strip()

    try:
        # Validate credentials
        if not email:
            raise ValueError("READWISE_EMAIL not configured")
        if not password:
            raise ValueError("READWISE_PASSWORD not configured")

        # Login
        session = login(email, password)

        # Send digest
        result = send_kindle_digest(session)

        # Output CGI headers and success response
        print("Content-Type: text/html")
        print("")
        print("""<!DOCTYPE html>
<html>
<head>
    <title>Kindle Digest Sent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 16px;
            background-color: #f5f5f5;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .success {
            color: #2ecc71;
        }
        h1 {
            margin-top: 0;
            color: #333;
        }
        .details {
            background: #f9f9f9;
            padding: 12px;
            border-radius: 8px;
            margin-top: 12px;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1 class="success">✓ Kindle Digest Sent</h1>
        <p>Your Readwise Kindle digest has been triggered successfully.</p>""")
        if result:
            print('        <div class="details">Response: ' + json.dumps(result) + '</div>')
        print("""    </div>
</body>
</html>""")

    except Exception as e:
        # Ensure we always output valid HTTP headers even if there's an error
        print("Content-Type: text/html")
        print("")
        print(f"""<!DOCTYPE html>
<html>
<head>
    <title>Error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 16px;
            background-color: #f5f5f5;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .error {{
            color: #e74c3c;
        }}
        h1 {{
            margin-top: 0;
            color: #333;
        }}
        .details {{
            background: #f9f9f9;
            padding: 12px;
            border-radius: 8px;
            margin-top: 12px;
            font-size: 0.9em;
            color: #666;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1 class="error">✗ Error</h1>
        <p>Failed to send Kindle digest.</p>
        <div class="details">{str(e)}</div>
    </div>
</body>
</html>""")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Ensure we always output valid HTTP headers even if there's an error
        print("Content-Type: text/html")
        print("")
        print(f"<html><body><h1>Error</h1><p>An error occurred: {str(e)}</p></body></html>")
