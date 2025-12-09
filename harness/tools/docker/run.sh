sudo docker run -d \
--name lightspeed \
--network host \
--restart unless-stopped \
-e CLICKHOUSE_UID=101 -e CLICKHOUSE_GID=101 \
--platform linux/amd64 \
--ulimit nofile=262144:262144 \
-v="$(pwd)/data/lightspeed:/var/lib/clickhouse" \
-v="$(pwd)/log/lightspeed:/var/log/clickhouse-server" \
-v="$(pwd)/config/users.xml:/etc/clickhouse-server/users.xml" \
-v="$(pwd)/config/config.xml:/etc/clickhouse-server/config.xml" \
-v="$(pwd)/../../../projects:/var/lib/clickhouse/user_files/projects:ro" \
clickhouse/clickhouse-server:22.12.1