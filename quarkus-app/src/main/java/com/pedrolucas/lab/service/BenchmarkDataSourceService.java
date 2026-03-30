package com.pedrolucas.lab.service;

import io.agroal.api.AgroalDataSource;
import io.agroal.api.configuration.supplier.AgroalConnectionFactoryConfigurationSupplier;
import io.agroal.api.configuration.supplier.AgroalConnectionPoolConfigurationSupplier;
import io.agroal.api.configuration.supplier.AgroalDataSourceConfigurationSupplier;
import io.agroal.api.security.NamePrincipal;
import io.agroal.api.security.SimplePassword;
import io.quarkus.runtime.ShutdownEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.Duration;
import java.util.Optional;

@ApplicationScoped
public class BenchmarkDataSourceService {

    @ConfigProperty(name = "benchmark.datasource.url")
    Optional<String> jdbcUrl;

    @ConfigProperty(name = "benchmark.datasource.username", defaultValue = "benchmark")
    String username;

    @ConfigProperty(name = "benchmark.datasource.password", defaultValue = "benchmark")
    String password;

    @ConfigProperty(name = "benchmark.datasource.initial-size", defaultValue = "2")
    int initialSize;

    @ConfigProperty(name = "benchmark.datasource.min-size", defaultValue = "2")
    int minSize;

    @ConfigProperty(name = "benchmark.datasource.max-size", defaultValue = "16")
    int maxSize;

    @ConfigProperty(name = "benchmark.datasource.acquisition-timeout-seconds", defaultValue = "2")
    long acquisitionTimeoutSeconds;

    private volatile AgroalDataSource dataSource;

    public Connection getConnection() throws SQLException {
        return getDataSource().getConnection();
    }

    public boolean isConfigured() {
        return jdbcUrl.filter(value -> !value.isBlank()).isPresent();
    }

    public void requireConfigured() {
        configuredUrl();
    }

    void closePool(@Observes ShutdownEvent shutdownEvent) {
        AgroalDataSource current = dataSource;
        if (current != null) {
            current.close();
            dataSource = null;
        }
    }

    private AgroalDataSource getDataSource() {
        AgroalDataSource current = dataSource;
        if (current != null) {
            return current;
        }

        synchronized (this) {
            if (dataSource == null) {
                AgroalConnectionFactoryConfigurationSupplier factory =
                        new AgroalConnectionFactoryConfigurationSupplier()
                                .connectionProviderClassName("org.postgresql.Driver")
                                .jdbcUrl(configuredUrl())
                                .principal(new NamePrincipal(username))
                                .credential(new SimplePassword(password));

                AgroalConnectionPoolConfigurationSupplier pool =
                        new AgroalConnectionPoolConfigurationSupplier()
                                .connectionFactoryConfiguration(factory)
                                .initialSize(initialSize)
                                .minSize(minSize)
                                .maxSize(maxSize)
                                .acquisitionTimeout(Duration.ofSeconds(acquisitionTimeoutSeconds));

                AgroalDataSourceConfigurationSupplier configuration =
                        new AgroalDataSourceConfigurationSupplier()
                                .connectionPoolConfiguration(pool);

                try {
                    dataSource = AgroalDataSource.from(configuration);
                } catch (SQLException e) {
                    throw new WebApplicationException(
                            "Failed to initialize the DB-backed benchmark pool.",
                            e,
                            Response.Status.INTERNAL_SERVER_ERROR
                    );
                }
            }

            return dataSource;
        }
    }

    private String configuredUrl() {
        return jdbcUrl
                .filter(value -> !value.isBlank())
                .orElseThrow(() -> new WebApplicationException(
                        "Set benchmark.datasource.url to enable the DB-backed benchmark path.",
                        Response.Status.SERVICE_UNAVAILABLE
                ));
    }
}
