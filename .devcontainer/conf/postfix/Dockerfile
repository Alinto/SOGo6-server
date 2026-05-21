FROM registry.alinto.net:5443/alinto/sogo6/postfix:latest

ADD main.cf /etc/postfix/main.cf
ADD mailname /etc/mailname
ADD virtual /etc/postfix/virtual
ADD aliases /etc/aliases
ADD entrypoint.sh /entrypoint.sh