FROM grafana/grafana-oss:11.5.0

USER root
RUN set -eux; \
    curl -k -L --fail \
      -o /tmp/grafana-clickhouse-datasource.zip \
      https://grafana.com/api/plugins/grafana-clickhouse-datasource/versions/latest/download; \
    unzip -q /tmp/grafana-clickhouse-datasource.zip -d /var/lib/grafana/plugins; \
    rm /tmp/grafana-clickhouse-datasource.zip; \
    chown -R grafana:root /var/lib/grafana/plugins/grafana-clickhouse-datasource

USER grafana
