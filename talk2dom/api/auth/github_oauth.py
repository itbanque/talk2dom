import os
from authlib.integrations.starlette_client import OAuth


GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")


oauth = OAuth()
oauth.register(
    name="github",
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={
        # GitHub OAuth App 支持这两个 scope；如需更少权限可只用 read:user
        "scope": "read:user user:email",
        "token_endpoint_auth_method": "client_secret_post",
    },
)
