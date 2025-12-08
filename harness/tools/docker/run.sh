sudo docker run -d \
--name clickhouse-test \
--restart unless-stopped \
-p 8124:8124 \
-p 9001:9001 \
-p 9005:9005 \
--platform linux/arm64/v8 \
--ulimit nofile=262144:262144 \
-v="/data/clickhouse/test:/var/lib/clickhouse" \
-v="/var/log/clickhouse-server/test:/var/log/clickhouse-server" \
-v="/etc/clickhouse-server/test/users.xml:/etc/clickhouse-server/users.xml" \
-v="/etc/clickhouse-server/test/config.xml:/etc/clickhouse-server/config.xml" \
clickhouse/clickhouse-server:22.12.1