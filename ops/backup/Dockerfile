FROM postgres:17-alpine
RUN apk add --no-cache aws-cli openssl tzdata
COPY ops/backup/backup.sh ops/backup/restore.sh ops/backup/schedule.sh ops/backup/verify_restore.sql /opt/backup/
RUN chmod 0555 /opt/backup/*.sh
ENTRYPOINT ["/opt/backup/schedule.sh"]
