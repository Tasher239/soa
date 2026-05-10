FROM cassandra:4.1

COPY schema.cql /schema.cql
COPY init.sh /init.sh
RUN chmod +x /init.sh

ENTRYPOINT ["/init.sh"]
