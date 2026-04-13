FROM eclipse-temurin:21-jdk AS builder
WORKDIR /build
COPY . .
RUN chmod +x gradlew && ./gradlew :biz-service:bootJar -x test --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /build/biz-service/build/libs/*.jar app.jar
EXPOSE 8081
ENV JAVA_OPTS="-Xms256m -Xmx384m -XX:+UseZGC"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
