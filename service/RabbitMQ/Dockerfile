FROM rabbitmq:3-management

# Zugangsdaten für Admin
ENV RABBITMQ_DEFAULT_USER=admin
ENV RABBITMQ_DEFAULT_PASS=avg123

# UI auf Port 15672 aktivieren
RUN rabbitmq-plugins enable --offline rabbitmq_management

EXPOSE 5672 15672
