# SOGo 6 server

## Description

Flask application which permit to publish web pages like maintenance page.

## Development

Use vscode and devcontainer will set up the development workspace.
A launcher start the project on http://localhost:5000/

## Install

* To check the `docker-compose.yml` file try
```shell
docker compose -f docker-compose.yml config
```

* for module python-ldap you'll need the openldap libraries that wont be install with poetry/pip. On debian bookworm, meaning this libldap2-dev, libsasl2-dev and ldap-utils.
* for module psycopg, you'll need to install the package libpq5.

## DevContainer

To properly use the devcontainer, where files will be generated, you should change the following:
* in `.devcontainer/Dockerfile.devcontainer` modify:
```
ARG USERNAME=
ARG USER_ID=
ARG GROUP_ID=
```
to match your host name, user id and group id. To get this info, run the command `id` in your terminal.

* in `.devcontainer/docker-compose.yml`, in the service `server` midify the paramer `user` as <uid>:<guid>.

* in `.devcontainer/devcontainer.json`, change `remoteUser` to your username.

## Run

Start flask application
```bash
poetry run start
```

Start agent application
```bash
poetry run agent
poetry run agent-beat
```

Run unittest
```bash
poetry run pytest
```

Run unittest and generate artifacts
```bash
poetry run pytest --doctest-modules --junitxml=junit/test-results.xml --cov=app --cov-report=xml --cov-report=html
```

Generate documentation
```bash
npx antora antora-playbook-dev.yml
```

Push documentation (with vpn)
```
rsync -avz docs/developer/build/ root@192.168.69.247:/data2/sogo_doc
```

# Build the local image

```
docker build -t sogo6-backend -f deploy/local/Dockerfile.local .
```
