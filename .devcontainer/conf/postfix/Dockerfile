From ubuntu:trusty

# Set noninteractive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Update
RUN apt-get update

# Start editing
# Install package here for cache
RUN apt-get -y install supervisor postfix sasl2-bin opendkim opendkim-tools

# Add files
ADD catcatnight/assets/install.sh /opt/install.sh

ADD main.cf /etc/postfix/main.cf
ADD mailname /etc/mailname
ADD virtual /etc/postfix/virtual
ADD aliases /etc/aliases
ADD entrypoint.sh /entrypoint.sh

CMD /opt/install.sh;/usr/bin/supervisord -c /etc/supervisor/supervisord.conf