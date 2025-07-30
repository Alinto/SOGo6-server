# SOGo 6 server

## Description

Flask application which permit to publish web pages like maintenance page.

## Development

Use vscode and devcontainer will set up the development workspace.
A launcher start the project on http://localhost:5000/


## Structure

* agent/...............Contains all code of the sogo agent for event scheduling
* app/.................Contains all code of the web application
* docs................All documentation about installation, configuration and devellopers' contribution
* tests...............Contains all code for testing the web application


## Install

* for module python-ldap you'll need the openldap libraries that wont be install with poetry/pip. On debian bookworm, meaning this libldap2-dev, libsasl2-dev and ldap-utils.

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
