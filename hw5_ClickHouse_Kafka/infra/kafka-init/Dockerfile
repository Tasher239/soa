FROM confluentinc/cp-kafka:7.8.0

USER root

COPY init.sh /init.sh
RUN chmod +x /init.sh

ENTRYPOINT ["/init.sh"]
