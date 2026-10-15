package com.docanalyser.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * DataSource configuration that supports both standard Spring Boot datasource
 * properties and platform-injected DATABASE_URL connection strings (e.g., from Render / Heroku).
 *
 * Format: postgres://user:password@host:port/database or postgresql://...
 * Converted to: jdbc:postgresql://host:port/database with credentials applied to HikariCP.
 */
@Configuration
public class DataSourceConfig {

    private static final Logger log = LoggerFactory.getLogger(DataSourceConfig.class);

    private static final Pattern DB_URL_PATTERN = Pattern.compile(
            "^(?:postgres|postgresql)://(?:([^:]+)(?::([^@]*))?@)?([^:/]+)(?::(\\d+))?/(.+)$"
    );

    @Value("${DATABASE_URL:}")
    private String databaseUrl;

    @Value("${spring.datasource.url:}")
    private String defaultUrl;

    @Value("${spring.datasource.username:}")
    private String defaultUsername;

    @Value("${spring.datasource.password:}")
    private String defaultPassword;

    @Value("${spring.datasource.driver-class-name:org.postgresql.Driver}")
    private String driverClassName;

    @Bean
    @Primary
    public DataSource dataSource() {
        HikariConfig config = new HikariConfig();
        config.setDriverClassName(driverClassName);

        String rawUrl = databaseUrl;
        if (rawUrl != null && !rawUrl.isBlank()) {
            rawUrl = rawUrl.trim();
            if (rawUrl.startsWith("jdbc:")) {
                config.setJdbcUrl(rawUrl);
                if (defaultUsername != null && !defaultUsername.isBlank()) {
                    config.setUsername(defaultUsername);
                }
                if (defaultPassword != null && !defaultPassword.isBlank()) {
                    config.setPassword(defaultPassword);
                }
            } else {
                Matcher matcher = DB_URL_PATTERN.matcher(rawUrl);
                if (matcher.matches()) {
                    String user = matcher.group(1);
                    String password = matcher.group(2);
                    String host = matcher.group(3);
                    String portStr = matcher.group(4);
                    String dbAndQuery = matcher.group(5);

                    int port = (portStr != null && !portStr.isBlank()) ? Integer.parseInt(portStr) : 5432;

                    if (user != null) {
                        config.setUsername(URLDecoder.decode(user, StandardCharsets.UTF_8));
                    }
                    if (password != null) {
                        config.setPassword(URLDecoder.decode(password, StandardCharsets.UTF_8));
                    }

                    String jdbcUrl = "jdbc:postgresql://" + host + ":" + port + "/" + dbAndQuery;
                    config.setJdbcUrl(jdbcUrl);
                    log.info("Configured DataSource from DATABASE_URL -> jdbc:postgresql://{}:{}/{}", host, port, dbAndQuery.split("\\?")[0]);
                } else {
                    try {
                        URI uri = new URI(rawUrl);
                        String userInfo = uri.getUserInfo();
                        if (userInfo != null && userInfo.contains(":")) {
                            String[] parts = userInfo.split(":", 2);
                            config.setUsername(URLDecoder.decode(parts[0], StandardCharsets.UTF_8));
                            config.setPassword(URLDecoder.decode(parts[1], StandardCharsets.UTF_8));
                        }
                        int port = uri.getPort() == -1 ? 5432 : uri.getPort();
                        String path = uri.getPath();
                        if (path != null && path.startsWith("/")) {
                            path = path.substring(1);
                        }
                        String jdbcUrl = "jdbc:postgresql://" + uri.getHost() + ":" + port + "/" + path;
                        if (uri.getQuery() != null && !uri.getQuery().isBlank()) {
                            jdbcUrl += "?" + uri.getQuery();
                        }
                        config.setJdbcUrl(jdbcUrl);
                        log.info("Configured DataSource from URI -> jdbc:postgresql://{}:{}/{}", uri.getHost(), port, path);
                    } catch (Exception e) {
                        log.warn("Could not parse DATABASE_URL as URI, using fallback properties: {}", e.getMessage());
                        config.setJdbcUrl(defaultUrl);
                        config.setUsername(defaultUsername);
                        config.setPassword(defaultPassword);
                    }
                }
            }
        } else {
            config.setJdbcUrl(defaultUrl);
            config.setUsername(defaultUsername);
            config.setPassword(defaultPassword);
        }

        config.setMaximumPoolSize(10);
        config.setMinimumIdle(2);
        config.setConnectionTimeout(30000);
        config.setIdleTimeout(600000);
        config.setMaxLifetime(1800000);

        return new HikariDataSource(config);
    }
}
