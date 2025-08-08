#!/usr/bin/env python3
"""
JWT Token Generator Script for FastMCP Slack Server

This script generates JWT tokens that can be used to authenticate with the FastMCP Slack server.
Tokens are signed with HMAC-SHA256 and include configurable expiration times.
"""

import jwt
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def generate_jwt_token(
    user_id: str,
    scopes: list = None,
    expires_in_hours: int = 24,
    secret: str = None,
    issuer: str = "bernerspace-ecosystem",
    audience: str = "mcp-slack-server"
) -> str:
    """
    Generate a JWT token for the FastMCP Slack server.
    
    Args:
        user_id: Unique identifier for the user
        scopes: List of permission scopes (default: ["read", "write"])
        expires_in_hours: Token validity in hours (default: 24)
        secret: JWT signing secret (uses JWT_SECRET env var if not provided)
        issuer: Token issuer (default: "bernerspace-ecosystem")
        audience: Token audience (default: "mcp-slack-server")
    
    Returns:
        JWT token string
        
    Raises:
        ValueError: If JWT_SECRET is not found and no secret provided
    """
    
    if secret is None:
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise ValueError(
                "JWT_SECRET not found in environment variables. "
                "Please set JWT_SECRET in your .env file or provide the --secret argument."
            )
    
    if scopes is None:
        scopes = ["read", "write"]
    
    # Calculate timestamps
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=expires_in_hours)
    
    # Token payload
    payload = {
        "sub": user_id,                    # Subject (user ID)
        "iss": issuer,                     # Issuer
        "aud": audience,                   # Audience
        "iat": now,                        # Issued at
        "exp": expiration,                 # Expiration
        "scopes": scopes,                  # Custom scopes
        "client_id": user_id               # Client ID for FastMCP
    }
    
    # Generate token
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token

def verify_jwt_token(token: str, secret: str = None) -> dict:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string to verify
        secret: JWT signing secret (uses JWT_SECRET env var if not provided)
    
    Returns:
        Decoded token payload
        
    Raises:
        ValueError: If token is invalid or expired
    """
    if secret is None:
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise ValueError("JWT_SECRET not found in environment variables")
    
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer="bernerspace-ecosystem",
            audience="mcp-slack-server"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")

def format_token_info(payload: dict) -> str:
    """Format token payload information for display."""
    
    # Convert timestamps to readable format
    issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    
    # Calculate time until expiration
    now = datetime.now(timezone.utc)
    time_until_expiry = expires_at - now
    
    info = f"""
Token Information:
├── User ID: {payload['sub']}
├── Issuer: {payload['iss']}
├── Audience: {payload['aud']}
├── Scopes: {', '.join(payload.get('scopes', []))}
├── Issued At: {issued_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
├── Expires At: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
└── Valid For: {time_until_expiry.total_seconds() / 3600:.1f} hours
"""
    
    if time_until_expiry.total_seconds() <= 0:
        info += "\n⚠️  WARNING: Token has EXPIRED!"
    elif time_until_expiry.total_seconds() < 3600:  # Less than 1 hour
        info += f"\n⚠️  WARNING: Token expires in {time_until_expiry.total_seconds() / 60:.0f} minutes!"
    
    return info.strip()

def main():
    parser = argparse.ArgumentParser(
        description="Generate and verify JWT tokens for FastMCP Slack server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate token for user "admin" valid for 24 hours (default)
  python generate_jwt.py --user-id admin
  
  # Generate token valid for 7 days with custom scopes
  python generate_jwt.py --user-id alice --hours 168 --scopes read write admin
  
  # Verify an existing token
  python generate_jwt.py --verify "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  
  # Generate token with custom secret (for testing)
  python generate_jwt.py --user-id test --secret "my-secret-key"

Token Validity:
  - Default validity: 24 hours
  - Can be set from 1 hour to 8760 hours (1 year)
  - Tokens are signed with HMAC-SHA256
  - Include issuer/audience validation for security
        """
    )
    
    # Main action group
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--user-id",
        type=str,
        help="User ID to generate token for"
    )
    action_group.add_argument(
        "--verify",
        type=str,
        help="JWT token to verify and decode"
    )
    
    # Token generation options
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Token validity in hours (default: 24, max: 8760)"
    )
    parser.add_argument(
        "--scopes",
        nargs="+",
        default=["read", "write"],
        help="Permission scopes (default: read write)"
    )
    parser.add_argument(
        "--secret",
        type=str,
        help="JWT signing secret (uses JWT_SECRET env var if not provided)"
    )
    parser.add_argument(
        "--issuer",
        type=str,
        default="bernerspace-ecosystem",
        help="Token issuer (default: bernerspace-ecosystem)"
    )
    parser.add_argument(
        "--audience",
        type=str,
        default="mcp-slack-server",
        help="Token audience (default: mcp-slack-server)"
    )
    
    # Output options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output the token (for scripting)"
    )
    
    args = parser.parse_args()
    
    # Validate hours
    if args.hours < 1 or args.hours > 8760:
        print("Error: Token validity must be between 1 and 8760 hours (1 year)", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.verify:
            # Verify token
            payload = verify_jwt_token(args.verify, args.secret)
            
            if args.json:
                print(json.dumps(payload, indent=2, default=str))
            elif args.quiet:
                print("Token is valid")
            else:
                print("✅ Token is valid!")
                print(format_token_info(payload))
                
        else:
            # Generate token
            token = generate_jwt_token(
                user_id=args.user_id,
                scopes=args.scopes,
                expires_in_hours=args.hours,
                secret=args.secret,
                issuer=args.issuer,
                audience=args.audience
            )
            
            if args.quiet:
                print(token)
            elif args.json:
                # Decode token for JSON output
                payload = verify_jwt_token(token, args.secret)
                result = {
                    "token": token,
                    "payload": payload
                }
                print(json.dumps(result, indent=2, default=str))
            else:
                print("✅ JWT Token Generated Successfully!")
                print("=" * 50)
                print(f"Token: {token}")
                print("=" * 50)
                
                # Show token info
                payload = verify_jwt_token(token, args.secret)
                print(format_token_info(payload))
                
                print("\n📋 Usage Examples:")
                print(f"# FastMCP Client")
                print(f'Authorization: Bearer {token}')
                print(f"\n# Curl")
                print(f'curl -H "Authorization: Bearer {token}" http://localhost:8000')
                print(f"\n# Python")
                print(f'headers = {{"Authorization": "Bearer {token}"}}')
                
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()