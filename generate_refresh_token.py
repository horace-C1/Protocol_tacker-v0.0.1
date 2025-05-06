import dropbox
from dropbox.oauth import DropboxOAuth2FlowNoRedirect

APP_KEY = "YOUR_APP_KEY"
APP_SECRET = "YOUR_APP_SECRET"

auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET, token_access_type='offline')
authorize_url = auth_flow.start()

print("1. Go to:", authorize_url)
print("2. Click 'Allow' (you may have to log in first)")
print("3. Copy the authorization code.")

auth_code = input("Enter the authorization code here: ").strip()
oauth_result = auth_flow.finish(auth_code)

print("\n✅ Access token:", oauth_result.access_token)
print("🔁 Refresh token:", oauth_result.refresh_token)
print("⏳ Expires in:", oauth_result.expires_in, "seconds")

# Save your refresh_token somewhere safe!
