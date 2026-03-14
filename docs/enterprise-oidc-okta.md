# Enterprise OIDC and Okta Integration

**Workstream 6.** The Detec dashboard supports generic OIDC for SSO. This doc describes how to configure Okta (or any OIDC-compatible identity provider) for sign-in.

## Server configuration

SSO is configured via environment variables on the API server. Set:

| Variable | Description | Example (Okta) |
|----------|-------------|----------------|
| `OIDC_ISSUER` | Issuer URL of the IdP | `https://your-org.okta.com/oauth2/default` |
| `OIDC_CLIENT_ID` | OAuth2 client id | Application client id from Okta |
| `OIDC_CLIENT_SECRET` | OAuth2 client secret | From Okta application |
| `OIDC_REDIRECT_URI` | Callback URL after login | `https://your-detec.example.com/auth/callback` |

The dashboard Settings page shows "SSO Configuration" and reflects whether OIDC is configured (it reads `/api/auth/sso-status` from the server).

## Okta setup steps

1. In Okta Admin: Applications → Create App Integration → OIDC, Single-Page Application or Web Application (depending on your deployment). Configure redirect URI to match `OIDC_REDIRECT_URI`.
2. For Web Application: use Authorization Code flow; set redirect URI to your Detec base URL + `/auth/callback` (or the path your API uses for OIDC callback).
3. Copy the Client ID and Client Secret into `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET`. Set `OIDC_ISSUER` to your Okta issuer (e.g. `https://dev-12345.okta.com/oauth2/default`).
4. Restart the API server and open the dashboard; sign-in should offer the OIDC option.

## Proof of working integration

- **Manual test:** Configure the four env vars, restart API, open dashboard, sign in via OIDC. Confirm user is logged in and tenant context is correct.
- **Automated test:** Existing SSO tests in `api/tests/test_sso.py` (if present) or auth tests validate the OIDC flow with a mock or test issuer. Run `pytest api/tests/ -k sso -v` to confirm.

## Limitations

- User provisioning (creating Detec users from Okta groups) is not described here; today OIDC typically logs in an existing user or creates on first login depending on API implementation.
- Okta-specific claims (e.g. groups) can be used for role mapping if the API supports it; see API auth and tenant resolution code for details.
