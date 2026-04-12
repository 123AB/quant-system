FROM gradle:8-jdk21 AS builder
WORKDIR /src
COPY . .
RUN gradle :biz-service:bootJar --no-daemon -x test

FROM eclipse-temurin:21-jre-alpine
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
WORKDIR /app
COPY --from=builder /src/biz-service/build/libs/*.jar app.jar
ENV JAVA_OPTS="-Xms256m -Xmx384m -XX:+UseZGC -Dspring.threads.virtual.enabled=true"
EXPOSE 9001
ENTRYPOINT ["sh", "-c", "java ${JAVA_OPTS} -jar app.jar"]
