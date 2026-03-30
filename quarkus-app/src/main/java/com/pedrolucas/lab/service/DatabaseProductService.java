package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.ProductDTO;
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
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@ApplicationScoped
public class DatabaseProductService {

    private static final int MAX_COUNT = 500;
    private static final String PRODUCTS_SQL = """
            SELECT id, name, category, price, brand, region, segment, primary_tag, secondary_tag, tertiary_tag
            FROM benchmark_products
            ORDER BY id
            LIMIT ?
            """;

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

    public List<ProductDTO> getProducts(int count) {
        int limit = Math.max(1, Math.min(count, MAX_COUNT));

        try (Connection connection = getDataSource().getConnection();
             PreparedStatement statement = connection.prepareStatement(PRODUCTS_SQL)) {
            statement.setInt(1, limit);

            try (ResultSet resultSet = statement.executeQuery()) {
                List<ProductDTO> products = new ArrayList<>(limit);
                while (resultSet.next()) {
                    products.add(mapProduct(resultSet));
                }
                return products;
            }
        } catch (SQLException e) {
            throw new WebApplicationException(
                    "Failed to load DB-backed products.",
                    e,
                    Response.Status.INTERNAL_SERVER_ERROR
            );
        }
    }

    void closePool(@Observes ShutdownEvent shutdownEvent) {
        AgroalDataSource current = dataSource;
        if (current != null) {
            current.close();
        }
    }

    private AgroalDataSource getDataSource() {
        AgroalDataSource current = dataSource;
        if (current != null) {
            return current;
        }

        synchronized (this) {
            if (dataSource == null) {
                String url = jdbcUrl
                        .filter(value -> !value.isBlank())
                        .orElseThrow(() -> new WebApplicationException(
                                "Set benchmark.datasource.url to enable the DB-backed benchmark path.",
                                Response.Status.SERVICE_UNAVAILABLE
                        ));

                AgroalConnectionFactoryConfigurationSupplier factory =
                        new AgroalConnectionFactoryConfigurationSupplier()
                                .connectionProviderClassName("org.postgresql.Driver")
                                .jdbcUrl(url)
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

    private ProductDTO mapProduct(ResultSet resultSet) throws SQLException {
        Map<String, String> attributes = new LinkedHashMap<>();
        attributes.put("brand", resultSet.getString("brand"));
        attributes.put("region", resultSet.getString("region"));
        attributes.put("segment", resultSet.getString("segment"));

        List<String> tags = List.of(
                resultSet.getString("primary_tag"),
                resultSet.getString("secondary_tag"),
                resultSet.getString("tertiary_tag")
        );

        return new ProductDTO(
                resultSet.getLong("id"),
                resultSet.getString("name"),
                resultSet.getString("category"),
                resultSet.getDouble("price"),
                tags,
                attributes
        );
    }
}
