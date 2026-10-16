# Sign-in options and single sign-on

LeadsGen supports four ways to sign in:

| Method | Who it's for | Plan |
|---|---|---|
| Email and password, with optional two-factor | Everyone | All |
| Continue with Google / Microsoft | Everyone | All |
| Workspace SSO over OpenID Connect (Okta, Entra ID, Auth0, Google Workspace) | Companies | Pro and Enterprise |
| Workspace SSO over SAML 2.0 | Companies | Enterprise |

Turn on the SSO screens with `FEATURE_SSO=true`.

## Continue with Google / Microsoft (operator setup)

Register an OAuth app with each provider and set these on the API:

| Variable | Value |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → OAuth client (Web) |
| `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET` | Entra ID → App registrations (multi-tenant + personal accounts) |

Authorised redirect URIs (replace with your web URL):

- `https://app.example.com/api/auth/oidc/google/callback`
- `https://app.example.com/api/auth/oidc/microsoft/callback`

The redirect goes through the web app's `/api` proxy, so the session cookie stays first-party.

How accounts are matched:

- **Google:** a verified Google email signs in, and links, the LeadsGen account with the same email.
- **Microsoft:** Microsoft doesn't guarantee that the email in a token is verified (the "nOAuth" issue). So a Microsoft sign-in never takes over an existing account by email. People with an existing account connect Microsoft from **Settings → Security → Sign-in methods** while signed in.
- **New accounts:** Google and Microsoft sign-ins with no matching account create a new account and workspace.
- **Two-factor:** people who have it turned on still enter their code after Google or Microsoft.

## Workspace SSO (customer setup)

Admins set this up in **Settings → Single sign-on**:

1. **Verify your domain.** Add `yourcompany.com`, then publish the TXT record shown (`leadsgen-verification=…`) on that domain. Click **Check now** once DNS has updated. Public email domains such as gmail.com can't be verified, and a domain can only belong to one workspace.
2. **Add your identity provider.**
   - **OIDC:** enter the issuer URL, client ID and client secret. Register the **Redirect URI** shown with your provider.
   - **SAML:** enter the IdP entity ID, SSO URL and signing certificate (PEM). Give your IdP the **Entity ID** and **ACS URL** shown. Metadata is also available at the entity ID URL.

     The IdP must sign assertions, and send the email as the NameID or as an `email` / `mail` attribute.
3. **Turn it on.** People sign in from the login page with **Sign in with single sign-on (SSO)** and their work email.
4. **Optionally, require SSO.** Password sign-in is then blocked for emails at your verified domains. Workspace owners keep password access as a break-glass route.

Just-in-time provisioning: the first time someone at a verified domain signs in, they get an account if they don't have one. They're added to the workspace with the role you chose.

## Security notes

- OIDC uses the authorization code flow with PKCE, a nonce and a single-use state. The state is bound to the browser with a short-lived cookie.
- ID tokens are verified against the provider's published keys. The checks cover issuer, audience, expiry and nonce.
- SAML responses must be signed by the configured certificate, and only the signed part of the document is trusted, which prevents signature wrapping. The checks cover issuer, audience, recipient, time limits and that the response answers a sign-in request started here (`InResponseTo`, single use).
- Identity provider URLs entered by admins are fetched through the SSRF-safe HTTP client, which blocks private and internal addresses.
- Every SSO sign-in, identity link and provisioning event is written to the audit log.
