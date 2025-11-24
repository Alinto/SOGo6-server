#bash

cd /workspace/scripts/init
curl -X PATCH -H 'Content-Type: application/json' -d @system_settings.json http://localhost:5000/api/v1/admin-config/system
curl -X PATCH -H 'Content-Type: application/json' -d @domain_settings.json http://localhost:5000/api/v1/admin-config/domain-default
