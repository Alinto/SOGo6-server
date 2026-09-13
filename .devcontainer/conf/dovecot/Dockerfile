# Use Debian Trixie (13) as the base image
FROM debian:13-slim

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C

# Update and install Dovecot 2.4 with LDA, Sieve, LDAP, and SQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        dovecot-core \
        dovecot-imapd \
        dovecot-lmtpd \
        dovecot-sieve \
        dovecot-ldap \
        dovecot-mysql \
        dovecot-pgsql \
        ca-certificates \
        ssl-cert && \
    groupadd -g 1000 vmail && \
    useradd -u 1000 -g 1000 vmail -d /srv/vmail && \
    passwd -l vmail && \
    rm -rf /etc/dovecot && \
    # mkdir /var/mail && \
    chown -R vmail:vmail /var/mail && \
    rm -rf /var/lib/apt/lists/*

# Generate a default SSL certificate (self-signed)
RUN make-ssl-cert generate-default-snakeoil && \
    mkdir -p /etc/dovecot && \
    ln -s /etc/ssl/certs/ssl-cert-snakeoil.pem /etc/dovecot/cert.pem && \
    ln -s /etc/ssl/private/ssl-cert-snakeoil.key /etc/dovecot/key.pem

# Conf
ADD dovecot.conf /etc/dovecot/dovecot.conf
ADD conf.d /etc/dovecot/conf.d

# Expose Dovecot ports
# 143 = IMAP
# 993 = IMAPS
# 24 = LMTP
# 587 = Submission
EXPOSE 143
EXPOSE 993
EXPOSE 24
EXPOSE 587

# Start Dovecot in the foreground
VOLUME ["/etc/dovecot", "/srv/mail"]
CMD ["/usr/sbin/dovecot", "-F"]