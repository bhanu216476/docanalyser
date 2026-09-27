# ==============================================================================
# DocAnalyser Spring Boot Backend - Multi-Stage Production Dockerfile
# ==============================================================================

# Stage 1: Build stage
FROM maven:3.9.8-eclipse-temurin-21-alpine AS builder

WORKDIR /build

# Copy project definition and source code
COPY spring-boot-service/pom.xml ./pom.xml
COPY spring-boot-service/src ./src

# Build production jar without running test suite in container build
RUN mvn clean package -DskipTests --no-transfer-progress

# Stage 2: Production runtime stage
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy built artifact
COPY --from=builder /build/target/*.jar app.jar
RUN chown -R appuser:appgroup /app

USER appuser

# Expose Spring Boot port
EXPOSE 8080

# Healthcheck using existing health endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/api/health || exit 1

ENTRYPOINT ["java", "-Djava.security.egd=file:/dev/./urandom", "-jar", "app.jar"]
