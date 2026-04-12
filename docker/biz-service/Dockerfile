FROM eclipse-temurin:21-jdk AS builder
WORKDIR /build
COPY . .
RUN ./gradlew :biz-service:bootJar -x test --no-daemon 2>/dev/null || \
    echo "Gradle wrapper not found — pre-built JAR expected"

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /build/biz-service/build/libs/*.jar app.jar 2>/dev/null || true
EXPOSE 8081
ENV JAVA_OPTS="-Xms256m -Xmx384m -XX:+UseZGC"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
