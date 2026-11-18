FROM maven:3.9.16-eclipse-temurin-21-noble AS build
WORKDIR /workspace
COPY pom.xml ./pom.xml
COPY src ./src
# Packaging compiles the application only. Database-backed tests run in the
# isolated test runner, never during an image build.
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21.0.9_10-jre-noble AS runtime
WORKDIR /app
COPY --from=build --chown=10001:10001 \
  /workspace/target/paymesh-backend-0.0.1-SNAPSHOT.jar /app/app.jar
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
